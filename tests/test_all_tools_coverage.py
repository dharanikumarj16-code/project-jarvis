"""
tests/test_all_tools_coverage.py
================================
Validates comprehensive tool coverage, schema validity, discovery for FunctionGemma
and the Layer 2 reasoning agent, permissions enforcement, and safe tool execution.
"""

import pytest
import asyncio
from pathlib import Path

from app.tools.bus import tool_bus
from app.tools.registry import register_all_tools
from app.permissions import PermissionLevel
from app.local_brain import local_brain
from app.agent import build_dynamic_tools


@pytest.fixture(scope="module", autouse=True)
def setup_tools():
    """Ensure all tools are registered in UnifiedToolBus."""
    tool_bus.tools.clear()
    register_all_tools()
    local_brain._refresh_schema_cache()


def test_registry_populated_and_no_duplicates():
    """Verify that UnifiedToolBus is populated and keys are unique."""
    assert len(tool_bus.tools) >= 35, f"Expected at least 35 registered tools, got {len(tool_bus.tools)}"
    
    names = list(tool_bus.tools.keys())
    assert len(names) == len(set(names)), "Duplicate tool names detected in UnifiedToolBus"


def test_every_registered_tool_has_valid_attributes():
    """Verify that every tool has name, description, schema, permission, category, and executor."""
    allowed_categories = {
        "SYSTEM", "TERMINAL", "WINDOWS", "INPUT", "UIA", "WEB", "BROWSER", "FILESYSTEM", "VISION", "PATTERNS", "COMMUNICATION", "MEDIA"
    }

    for name, tool_def in tool_bus.tools.items():
        assert tool_def.name == name, f"Tool key '{name}' does not match definition name '{tool_def.name}'"
        assert len(tool_def.description.strip()) > 5, f"Tool '{name}' has missing or too short description"
        assert isinstance(tool_def.input_schema, dict), f"Tool '{name}' input_schema is not a dict"
        assert isinstance(tool_def.permission_level, PermissionLevel), f"Tool '{name}' invalid permission level"
        assert tool_def.category.upper() in allowed_categories, f"Tool '{name}' category '{tool_def.category}' is unrecognized"
        assert callable(tool_bus.executors.get(name)), f"Tool '{name}' executor is not registered or callable"


def test_functiongemma_schema_conversion_coverage():
    """Verify that FunctionGemma schema converter converts 100% of registered tools without error."""
    schemas = local_brain.get_all_tool_schemas()
    assert len(schemas) == len(tool_bus.tools), "Schema count must equal registered tool count"

    for entry in schemas:
        assert entry.get("type") == "function"
        fn = entry.get("function", {})
        assert "name" in fn and fn["name"] in tool_bus.tools
        assert "description" in fn and len(fn["description"]) > 0
        assert "parameters" in fn
        params = fn["parameters"]
        assert params.get("type") == "object"
        assert "properties" in params


def test_agent_dynamic_tools_conversion():
    """Verify that the Layer 2 reasoning agent can convert all registered tools to PydanticAI tools."""
    pydantic_tools = build_dynamic_tools()
    assert len(pydantic_tools) == len(tool_bus.tools), (
        f"Agent dynamic tools count ({len(pydantic_tools)}) must match registered tools ({len(tool_bus.tools)})"
    )


def test_tool_discovery_by_intent():
    """Verify that filter_tools_for_request selects appropriate tools for varied user requests."""
    # 1. Application and window launch request
    app_tools = [t["function"]["name"] for t in local_brain.filter_tools_for_request("Open VS Code and start my project")]
    assert any(name in app_tools for name in ["open_app", "focus_window", "macro_windows_search"]), (
        f"Expected app/window launch tools in {app_tools}"
    )

    # 2. Testing and code execution workflow
    test_tools = [t["function"]["name"] for t in local_brain.filter_tools_for_request("Find the error in my project and run the tests")]
    assert any(name in test_tools for name in ["terminal_run_action", "terminal_run_safe", "file_search", "read_file"]), (
        f"Expected terminal or filesystem tools in {test_tools}"
    )

    # 3. UI Automation / Button click
    ui_tools = [t["function"]["name"] for t in local_brain.filter_tools_for_request("Find the Save button and click it")]
    assert any(name in ui_tools for name in ["uia_find", "uia_invoke", "uia_get_tree", "mouse_click"]), (
        f"Expected UIA or mouse tools in {ui_tools}"
    )

    # 4. Process inspection
    proc_tools = [t["function"]["name"] for t in local_brain.filter_tools_for_request("Check whether my development server is running")]
    assert any(name in proc_tools for name in ["list_running_processes", "process_info", "check_app_running"]), (
        f"Expected process/app inspection tools in {proc_tools}"
    )

    # 5. Native Filesystem operations
    file_tools = [t["function"]["name"] for t in local_brain.filter_tools_for_request("Read the file config.json and search for directory")]
    assert any(name in file_tools for name in ["read_file", "file_search", "list_directory", "file_exists"]), (
        f"Expected filesystem tools in {file_tools}"
    )

    # 6. Audio / System control
    sys_tools = [t["function"]["name"] for t in local_brain.filter_tools_for_request("Mute the sound and check wifi network status")]
    assert any(name in sys_tools for name in ["mute_audio", "set_volume", "get_wifi_networks"]), (
        f"Expected audio/network tools in {sys_tools}"
    )


@pytest.mark.asyncio
async def test_safe_read_only_tool_executions():
    """Verify that read-only tools actually execute cleanly and return structured data."""
    # 1. System Info
    res_sys = await tool_bus.execute("get_system_information", {})
    assert res_sys.get("success") is True
    data_sys = res_sys.get("data", {})
    assert "cpu_percent" in data_sys
    assert "ram_total_gb" in data_sys

    # 2. Process listing
    res_proc = await tool_bus.execute("list_running_processes", {})
    assert res_proc.get("success") is True
    data_proc = res_proc.get("data", {})
    assert "processes" in data_proc
    assert len(data_proc["processes"]) > 0

    # 3. Native Filesystem exists & search
    res_exists = await tool_bus.execute("file_exists", {"path": "pytest.ini"})
    assert res_exists.get("success") is True
    assert res_exists.get("data", {}).get("exists") is True

    # 4. Native Filesystem list directory
    res_list = await tool_bus.execute("list_directory", {"path": "."})
    assert res_list.get("success") is True
    assert "entries" in res_list.get("data", {})

    # 5. Visible Windows
    res_win = await tool_bus.execute("win_list_visible", {})
    assert res_win.get("success") is True
    assert isinstance(res_win.get("data"), list)


def test_sensitive_permissions_enforced():
    """Verify that potentially destructive or modifying tools have SENSITIVE or ACTION permissions."""
    sensitive_tools = ["system_shutdown", "system_restart", "kill_process", "terminal_run_sudo", "file_delete"]
    for t_name in sensitive_tools:
        if t_name in tool_bus.tools:
            tool_def = tool_bus.tools[t_name]
            assert tool_def.permission_level == PermissionLevel.SENSITIVE, (
                f"Tool '{t_name}' must have SENSITIVE permission, got {tool_def.permission_level}"
            )


@pytest.mark.asyncio
async def test_non_crashing_error_handling():
    """Verify that invalid arguments or non-existent paths return structured failure and do not crash."""
    res_file = await tool_bus.execute("read_file", {"path": "non_existent_file_xyz_123.txt"})
    # Tool executed cleanly without unhandled exception, but reported failure for missing file
    data_file = res_file.get("data", {})
    assert data_file.get("success") is False
    assert "error" in data_file

    res_proc = await tool_bus.execute("process_info", {"pid": 99999999})
    data_proc = res_proc.get("data", {})
    assert data_proc.get("success") is False
    assert "error" in data_proc


@pytest.mark.asyncio
async def test_one_second_execution_gap():
    """Verify that multi-tool execution enforces a 1-second gap between tool calls."""
    import time
    from unittest.mock import AsyncMock, patch

    # 1. Test UnifiedToolBus level pacing
    tool_bus.set_execution_delay(1.0)
    try:
        t0 = time.perf_counter()
        await tool_bus.execute("file_exists", {"path": "pytest.ini"})
        await tool_bus.execute("file_exists", {"path": "pytest.ini"})
        elapsed = time.perf_counter() - t0
        assert elapsed >= 0.95, f"Expected at least ~1.0s gap between tool executions, got {elapsed:.2f}s"
    finally:
        tool_bus.set_execution_delay(0.0)  # Reset for other tests

    # 2. Test FunctionGemmaLocalBrain run_tool_loop level pacing
    mock_client = AsyncMock()

    class MockResponse:
        class message:
            content = ""
            tool_calls = [
                {"function": {"name": "file_exists", "arguments": {"path": "pytest.ini"}}},
                {"function": {"name": "list_directory", "arguments": {"path": "."}}}
            ]

    mock_client.chat.return_value = MockResponse()

    with patch.object(local_brain, "_client", mock_client), \
         patch.object(local_brain, "get_effective_backend", return_value="ollama"):
        t1 = time.perf_counter()
        res = await local_brain.run_tool_loop("Check files", max_turns=1, tool_delay=1.0)
        loop_elapsed = time.perf_counter() - t1
        assert res["executed_count"] == 2
        assert loop_elapsed >= 1.9, f"Expected >= 2.0s for 2 tool executions with 1.0s gap, got {loop_elapsed:.2f}s"


@pytest.mark.asyncio
async def test_press_window_button_and_hotkey_execution():
    """Verify that press_key accepts natural phrasings like 'window button', 'ctrl c', and semantic shortcuts."""
    from unittest.mock import patch, MagicMock

    with patch("app.tools.computer.keyboard.PyAutoGUIAdapter") as MockAdapter:
        mock_instance = MagicMock()
        MockAdapter.return_value = mock_instance

        # 1. Natural language "window button"
        res_win = await tool_bus.execute("press_key", {"key": "window button"})
        assert res_win.get("success") is True
        assert res_win.get("data", {}).get("success") is True
        assert "win" in res_win.get("data", {}).get("message", "")

        # 2. Multi-key chord "ctrl c" and "ctrl + n"
        res_chord = await tool_bus.execute("press_key", {"key": "ctrl c"})
        assert res_chord.get("success") is True
        assert res_chord.get("data", {}).get("success") is True

        res_ctrl_n = await tool_bus.execute("press_key", {"key": "ctrl + n"})
        assert res_ctrl_n.get("success") is True
        assert res_ctrl_n.get("data", {}).get("success") is True

        # 3. Semantic shortcut "copy"
        res_copy = await tool_bus.execute("press_key", {"key": "copy"})
        assert res_copy.get("success") is True
        assert res_copy.get("data", {}).get("success") is True

        # 4. Direct KeyboardController.press with chord
        from app.tools.computer.keyboard import KeyboardController
        kbd = KeyboardController(backend=mock_instance)
        kbd.press("ctrl + n")
        mock_instance.hotkey.assert_called_with("ctrl", "n")


async def test_mouse_optimization_tool_executions():
    """Verify that mouse tools (click, move, scroll, drag, get_pos) work with smart handlers."""
    from unittest.mock import patch, MagicMock

    with patch("app.tools.computer.mouse.PyAutoGUIAdapter") as MockAdapter:
        mock_instance = MagicMock()
        mock_instance.size.return_value = (1920, 1080)
        mock_instance.position.return_value = (500, 300)
        MockAdapter.return_value = mock_instance

        # 1. mouse_click with coordinates
        res_click = await tool_bus.execute("mouse_click", {"x": 500, "y": 300})
        assert res_click.get("success") is True
        assert res_click.get("data", {}).get("success") is True

        # 2. mouse_click center
        res_center = await tool_bus.execute("mouse_click", {"target": "center"})
        assert res_center.get("success") is True
        assert res_center.get("data", {}).get("success") is True

        # 3. mouse_move
        res_move = await tool_bus.execute("mouse_move", {"x": 600, "y": 400})
        assert res_move.get("success") is True
        assert res_move.get("data", {}).get("success") is True

        # 4. mouse_scroll
        res_scroll = await tool_bus.execute("mouse_scroll", {"direction": "down"})
        assert res_scroll.get("success") is True
        assert res_scroll.get("data", {}).get("clicks") == -5

        # 5. mouse_drag
        res_drag = await tool_bus.execute("mouse_drag", {"x": 700, "y": 500})
        assert res_drag.get("success") is True

        # 6. mouse_get_position
        res_pos = await tool_bus.execute("mouse_get_position", {})
        assert res_pos.get("success") is True
        assert res_pos.get("data", {}).get("x") == 500
        assert res_pos.get("data", {}).get("y") == 300


@pytest.mark.asyncio
async def test_uia_element_detection_and_location():
    """Verify UIA semantic element classification, bounding box / center detection, and execution."""
    from unittest.mock import MagicMock, patch
    from app.tools.uia import _classify_control, _extract_bounding_box_and_center, uia_detect_elements, uia_get_element_location

    # 1. Test _extract_bounding_box_and_center
    mock_ctrl = MagicMock()
    mock_rect = MagicMock()
    mock_rect.left = 100
    mock_rect.top = 200
    mock_rect.right = 300
    mock_rect.bottom = 400
    mock_rect.width.return_value = 200
    mock_rect.height.return_value = 200
    mock_rect.xcenter.return_value = 200
    mock_rect.ycenter.return_value = 300
    mock_ctrl.BoundingRectangle = mock_rect

    bbox, center = _extract_bounding_box_and_center(mock_ctrl)
    assert bbox == {"left": 100, "top": 200, "right": 300, "bottom": 400, "width": 200, "height": 200}
    assert center == {"x": 200, "y": 300}

    # 2. Test semantic classification
    # Button
    btn = MagicMock()
    btn.ControlTypeName = "ButtonControl"
    btn.Name = "Click Here"
    btn.AutomationId = "button_1"
    roles_btn = _classify_control(btn)
    assert roles_btn["is_button"] is True
    assert roles_btn["clickable"] is True

    # Search Bar
    search = MagicMock()
    search.ControlTypeName = "EditControl"
    search.Name = "Search or type URL"
    search.AutomationId = "search_box"
    roles_search = _classify_control(search)
    assert roles_search["is_search_bar"] is True
    assert roles_search["is_input_field"] is True

    # Close Button
    close_btn = MagicMock()
    close_btn.ControlTypeName = "ButtonControl"
    close_btn.Name = "Close"
    close_btn.AutomationId = "CloseButton"
    roles_close = _classify_control(close_btn)
    assert roles_close["is_close_button"] is True
    assert roles_close["is_button"] is True

    # Submit Button
    submit_btn = MagicMock()
    submit_btn.ControlTypeName = "ButtonControl"
    submit_btn.Name = "Submit Form"
    submit_btn.AutomationId = "btn_submit"
    roles_submit = _classify_control(submit_btn)
    assert roles_submit["is_submit_button"] is True

    # Skip Button (e.g. YouTube Ad or Intro)
    skip_btn = MagicMock()
    skip_btn.ControlTypeName = "ButtonControl"
    skip_btn.Name = "Skip Ad"
    skip_btn.AutomationId = "skip_ad_button"
    roles_skip = _classify_control(skip_btn)
    assert roles_skip["is_skip_button"] is True
    assert "skip_button" in roles_skip["roles"]

    # Enter / Next Button
    enter_btn = MagicMock()
    enter_btn.ControlTypeName = "ButtonControl"
    enter_btn.Name = "Enter"
    enter_btn.AutomationId = "btn_enter"
    roles_enter = _classify_control(enter_btn)
    assert roles_enter["is_enter_button"] is True
    assert "enter_button" in roles_enter["roles"]

    # Box / Container
    ad_box = MagicMock()
    ad_box.ControlTypeName = "PaneControl"
    ad_box.Name = "Video Ad Container"
    ad_box.AutomationId = "ad_container"
    roles_box = _classify_control(ad_box)
    assert roles_box["is_box"] is True

    # Spatial containment check
    from app.tools.uia import _is_spatially_inside
    box_rect = {"left": 100, "top": 100, "right": 500, "bottom": 400}
    child_rect = {"left": 150, "top": 150, "right": 250, "bottom": 200}
    outside_rect = {"left": 600, "top": 600, "right": 700, "bottom": 700}
    assert _is_spatially_inside(child_rect, box_rect) is True
    assert _is_spatially_inside(outside_rect, box_rect) is False

    # 3. Test classification of all major Windows UIA control types
    ctrl_types_to_verify = [
        ("CheckBoxControl", "Agree to Terms", "is_checkbox", "checkbox"),
        ("RadioButtonControl", "Option A", "is_radio", "radio"),
        ("ComboBoxControl", "Select Language", "is_combobox", "combobox"),
        ("SliderControl", "Volume Slider", "is_slider", "slider"),
        ("TableControl", "Accounts Grid", "is_table", "table"),
        ("TabItemControl", "General Settings", "is_tab", "tab"),
        ("HyperlinkControl", "Privacy Policy", "is_link", "link"),
        ("TreeItemControl", "Project Folder", "is_tree_item", "tree"),
        ("MenuItemControl", "Save As", "is_menu_item", "menu"),
        ("ProgressBarControl", "Download Status", "is_progress_bar", "progress"),
        ("SpinnerControl", "Quantity Stepper", "is_spinner", "spinner"),
    ]
    for ctype, name, expected_flag, expected_family in ctrl_types_to_verify:
        mock = MagicMock()
        mock.ControlTypeName = ctype
        mock.Name = name
        mock.AutomationId = f"id_{name.lower().replace(' ', '_')}"
        info = _classify_control(mock)
        assert info[expected_flag] is True, f"Expected {expected_flag} True for {ctype}"
        assert info["control_family"] == expected_family, f"Expected family {expected_family} for {ctype}"

    # 4. Test all UIA tools registration in tool_bus
    assert "uia_detect_elements" in tool_bus.tools
    assert "uia_detect_box_content" in tool_bus.tools
    assert "uia_click_inside_box" in tool_bus.tools
    assert "uia_get_element_location" in tool_bus.tools
    assert "uia_click_element" in tool_bus.tools
    assert "uia_type_into_element" in tool_bus.tools
    assert "uia_toggle_element" in tool_bus.tools
    assert "uia_set_slider" in tool_bus.tools
    assert "uia_select_option" in tool_bus.tools
    assert "uia_get_table_data" in tool_bus.tools

    # 5. Filter tools for UI request verifies discovery including skip button / box content / slider / table
    filtered_box = [t["function"]["name"] for t in local_brain.filter_tools_for_request("detect box inside content like skip button enter button")]
    assert any(name in filtered_box for name in ["uia_detect_box_content", "uia_click_inside_box", "uia_detect_elements"]), (
        f"Expected box content tools in {filtered_box}"
    )

    filtered_slider = [t["function"]["name"] for t in local_brain.filter_tools_for_request("adjust volume slider or check table data")]
    assert any(name in filtered_slider for name in ["uia_set_slider", "uia_get_table_data", "uia_detect_elements"]), (
        f"Expected slider / table tools in {filtered_slider}"
    )



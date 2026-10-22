"""
test_action_patterns.py – Unit and Integration Tests for Universal User Action Patterns
======================================================================================
"""

import pytest
from unittest.mock import MagicMock, patch

from app.tools.bus import tool_bus
from app.tools.registry import register_all_tools
from app.local_brain import local_brain
from app.tools.action_patterns import (
    pattern_search_and_navigate,
    pattern_form_fill_and_submit,
    pattern_handle_dialog,
    pattern_tab_and_window,
    pattern_scroll_and_find,
    pattern_context_action,
    pattern_smart_click_or_type
)


@pytest.fixture(scope="module", autouse=True)
def setup_tools():
    """Ensure all tools are registered in UnifiedToolBus."""
    register_all_tools()
    local_brain._refresh_schema_cache()


def test_patterns_registered_in_tool_bus():
    """Verify all 7 action patterns are properly registered in UnifiedToolBus."""
    pattern_tools = [
        "pattern_search_and_navigate",
        "pattern_form_fill_and_submit",
        "pattern_handle_dialog",
        "pattern_tab_and_window",
        "pattern_scroll_and_find",
        "pattern_context_action",
        "pattern_smart_click_or_type"
    ]
    for tool_name in pattern_tools:
        assert tool_name in tool_bus.tools
        tdef = tool_bus.tools[tool_name]
        assert tdef.category == "PATTERNS"
        assert tdef.description != ""
        assert isinstance(tdef.input_schema, dict)


def test_patterns_discovered_by_local_brain():
    """Verify LocalBrain filters and discovers action patterns based on human intent."""
    req = "Fill out the registration form and submit"
    filtered = [t["function"]["name"] for t in local_brain.filter_tools_for_request(req)]
    assert "pattern_form_fill_and_submit" in filtered or "pattern_smart_click_or_type" in filtered

    req_dialog = "Dismiss this alert popup dialog"
    filtered_dialog = [t["function"]["name"] for t in local_brain.filter_tools_for_request(req_dialog)]
    assert "pattern_handle_dialog" in filtered_dialog


def test_pattern_search_and_navigate_browser():
    """Verify browser search pattern uses Ctrl+L and types query."""
    with patch("app.tools.action_patterns._get_active_window_info") as mock_win, \
         patch("app.tools.action_patterns.KeyboardController") as MockKbd:
        
        mock_win.return_value = {"title": "Google Chrome - New Tab", "class_name": "Chrome_WidgetWin_1"}
        mock_kbd_inst = MagicMock()
        MockKbd.return_value = mock_kbd_inst

        res = pattern_search_and_navigate("python tutorials", window_title="active", submit=True)
        assert res["success"] is True
        assert res["method"] == "browser_address_bar"
        mock_kbd_inst.hotkey.assert_called_with("ctrl", "l")
        mock_kbd_inst.type_text.assert_called_with("python tutorials")
        mock_kbd_inst.press.assert_called_with("enter")


def test_pattern_search_and_navigate_uia_desktop():
    """Verify desktop search pattern detects UIA search bar and clicks it."""
    with patch("app.tools.action_patterns._get_active_window_info") as mock_win, \
         patch("app.tools.uia.uia_detect_elements") as mock_det, \
         patch("app.tools.action_patterns.MouseController") as MockMouse, \
         patch("app.tools.action_patterns.KeyboardController") as MockKbd:

        mock_win.return_value = {"title": "File Explorer", "class_name": "CabinetWClass"}
        mock_det.return_value = {
            "search_bars": [{"name": "Search Box", "center": {"x": 800, "y": 60}}]
        }
        mock_mouse_inst = MagicMock()
        MockMouse.return_value = mock_mouse_inst
        mock_kbd_inst = MagicMock()
        MockKbd.return_value = mock_kbd_inst

        res = pattern_search_and_navigate("budget.xlsx", window_title="File Explorer", submit=True)
        assert res["success"] is True
        assert res["method"] == "uia_search_bar"
        mock_mouse_inst.click.assert_called_with(800, 60)
        mock_kbd_inst.type_text.assert_called_with("budget.xlsx")
        mock_kbd_inst.press.assert_called_with("enter")


def test_pattern_form_fill_and_submit():
    """Verify multi-field form input and submit button click."""
    with patch("app.tools.uia.uia_type_into_element") as mock_type, \
         patch("app.tools.uia.uia_click_element") as mock_click:

        mock_type.return_value = {"success": True}
        mock_click.return_value = {"success": True}

        fields = {"Username": "admin", "Password": "secretpassword"}
        res = pattern_form_fill_and_submit(fields, submit_button="Sign In", window_title="Login")

        assert res["success"] is True
        assert res["filled_fields"] == ["Username", "Password"]
        assert res["submitted"] is True
        mock_click.assert_called_with(window_title="Login", query="Sign In")


def test_pattern_handle_dialog_affirmative_and_negative():
    """Verify dialog handling for affirmative, negative, and close decisions."""
    with patch("app.tools.uia.uia_detect_elements") as mock_det, \
         patch("app.tools.uia.uia_click_element") as mock_click, \
         patch("app.tools.action_patterns.KeyboardController") as MockKbd:

        mock_kbd_inst = MagicMock()
        MockKbd.return_value = mock_kbd_inst

        # 1. Affirmative click OK
        mock_det.return_value = {
            "buttons": [{"name": "OK", "center": {"x": 500, "y": 400}}]
        }
        mock_click.return_value = {"success": True}
        res_aff = pattern_handle_dialog(decision="affirmative", window_title="Confirm")
        assert res_aff["success"] is True
        assert res_aff["target"] == "OK"

        # 2. Negative click Cancel
        mock_det.return_value = {
            "buttons": [{"name": "Cancel", "center": {"x": 600, "y": 400}}]
        }
        res_neg = pattern_handle_dialog(decision="negative", window_title="Confirm")
        assert res_neg["success"] is True
        assert res_neg["target"] == "Cancel"

        # 3. Close dismiss
        mock_det.return_value = {
            "close_buttons": [{"name": "Close", "center": {"x": 700, "y": 200}}]
        }
        res_close = pattern_handle_dialog(decision="close", window_title="Confirm")
        assert res_close["success"] is True


def test_pattern_tab_and_window():
    """Verify tab and window hotkeys."""
    with patch("app.tools.action_patterns.KeyboardController") as MockKbd:
        mock_kbd_inst = MagicMock()
        MockKbd.return_value = mock_kbd_inst

        res_new = pattern_tab_and_window("new_tab")
        assert res_new["success"] is True
        mock_kbd_inst.hotkey.assert_called_with("ctrl", "t")

        res_close = pattern_tab_and_window("close_tab")
        assert res_close["success"] is True
        mock_kbd_inst.hotkey.assert_called_with("ctrl", "w")

        res_max = pattern_tab_and_window("maximize")
        assert res_max["success"] is True
        mock_kbd_inst.hotkey.assert_called_with("win", "up")


def test_pattern_scroll_and_find():
    """Verify scrolling viewport to discover elements."""
    with patch("app.tools.uia.uia_get_element_location") as mock_loc, \
         patch("app.tools.action_patterns.MouseController") as MockMouse:

        mock_mouse_inst = MagicMock()
        MockMouse.return_value = mock_mouse_inst

        # First call fails, second call succeeds after scroll
        mock_loc.side_effect = [
            {"success": False, "center": None},
            {"success": True, "center": {"x": 400, "y": 600}, "location": {"width": 100, "height": 30}}
        ]

        res = pattern_scroll_and_find("Subscribe Button", max_scrolls=3, direction="down")
        assert res["success"] is True
        assert res["found_on_attempt"] == 1
        assert res["center"] == {"x": 400, "y": 600}
        mock_mouse_inst.scroll.assert_called_with(-5)


def test_pattern_smart_click_or_type():
    """Verify universal smart click or type dispatching."""
    with patch("app.tools.uia.uia_click_element") as mock_click, \
         patch("app.tools.uia.uia_type_into_element") as mock_type:

        mock_click.return_value = {"success": True}
        mock_type.return_value = {"success": True}

        # 1. Click mode (no text)
        res_click = pattern_smart_click_or_type(target="Submit Order")
        assert res_click["pattern"] == "smart_click"
        assert res_click["success"] is True
        mock_click.assert_called_with(window_title="active", query="Submit Order")

        # 2. Type mode (with text)
        res_type = pattern_smart_click_or_type(target="Email Address", text="user@example.com")
        assert res_type["pattern"] == "smart_type"
        assert res_type["success"] is True
        mock_type.assert_called_with(window_title="active", query="Email Address", text="user@example.com")

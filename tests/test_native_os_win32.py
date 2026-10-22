"""
test_native_os_win32.py – Unit and Integration Tests for Native OS, Subprocess, PyAutoGUI, and Win32 Tools
========================================================================================================
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from app.tools.bus import tool_bus
from app.tools.registry import register_all_tools
from app.local_brain import local_brain
from app.tools.native_os_win32 import (
    os_get_env,
    os_set_env,
    os_get_cwd,
    os_list_drives,
    subprocess_run_sync,
    subprocess_start_background,
    pyautogui_get_screen_size,
    pyautogui_locate_on_screen,
    pyautogui_mouse_down,
    pyautogui_mouse_up,
    pyautogui_alert,
    win32_get_foreground_window,
    win32_enum_windows,
    win32_set_window_pos,
    win32_show_desktop,
    win32_lock_workstation,
    win32_get_cursor_pos
)


@pytest.fixture(scope="module", autouse=True)
def setup_tools():
    """Ensure all tools are registered in UnifiedToolBus."""
    register_all_tools()
    local_brain._refresh_schema_cache()


def test_native_tools_registered_in_tool_bus():
    """Verify all 17 native OS/subprocess/pyautogui/win32 tools are registered in UnifiedToolBus."""
    tools = [
        "os_get_env",
        "os_set_env",
        "os_get_cwd",
        "os_list_drives",
        "subprocess_run_sync",
        "subprocess_start_background",
        "pyautogui_get_screen_size",
        "pyautogui_locate_on_screen",
        "pyautogui_mouse_down",
        "pyautogui_mouse_up",
        "pyautogui_alert",
        "win32_get_foreground_window",
        "win32_enum_windows",
        "win32_set_window_pos",
        "win32_show_desktop",
        "win32_lock_workstation",
        "win32_get_cursor_pos"
    ]
    for t_name in tools:
        assert t_name in tool_bus.tools, f"Expected {t_name} in tool_bus"
        tdef = tool_bus.tools[t_name]
        assert len(tdef.description) > 5
        assert isinstance(tdef.input_schema, dict)


def test_os_env_and_cwd():
    """Verify os_get_env, os_set_env, and os_get_cwd."""
    # Set and get env
    set_res = os_set_env("JARVIS_TEST_VAR", "active_value_123")
    assert set_res["success"] is True
    assert set_res["value"] == "active_value_123"

    get_res = os_get_env("JARVIS_TEST_VAR")
    assert get_res["success"] is True
    assert get_res["value"] == "active_value_123"

    # Get cwd
    cwd_res = os_get_cwd()
    assert cwd_res["success"] is True
    assert os.path.exists(cwd_res["cwd"])


def test_os_list_drives():
    """Verify os_list_drives returns valid drive statistics."""
    res = os_list_drives()
    assert res["success"] is True
    assert isinstance(res["drives"], list)
    assert len(res["drives"]) > 0
    c_drive = next((d for d in res["drives"] if "C:" in d["drive"]), None)
    assert c_drive is not None
    assert "total_gb" in c_drive or "status" in c_drive


def test_subprocess_execution():
    """Verify synchronous and background subprocess execution."""
    # 1. Sync run
    res_sync = subprocess_run_sync("python -c \"print('JARVIS_TEST_OUTPUT')\"")
    assert res_sync["success"] is True
    assert "JARVIS_TEST_OUTPUT" in res_sync["stdout"]
    assert res_sync["exit_code"] == 0

    # 2. Background start
    with patch("subprocess.Popen") as mock_popen:
        mock_proc = MagicMock()
        mock_proc.pid = 99999
        mock_popen.return_value = mock_proc

        res_bg = subprocess_start_background("dummy_daemon.exe")
        assert res_bg["success"] is True
        assert res_bg["pid"] == 99999


def test_pyautogui_tools():
    """Verify PyAutoGUI screen size, mouse hold/release, and alerts."""
    with patch("pyautogui.size") as mock_size, \
         patch("pyautogui.mouseDown") as mock_down, \
         patch("pyautogui.mouseUp") as mock_up, \
         patch("pyautogui.alert") as mock_alert:

        mock_size.return_value = (1920, 1080)

        # Screen size
        res_size = pyautogui_get_screen_size()
        assert res_size["success"] is True
        assert res_size["width"] == 1920
        assert res_size["height"] == 1080

        # Mouse down & up
        res_down = pyautogui_mouse_down(button="left", x=100, y=200)
        assert res_down["success"] is True
        mock_down.assert_called_with(x=100, y=200, button="left")

        res_up = pyautogui_mouse_up(button="left", x=100, y=200)
        assert res_up["success"] is True
        mock_up.assert_called_with(x=100, y=200, button="left")

        # Alert
        res_alert = pyautogui_alert("Test Alert", "JARVIS")
        assert res_alert["success"] is True
        mock_alert.assert_called_with(text="Test Alert", title="JARVIS")


def test_win32_tools():
    """Verify Win32 window management and cursor position."""
    # Cursor pos
    res_cursor = win32_get_cursor_pos()
    assert res_cursor["success"] is True
    assert "x" in res_cursor and "y" in res_cursor

    # Foreground window
    res_fg = win32_get_foreground_window()
    assert res_fg["success"] is True
    assert "hwnd" in res_fg
    assert "bounds" in res_fg

    # Enum windows
    res_enum = win32_enum_windows()
    assert res_enum["success"] is True
    assert res_enum["count"] > 0
    assert isinstance(res_enum["windows"], list)

    # Show desktop
    with patch("pyautogui.hotkey") as mock_hotkey:
        res_desk = win32_show_desktop()
        assert res_desk["success"] is True
        mock_hotkey.assert_called_with("win", "d")


def test_native_discovery_in_local_brain():
    """Verify FunctionGemma / LocalBrain filters discover these native OS/win32 tools."""
    # 1. Drive inspection
    req1 = "Check how much disk space is left on drive C"
    filt1 = [t["function"]["name"] for t in local_brain.filter_tools_for_request(req1)]
    assert any(name in filt1 for name in ["os_list_drives", "get_system_info", "list_directory"])

    # 2. Window position
    req2 = "Enumerate visible windows and set window position"
    filt2 = [t["function"]["name"] for t in local_brain.filter_tools_for_request(req2)]
    assert any(name in filt2 for name in ["win32_enum_windows", "win32_set_window_pos", "focus_window"])

    # 3. Environment variables
    req3 = "Get the environment variable PATH"
    filt3 = [t["function"]["name"] for t in local_brain.filter_tools_for_request(req3)]
    assert any(name in filt3 for name in ["os_get_env", "os_set_env", "get_system_info"])

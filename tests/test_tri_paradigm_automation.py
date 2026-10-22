"""
test_tri_paradigm_automation.py – Unit and Integration Tests for Tri-Paradigm Advanced Windows Automation
========================================================================================================
Validates the three key paradigms integrated into JARVIS:
  1. FastCUA: High-speed Accessibility Blindness Detection & Early Vision Escalation (uia.py)
  2. win-computer-use: Sub-50ms OpenCV Template Matching (vision.py)
  3. WindowsAgent: Post-Action State Verification & Recovery Loops (action_patterns.py)
"""

import os
import time
import pytest
import numpy as np
from unittest.mock import MagicMock, patch

from app.tools.bus import tool_bus
from app.tools.registry import register_all_tools
from app.tools.uia import is_window_accessibility_blind, uia_find, uia_detect_elements
from app.tools.vision import VisionManager, vision_match_template
from app.tools.action_patterns import pattern_handle_dialog, pattern_smart_click_or_type


@pytest.fixture(scope="module", autouse=True)
def setup_tools():
    """Ensure all tools are registered in UnifiedToolBus."""
    register_all_tools()


# =====================================================================
# 1. FastCUA: Accessibility Blindness Tests
# =====================================================================

def test_accessibility_blindness_detection_empty_children():
    """FastCUA: Control with 0 children is classified as accessibility blind."""
    mock_ctrl = MagicMock()
    mock_ctrl.GetChildren.return_value = []
    assert is_window_accessibility_blind(mock_ctrl) is True


def test_accessibility_blindness_detection_unnamed_canvas():
    """FastCUA: Control with only unnamed Pane/Custom controls is classified as accessibility blind."""
    child1 = MagicMock()
    child1.Name = ""
    child1.ControlTypeName = "PaneControl"
    child2 = MagicMock()
    child2.Name = ""
    child2.ControlTypeName = "CustomControl"

    mock_ctrl = MagicMock()
    mock_ctrl.GetChildren.return_value = [child1, child2]
    assert is_window_accessibility_blind(mock_ctrl) is True


def test_accessibility_blindness_detection_accessible_tree():
    """FastCUA: Standard window with named elements or buttons is NOT blind."""
    child1 = MagicMock()
    child1.Name = "File"
    child1.ControlTypeName = "MenuItemControl"
    child2 = MagicMock()
    child2.Name = "Save"
    child2.ControlTypeName = "ButtonControl"

    mock_ctrl = MagicMock()
    mock_ctrl.GetChildren.return_value = [child1, child2]
    assert is_window_accessibility_blind(mock_ctrl) is False


def test_uia_find_early_exit_on_blind_window():
    """FastCUA: uia_find() immediately returns escalate_to_vision on blind window."""
    with patch("app.tools.uia._get_window") as mock_get_win:
        mock_win = MagicMock()
        mock_win.GetChildren.return_value = []  # Blind!
        mock_get_win.return_value = mock_win

        res = uia_find(query="Submit", window_title="GameCanvas")
        assert res["success"] is False
        assert res["reason"] == "accessibility_blind"
        assert res.get("escalate_to_vision") is True


def test_uia_detect_elements_early_exit_on_blind_window():
    """FastCUA: uia_detect_elements() immediately flags accessibility blindness."""
    with patch("app.tools.uia._get_window") as mock_get_win:
        mock_win = MagicMock()
        mock_win.GetChildren.return_value = []  # Blind!
        mock_get_win.return_value = mock_win

        res = uia_detect_elements(window_title="DirectXApp")
        assert res["success"] is False
        assert res["reason"] == "accessibility_blind"
        assert res.get("escalate_to_vision") is True


# =====================================================================
# 2. win-computer-use: OpenCV Template Matching Tests
# =====================================================================

def test_vision_match_template_registered():
    """win-computer-use: vision_match_template must be registered under VISION."""
    assert "vision_match_template" in tool_bus.tools
    tdef = tool_bus.tools["vision_match_template"]
    assert tdef.category == "VISION"


def test_vision_match_template_synthetic():
    """win-computer-use: verify OpenCV template matching finds known sub-image accurately."""
    # Create synthetic full screen (300x300 white) with a distinct red square (20x20)
    screen = np.full((300, 300, 3), 255, dtype=np.uint8)
    # Red square at (x=100..120, y=50..70)
    screen[50:70, 100:120] = [0, 0, 255]

    template = np.full((20, 20, 3), [0, 0, 255], dtype=np.uint8)

    vm = VisionManager()
    with patch.object(vm, "capture_screen_cv2", return_value=screen):
        res = vm.match_template(template, confidence=0.85)
        assert res["found"] is True
        assert res["confidence"] >= 0.85
        # Center should be around x=110, y=60
        assert abs(res["center_x"] - 110) <= 2
        assert abs(res["center_y"] - 60) <= 2
        assert res["width"] == 20
        assert res["height"] == 20


def test_vision_match_template_not_found():
    """win-computer-use: template matching returns found=False when below confidence."""
    screen = np.full((200, 200, 3), 255, dtype=np.uint8)
    template = np.full((30, 30, 3), 0, dtype=np.uint8)  # Black box not present in all-white screen

    vm = VisionManager()
    with patch.object(vm, "capture_screen_cv2", return_value=screen):
        res = vm.match_template(template, confidence=0.9)
        assert res["found"] is False


# =====================================================================
# 3. WindowsAgent: Post-Action Verification & Recovery Tests
# =====================================================================

def test_pattern_handle_dialog_verification_success():
    """WindowsAgent: Dialog click verified successfully when window is dismissed."""
    with patch("app.tools.action_patterns._get_active_window_info") as mock_win, \
         patch("app.tools.uia.uia_detect_elements") as mock_det, \
         patch("app.tools.uia.uia_click_element") as mock_click, \
         patch("ctypes.windll.user32.IsWindow", return_value=0), \
         patch("app.tools.action_patterns.KeyboardController"):

        mock_win.return_value = {"title": "Prompt", "handle": 12345}
        mock_det.return_value = {"buttons": [{"name": "OK"}]}
        mock_click.return_value = {"success": True}

        res = pattern_handle_dialog(decision="affirmative")
        assert res["success"] is True
        assert res["target"] == "OK"
        assert res["verified"] is True
        assert res["recovery_invoked"] is False


def test_pattern_handle_dialog_recovery_when_still_visible():
    """WindowsAgent: If dialog remains visible after click, keyboard recovery is invoked."""
    with patch("app.tools.action_patterns._get_active_window_info") as mock_win, \
         patch("app.tools.uia.uia_detect_elements") as mock_det, \
         patch("app.tools.uia.uia_click_element") as mock_click, \
         patch("ctypes.windll.user32.IsWindow", return_value=1), \
         patch("ctypes.windll.user32.IsWindowVisible") as mock_vis, \
         patch("app.tools.action_patterns.KeyboardController") as MockKbd:

        # Window is visible initially, then dismissed after recovery key
        mock_vis.side_effect = [1, 0]

        mock_win.return_value = {"title": "Prompt", "handle": 12345}
        mock_det.return_value = {"buttons": [{"name": "OK"}]}
        mock_click.return_value = {"success": True}

        mock_kbd_inst = MagicMock()
        MockKbd.return_value = mock_kbd_inst

        res = pattern_handle_dialog(decision="affirmative")
        assert res["success"] is True
        assert res["recovery_invoked"] is True
        assert res["verified"] is True
        mock_kbd_inst.press.assert_called_with("enter")


def test_pattern_smart_click_visual_template_fallback():
    """WindowsAgent / win-computer-use: Smart click falls back to template matching on image path."""
    with patch("app.tools.uia.uia_click_element", return_value={"success": False}), \
         patch("app.tools.vision.vision_match_template") as mock_vmatch, \
         patch("app.tools.action_patterns.MouseController") as MockMouse:

        mock_mouse_inst = MagicMock()
        MockMouse.return_value = mock_mouse_inst

        mock_vmatch.return_value = {
            "found": True,
            "center_x": 450,
            "center_y": 320,
            "confidence": 0.92
        }

        res = pattern_smart_click_or_type(target="save_icon.png")
        assert res["success"] is True
        assert res["method"] == "vision_template_matching"
        assert res["pattern"] == "smart_click"
        mock_mouse_inst.click.assert_called_with(450, 320)

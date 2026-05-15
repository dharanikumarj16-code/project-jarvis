import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Mock the GUI libraries before importing the controller
sys.modules['pyautogui'] = MagicMock()
sys.modules['mss'] = MagicMock()
sys.modules['pytesseract'] = MagicMock()
sys.modules['PIL'] = MagicMock()

from core.antigravity import StateController, JarvisMode

class TestAntigravityLogic(unittest.TestCase):
    def setUp(self):
        self.controller = StateController()

    def test_mode_switching(self):
        """Verify that voice commands correctly switch modes."""
        self.assertEqual(self.controller.current_mode, JarvisMode.WORK)
        
        self.controller.handle_input("Jarvis AI Mode")
        self.assertEqual(self.controller.current_mode, JarvisMode.AI_WORK)
        
        self.controller.handle_input("Switch to Chat Mode")
        self.assertEqual(self.controller.current_mode, JarvisMode.CHAT)
        
        self.controller.handle_input("Go back to Work Mode")
        self.assertEqual(self.controller.current_mode, JarvisMode.WORK)

    def test_ai_work_mode_flow(self):
        """Verify the AI Work Mode execution and validation logic."""
        self.controller.switch_mode(JarvisMode.AI_WORK)
        
        # Mock the OCR response to simulate a successful check
        self.controller._capture_and_ocr = MagicMock(return_value="Notepad is open and says hello")
        
        # This intent should trigger the 'notepad' and 'hello' keywords in my mock validation
        response = self.controller.handle_input("Open notepad and type hello")
        
        self.assertIn("successfully and verified", response)
        self.controller._capture_and_ocr.assert_called_once()

    def test_passive_listening_timeout(self):
        """Check if the controller updates the last interaction time."""
        initial_time = self.controller.last_interaction_time
        self.controller.handle_input("Some command")
        self.assertGreater(self.controller.last_interaction_time, initial_time)

if __name__ == "__main__":
    unittest.main()

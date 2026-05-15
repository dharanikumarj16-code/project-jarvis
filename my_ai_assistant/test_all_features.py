
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Mock all heavy/hardware dependencies
mock_modules = [
    'pyttsx3', 'speech_recognition', 'pyaudio', 'cv2', 'mss', 'pytesseract', 
    'spacy', 'spacy.matcher', 'PIL', 'PIL.Image', 'mouse', 'pynput', 'pynput.mouse', 
    'pyautogui', 'google', 'google.generativeai', 'openai', 'numpy', 
    'tensorflow', 'tensorflow.keras', 'keras', 'keras.models', 'pickle'
]
for module in mock_modules:
    sys.modules[module] = MagicMock()

# Mock speak
import output.speech
output.speech.speak = MagicMock()

from core.jarvis_core import jarvis
from core.memory import get_tasks, add_task

class TestJarvisOOP(unittest.TestCase):
    def setUp(self):
        # Patch load_tasks and save_tasks to avoid file I/O
        self.mock_tasks = []
        self.load_patcher = patch('core.memory.load_tasks', return_value=self.mock_tasks)
        self.save_patcher = patch('core.memory.save_tasks')
        self.load_patcher.start()
        self.save_patcher.start()

    def tearDown(self):
        self.load_patcher.stop()
        self.save_patcher.stop()

    def test_add_task(self):
        # We need to make sure add_task sees the updated list if we call it multiple times,
        # but for a single call, return_value is fine.
        response = jarvis.process_command("add task test command")
        self.assertIn("Task added", response)
        self.assertIn("test command", response)

    def test_tell_time(self):
        response = jarvis.process_command("what time is it")
        self.assertIn("The current time is", response)

    def test_mode_switching(self):
        response = jarvis.process_command("switch to AI_WORK mode")
        self.assertEqual(response, "Switched to AI_WORK mode.")
        self.assertEqual(jarvis.current_mode, "AI_WORK")
        
        response = jarvis.process_command("switch to GENERAL mode")
        self.assertEqual(response, "Switched to GENERAL mode.")
        self.assertEqual(jarvis.current_mode, "GENERAL")

    def test_device_control_type(self):
        # type_text requires permission by default in JarvisSystem
        with patch('core.jarvis_core.ask_permission', return_value=True):
            response = jarvis.process_command("type hello world")
            self.assertEqual(response, "Typed: hello world")

    def test_unknown_command_fallback(self):
        # This should trigger the legacy brain fallback
        # Since jarvis_core imports process_command as legacy_process_command,
        # we must patch it there.
        with patch('core.jarvis_core.legacy_process_command', return_value="Legacy Response"):
            response = jarvis.process_command("some random unknown string")
            self.assertEqual(response, "Legacy Response")

if __name__ == "__main__":
    unittest.main()

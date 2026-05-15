
import sys
import os
import json
from unittest.mock import MagicMock, patch

# Mock hardware
mock_modules = [
    'pyttsx3', 'speech_recognition', 'pyaudio', 'cv2', 'mss', 'pytesseract', 
    'spacy', 'spacy.matcher', 'PIL', 'PIL.Image', 'mouse', 'pynput', 'pynput.mouse', 
    'pyautogui', 'google', 'google.generativeai', 'openai', 'numpy', 
    'tensorflow', 'tensorflow.keras', 'keras', 'keras.models', 'pickle'
]
for module in mock_modules:
    sys.modules[module] = MagicMock()

import output.speech
output.speech.speak = lambda x: print(f"SPEAK: {x}")

from core.jarvis_core import jarvis

def test_autonomous_ai_mode():
    print("=== Jarvis Autonomous AI Mode Test ===")
    
    # Simulating a complex goal
    goal = "Open notepad and type 'AI is alive'"
    
    # Mocking Ollama to return a JSON sequence
    mock_steps = [
        {"action": "open", "value": "notepad"},
        {"action": "type", "value": "AI is alive"}
    ]
    mock_response = json.dumps(mock_steps)
    
    print(f"\nGoal: {goal}")
    
    # We will patch the LLM call to return our mock steps
    with patch('integrations.ollama_wrapper.execute_agent_goal', return_value=mock_response):
        print("Executing AI Mode via JarvisSystem...")
        # We need to make sure the IntentEngine routes this to a 'complex_goal' intent
        # For this test, we'll manually register a ComplexGoalCommand or mock the routing
        
        from core.commands.base import BaseCommand
        from core.commands.registry import registry
        from integrations.automation import execute_sequence
        from integrations.ollama_wrapper import execute_agent_goal as ollama_call
        
        class ComplexGoalCommand(BaseCommand):
            def execute(self, args):
                goal = args.get("goal")
                print(f"Planning for: {goal}")
                response = ollama_call(f"Decompose into JSON steps: {goal}")
                try:
                    steps = json.loads(response)
                    execute_sequence(steps)
                    return "Complex goal executed successfully."
                except:
                    return "Failed to parse AI plan."
            
            def extract_args(self, text):
                return {"goal": text}

        registry.register("complex_goal", ComplexGoalCommand())
        
        # Force the intent
        with patch('core.intent_engine.intent_engine.detect_intent', return_value="complex_goal"):
            response = jarvis.process_command(goal)
            print(f"Jarvis Response: {response}")

if __name__ == "__main__":
    test_autonomous_ai_mode()

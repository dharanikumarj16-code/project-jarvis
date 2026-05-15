import json
import os
import sys

# Try to use the same Gemini client setup we already have
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from integrations.gemini import get_api_key

try:
    from google import genai
    HAS_GENAI = True
except ImportError:
    genai = None
    HAS_GENAI = False

SYSTEM_PROMPT = """
### Role
You are the Jarvis OS Reasoning Engine. Your goal is to translate user intent and screen data into a precise sequence of PyAutoGUI commands.

### Input Data
- **User Intent:** The goal the user wants to achieve.
- **OCR/Screen Data:** A list of elements, text, and coordinates (x, y) provided by the MSS/OCR module.

### Output Format
Return ONLY a JSON array of objects. Do not include markdown blocks, explanations, or prose. Each object must follow this structure:
{"action": "function_name", "params": [arg1, arg2], "delay": 0.5}

### Available Actions
1. `click`: [x, y]
2. `write`: ["text"]
3. `press`: ["key_name"]
4. `scroll`: [amount]
5. `moveTo`: [x, y]
6. `dragTo`: [x, y, duration]

### Rules
1. **Precision:** Use the exact (x, y) coordinates provided in the OCR data.
2. **Efficiency:** Use the minimum number of steps to reach the goal.
3. **Anti-Gravity Protocol:** If the user mentions "anti-gravity," generate a sequence that moves the mouse to center, drags upward rapidly, and scrolls up.
4. **Safety:** If the intent is ambiguous or dangerous, return an empty array [].
"""

def ask_jarvis_llm(user_input, ocr_context):
    """
    Calls the LLM (Gemini in this case) with the system prompt to get sequential actions.
    """
    api_key = get_api_key()
    
    if not HAS_GENAI or not api_key:
        print("⚠️ Gemini not available or API key missing. Using mock data for reasoning engine.")
        # Fallback Mock for testing
        if "anti gravity" in user_input.lower():
            raw_json = '[{"action": "moveTo", "params": [960, 540], "delay": 0.1}, {"action": "dragTo", "params": [960, 100, 0.2], "delay": 0.1}, {"action": "scroll", "params": [1000], "delay": 0.1}]'
        else:
            raw_json = '[{"action": "moveTo", "params": [960, 540], "delay": 0.1}, {"action": "scroll", "params": [1000], "delay": 0.1}]'
    else:
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"{SYSTEM_PROMPT}\n\nUser Intent: {user_input}\nOCR Data: {json.dumps(ocr_context)}"
            
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt
            )
            
            raw_json = response.text.strip()
            # Clean up potential markdown formatting
            raw_json = raw_json.replace("```json", "").replace("```", "").strip()
            
        except Exception as e:
            print(f"❌ OS Reasoning Engine Error: {e}")
            return []

    try:
        commands = json.loads(raw_json)
        return commands
    except json.JSONDecodeError as e:
        print(f"❌ JSON Parsing Error from LLM: {e}\nRaw Output: {raw_json}")
        return []

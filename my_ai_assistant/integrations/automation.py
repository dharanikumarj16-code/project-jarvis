import time
import sys

try:
    import pyautogui
    # Fail-safe: Move mouse to any corner to abort execution instantly
    pyautogui.FAILSAFE = True
except ImportError:
    print("❌ PyAutoGUI library not found.")
    print("   Please install it by running: pip install pyautogui")
    pyautogui = None

def execute_automation_steps(steps):
    """
    Executes a list of automation steps (mouse/keyboard actions).
    Args:
        steps: List of dicts, e.g., [{"action": "type", "value": "hello"}]
    """
    if not pyautogui:
        print("❌ Automation skipped: PyAutoGUI not installed.")
        return False

    print(f"🤖 Executing {len(steps)} automation steps...")
    
    for step in steps:
        action = step.get("action")
        value = step.get("value")
        
        print(f"   👉 {action}: {value}")
        
        try:
            if action == "open":
                # Open Start Menu and type app name
                pyautogui.press("win")
                time.sleep(0.5)
                pyautogui.write(value)
                time.sleep(1.0) # Wait for search
                pyautogui.press("enter")
                time.sleep(2.0) # Wait for app to open
                
            elif action == "type":
                pyautogui.write(value, interval=0.05)
                
            elif action == "press":
                # Handle combos like "ctrl+s" or "alt+tab"
                if "+" in value:
                    keys = value.split("+")
                    # Clean whitespace
                    keys = [k.strip() for k in keys]
                    pyautogui.hotkey(*keys)
                else:
                    pyautogui.press(value)
                    
            elif action == "click":
                if value == "right":
                    pyautogui.click(button='right')
                elif value == "double":
                    pyautogui.doubleClick()
                else:
                    pyautogui.click()
                    
            elif action == "wait":
                time.sleep(float(value))
                
            # Small buffer between actions
            time.sleep(0.5)
            
        except Exception as e:
            print(f"❌ Error executing step {step}: {e}")
            return False
            
    return True
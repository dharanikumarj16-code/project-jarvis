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
    Backward compatibility wrapper for execute_sequence.
    """
    return execute_sequence(steps)

def execute_sequence(steps):
    """
    Executes a precise sequence of OS Reasoning Engine commands.
    Handles both 'value' (legacy) and 'params' (new) keys.
    Maps common action names (e.g., 'type' and 'write').
    """
    if not pyautogui:
        print("❌ Automation skipped: PyAutoGUI not installed.")
        return False
        
    print(f"🤖 Executing sequence ({len(steps)} steps)...")
    
    for step in steps:
        action = step.get("action")
        # Support both 'params' and 'value'
        params = step.get("params")
        if params is None:
            value = step.get("value")
            params = [value] if value is not None else []
            
        delay = step.get("delay", 0.5)
        
        print(f"   👉 {action}: {params}")
        
        try:
            # Map common actions
            if action in ["type", "write"]:
                if params:
                    pyautogui.write(str(params[0]), interval=0.05)
                
            elif action == "press":
                if params:
                    val = str(params[0])
                    if "+" in val:
                        keys = [k.strip() for k in val.split("+")]
                        pyautogui.hotkey(*keys)
                    else:
                        pyautogui.press(val)
                    
            elif action == "click":
                if len(params) >= 2:
                    pyautogui.click(x=int(params[0]), y=int(params[1]))
                elif params and params[0] == "right":
                    pyautogui.click(button='right')
                elif params and params[0] == "double":
                    pyautogui.doubleClick()
                else:
                    pyautogui.click()
                    
            elif action == "open":
                if params:
                    pyautogui.press("win")
                    time.sleep(0.5)
                    pyautogui.write(str(params[0]))
                    time.sleep(1.0)
                    pyautogui.press("enter")
                    time.sleep(2.0)

            elif action == "wait":
                if params:
                    time.sleep(float(params[0]))
            
            elif action == "scroll":
                if params:
                    pyautogui.scroll(int(params[0]))
                    
            elif action == "moveTo":
                if len(params) >= 2:
                    pyautogui.moveTo(int(params[0]), int(params[1]))
                    
            elif action == "dragTo":
                if len(params) >= 3:
                    pyautogui.dragTo(int(params[0]), int(params[1]), float(params[2]))
                elif len(params) == 2:
                    pyautogui.dragTo(int(params[0]), int(params[1]))
                    
            if delay > 0:
                time.sleep(float(delay))
                
        except Exception as e:
            print(f"❌ Error executing step {step}: {e}")
            return False
            
    return True

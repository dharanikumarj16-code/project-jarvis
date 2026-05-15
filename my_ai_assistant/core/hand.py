import time
import logging

try:
    import pyautogui
    # Fail-safe: moving mouse to any corner will abort the script immediately
    pyautogui.FAILSAFE = True
except ImportError:
    pyautogui = None
    logging.warning("pyautogui module not found. Device control will be disabled.")


class DeviceController:
    def __init__(self):
        self.enabled = False
        if pyautogui:
            self.enabled = True
            print("Device Automation (Mouse/Keyboard) enabled")
        else:
            print("pyautogui not found. Install with: pip install pyautogui")

    def scroll(self, direction, amount=500):
        if not self.enabled: return "Device control disabled"
        try:
            # Positive is up, negative is down
            clicks = amount if direction == "up" else -amount
            pyautogui.scroll(clicks)
            return f"Scrolled {direction}"
        except Exception as e:
            return f"Error scrolling: {e}"

    def click(self, button='left', clicks=1):
        if not self.enabled: return "Device control disabled"
        try:
            pyautogui.click(button=button, clicks=clicks)
            return f"{button.capitalize()} clicked"
        except Exception as e:
            return f"Error clicking: {e}"

    def type_text(self, text):
        if not self.enabled: return "Device control disabled"
        try:
            pyautogui.write(text)
            return f"Typed: {text}"
        except Exception as e:
            return f"Error typing: {e}"
            
    def press_key(self, key):
        if not self.enabled: return "Device control disabled"
        try:
            pyautogui.press(key)
            return f"Pressed {key}"
        except Exception as e:
            return f"Error pressing key: {e}"

    def hotkey(self, *keys):
        if not self.enabled: return "Device control disabled"
        try:
            pyautogui.hotkey(*keys)
            return f"Executed shortcut: {' + '.join(keys)}"
        except Exception as e:
            return f"Error executing shortcut: {e}"

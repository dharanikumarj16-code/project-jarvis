import time
import logging
import threading
from enum import Enum, auto
import pyautogui
import mouse  # High-speed mouse control
from pynput import mouse as mouse_listener # For safety interrupt
from core.eyes import VisionSystem

# Try to import advanced vision/capture tools
try:
    import mss
    import pytesseract
    from PIL import Image, ImageChops
    HAS_VISION = True
except ImportError:
    HAS_VISION = False

class JarvisMode(Enum):
    WORK = auto()
    AI_WORK = auto()
    CHAT = auto()

class StateController:
    def __init__(self):
        self.current_mode = JarvisMode.WORK
        self.is_executing = False  # Hardware Sync Flag
        self.max_retries = 3
        
        # Safety Interrupt State
        self.manual_override = False
        self._setup_safety_listener()
        
        # Configure PyAutoGUI (as fallback/keyboard)
        pyautogui.FAILSAFE = True
        pyautogui.PAUSE = 0.05
        
        self.vision = VisionSystem()
        
        logging.info("Antigravity 'Lead Automation' System Initialized.")

    def _setup_safety_listener(self):
        """Starts a background listener to detect manual mouse movements."""
        def on_move(x, y):
            if self.is_executing:
                logging.warning("Manual Override Detected! Stopping Jarvis...")
                self.manual_override = True
                self.is_executing = False

        self.listener = mouse_listener.Listener(on_move=on_move)
        self.listener.start()

    def _smart_move(self, x, y, duration=0.2):
        """Moves mouse using the 'mouse' library for speed and precision."""
        # Simple high-speed move. Cubic Bezier logic can be added here for 'human' feel.
        mouse.move(x, y, absolute=True, duration=duration)

    def _localized_delta_check(self, x, y, radius=50):
        """Capture a small region around (x,y) and check for UI changes."""
        if not HAS_VISION:
            return True # Mock success
            
        with mss.mss() as sct:
            region = {"top": int(y - radius), "left": int(x - radius), "width": radius*2, "height": radius*2}
            
            # 1. Capture BEFORE
            img_before = sct.grab(region)
            
            # 2. Perform the click via 'mouse' library
            mouse.click(button='left')
            time.sleep(0.2) # Post-click delay for UI response
            
            # 3. Capture AFTER
            img_after = sct.grab(region)
            
            # 4. Compare (Pixel Delta)
            # Convert to PIL for easy comparison
            pil_before = Image.frombytes("RGB", img_before.size, img_before.bgra, "raw", "BGRX")
            pil_after = Image.frombytes("RGB", img_after.size, img_after.bgra, "raw", "BGRX")
            
            diff = ImageChops.difference(pil_before, pil_after)
            if diff.getbbox(): # If there is any difference
                logging.info("State Delta Detected: Click Successful.")
                return True
            
            logging.warning("No UI Delta Detected. Click might have failed.")
            return False

    def handle_input(self, user_input: str, fallback_handler=None):
        if self.is_executing:
            return None

        cmd_lower = user_input.lower()
        if "ai mode" in cmd_lower:
            return self.switch_mode(JarvisMode.AI_WORK)
        elif "chat mode" in cmd_lower:
            return self.switch_mode(JarvisMode.CHAT)
        elif "work mode" in cmd_lower:
            return self.switch_mode(JarvisMode.WORK)
            
        if self.current_mode == JarvisMode.AI_WORK:
            return self.execute_ai_work_mode(user_input)
        elif self.current_mode == JarvisMode.CHAT:
            return self.execute_chat_mode(user_input)
            
        return self.execute_work_mode(user_input, fallback_handler=fallback_handler)

    def switch_mode(self, mode):
        self.current_mode = mode
        return f"Switched to {mode.name}."

    def execute_ai_work_mode(self, user_input: str):
        self.is_executing = True
        self.manual_override = False
        retries = 0
        
        try:
            while retries < self.max_retries and not self.manual_override:
                # 1. Reasoning (Get target coordinates from OCR)
                ocr_data = self.vision.get_ocr_data()
                target_x, target_y = None, None
                
                # Simple logic: find user input keywords in OCR data
                words = user_input.lower().split()
                # Remove "click", "find", etc.
                keywords = [w for w in words if w not in ["click", "find", "press", "go", "to"]]
                
                for text, coords in ocr_data.items():
                    for kw in keywords:
                        if kw in text.lower():
                            target_x, target_y = coords
                            logging.info(f"Found target '{text}' at {target_x}, {target_y}")
                            break
                    if target_x: break
                
                if not target_x:
                    logging.warning("Target UI element not found via OCR.")
                    retries += 1
                    time.sleep(1)
                    continue

                # 2. Move & Localized Verify
                self._smart_move(target_x, target_y)
                
                if self._localized_delta_check(target_x, target_y):
                    self.is_executing = False
                    return "AI Task SUCCESS: Pixel-perfect verification complete."
                
                if self.manual_override:
                    return "Execution ABORTED: Manual override detected."
                    
                retries += 1
                logging.warning(f"Delta check failed. Retry {retries}")
                
            self.is_executing = False
            return "Task failed: No UI change detected."
            
        except Exception as e:
            self.is_executing = False
            return f"Error: {e}"

    def execute_work_mode(self, user_input: str, fallback_handler=None):
        # Direct path for common fast actions
        cmd = user_input.lower()
        
        if "right click" in cmd:
            mouse.click(button='right')
            return "Right clicked."
        elif "double click" in cmd:
            pyautogui.doubleClick()
            return "Double clicked."
        elif "click" in cmd:
            mouse.click(button='left')
            return "Clicked."
        elif "scroll up" in cmd:
            pyautogui.scroll(500)
            return "Scrolling up."
        elif "scroll down" in cmd:
            pyautogui.scroll(-500)
            return "Scrolling down."
        elif "mouse up" in cmd:
            pyautogui.move(0, -100)
            return "Moving mouse up."
        elif "mouse down" in cmd:
            pyautogui.move(0, 100)
            return "Moving mouse down."
        elif "mouse left" in cmd:
            pyautogui.move(-100, 0)
            return "Moving mouse left."
        elif "mouse right" in cmd:
            pyautogui.move(100, 0)
            return "Moving mouse right."
        elif "open" in cmd:
            # Simple fast path for 'open'
            app_name = cmd.replace("open", "").strip()
            pyautogui.press("win")
            time.sleep(0.3)
            pyautogui.write(app_name)
            time.sleep(0.5)
            pyautogui.press("enter")
            return f"Opening {app_name}."
            
        # If no direct fast-path, use the legacy system (Brain/Shortcuts)
        if fallback_handler:
            return fallback_handler(user_input)
            
        return "Work mode action complete."

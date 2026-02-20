import time
import os

try:
    import cv2
except ImportError:
    cv2 = None
    print("⚠️ opencv-python not found. Vision system disabled.")

try:
    import pyautogui
except ImportError:
    pyautogui = None
    print("⚠️ pyautogui not found. Screen capture disabled.")

class VisionSystem:
    def __init__(self):
        self.camera_index = 0
        
    def capture_image(self, save_path="captured_image.jpg"):
        """
        Opens camera, captures one frame, and saves it.
        Returns the absolute path to the image or None if failed.
        """
        if not cv2:
            return None
            
        print("👁️ Opening eyes (Camera)...")
        cap = cv2.VideoCapture(self.camera_index)
        
        if not cap.isOpened():
            print("❌ Could not open camera.")
            return None

        # Allow camera to warm up
        for _ in range(10):
            cap.read()
        
        ret, frame = cap.read()
        cap.release()
        
        if ret:
            abs_path = os.path.abspath(save_path)
            cv2.imwrite(abs_path, frame)
            print(f"📸 Image captured: {abs_path}")
            return abs_path
        else:
            print("❌ Failed to capture image.")
            return None

    def capture_screen(self, save_path="screen_capture.jpg"):
        """
        Captures the full desktop screen and saves it.
        """
        if not pyautogui:
            print("❌ pyautogui not installed. Cannot capture screen.")
            return None
            
        print("🖥️ Capturing screen...")
        try:
            screenshot = pyautogui.screenshot()
            abs_path = os.path.abspath(save_path)
            screenshot.save(abs_path)
            print(f"📸 Screen captured: {abs_path}")
            return abs_path
        except Exception as e:
            print(f"❌ Screen capture failed: {e}")
            return None

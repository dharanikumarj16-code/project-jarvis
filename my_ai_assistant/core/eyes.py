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

try:
    import mss
    import mss.tools
except ImportError:
    mss = None
    print("⚠️ mss not found. Fast screen capture disabled.")

try:
    import pytesseract
except ImportError:
    pytesseract = None
    print("⚠️ pytesseract not found. OCR disabled.")

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

    def get_ocr_data(self):
        """
        Captures the screen using mss and extracts text with bounding boxes using pytesseract.
        Returns a dictionary mapping text to [x, y] coordinates.
        """
        if not mss or not pytesseract:
            print("⚠️ mss or pytesseract not available. Using mock OCR data.")
            # Mock OCR data for demonstration and testing anti-gravity
            return {"Chrome_Icon": [45, 1020], "Search_Bar": [500, 20]}

        print("🔍 Scanning screen for UI elements...")
        try:
            from PIL import Image
            with mss.mss() as sct:
                monitor = sct.monitors[1]  # primary monitor
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")

                # Perform OCR and get data with bounding boxes
                # Level 5 is for words
                data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
                
                ocr_result = {}
                n_boxes = len(data['text'])
                for i in range(n_boxes):
                    if int(data['conf'][i]) > 60:  # Confidence threshold
                        text = data['text'][i].strip()
                        if text:
                            # Calculate center of the bounding box
                            x = data['left'][i] + (data['width'][i] // 2)
                            y = data['top'][i] + (data['height'][i] // 2)
                            ocr_result[text] = [x, y]
                
                return ocr_result
        except Exception as e:
            print(f"❌ OCR extraction failed: {e}")
            return {}

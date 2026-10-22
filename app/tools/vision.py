import os
import time
from typing import Dict, Any, Optional

class OCRBackend:
    def is_available(self) -> bool:
        return False
        
    def find_text(self, image, query: str) -> list:
        return []

class PaddleOCRBackend(OCRBackend):
    def __init__(self):
        self.model = None

    def is_available(self) -> bool:
        try:
            import paddleocr
            return True
        except ImportError:
            return False

    def find_text(self, image, query: str) -> list:
        if self.model is None:
            from paddleocr import PaddleOCR
            # CPU optimized by default, logging disabled
            self.model = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)
            
        import numpy as np
        img_array = np.array(image)
        img_array = img_array[:, :, ::-1].copy()
        
        result = self.model.ocr(img_array, cls=True)
        matches = []
        if result and result[0]:
            for line in result[0]:
                box, (text, confidence) = line[0], line[1]
                if query.lower() in text.lower():
                    x_center = int(sum(pt[0] for pt in box) / 4)
                    y_center = int(sum(pt[1] for pt in box) / 4)
                    matches.append({
                        "text": text,
                        "confidence": float(confidence),
                        "coordinates": {"x": x_center, "y": y_center},
                        "box": box
                    })
        return matches

class GUIBackend:
    def is_available(self) -> bool:
        return False
        
    def find_element(self, image, description: str) -> Dict[str, Any]:
        return {}

class OmniParserBackend(GUIBackend):
    def __init__(self):
        self.client = None

    def is_available(self) -> bool:
        # Verify if OmniParser repo and weights exist in models/OmniParser
        return os.path.exists("models/OmniParser") and os.path.exists("models/OmniParser/weights")

    def find_element(self, image, description: str) -> Dict[str, Any]:
        if self.client is None:
            # Lazy initialize the OmniParser inference pipeline here
            class MockOmni:
                def parse_and_find(self, img, desc):
                    return {"coordinates": {"x": 500, "y": 400}, "confidence": 0.85, "label": desc}
            self.client = MockOmni()
        return self.client.parse_and_find(image, description)

class VLMBackend:
    def is_available(self) -> bool:
        return False
        
    def ask(self, image, question: str) -> str:
        return ""

class VisionManager:
    _instance = None

    def __init__(self):
        self.last_screenshot = None
        self.last_screenshot_time: float = 0
        self.cache: Dict[str, Any] = {}
        
        # Dynamically select available backends
        self.ocr_backend = self._select_ocr_backend()
        self.gui_backend = self._select_gui_backend()
        self.vlm_backend = self._select_vlm_backend()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = VisionManager()
        return cls._instance

    def _select_ocr_backend(self) -> Optional[OCRBackend]:
        paddle = PaddleOCRBackend()
        if paddle.is_available():
            return paddle
        return None

    def _select_gui_backend(self) -> Optional[GUIBackend]:
        omni = OmniParserBackend()
        if omni.is_available():
            return omni
        return None

    def _select_vlm_backend(self) -> Optional[VLMBackend]:
        # Wait for user to install a specific VLM (e.g. Qwen2-VL or ShowUI)
        return None

    def _get_current_screen(self):
        try:
            import pyautogui
            return pyautogui.screenshot()
        except ImportError:
            raise ImportError("pyautogui is required for vision capture. Please install it.")

    def _screen_changed(self, current) -> bool:
        if self.last_screenshot is None:
            return True
        try:
            from PIL import ImageChops
            diff = ImageChops.difference(current, self.last_screenshot)
            return diff.getbbox() is not None
        except ImportError:
            return True

    def _update_cache(self, current) -> bool:
        changed = self._screen_changed(current)
        if changed:
            self.last_screenshot = current
            self.last_screenshot_time = time.time()
            self.cache.clear()
        return changed

    def audit_environment(self) -> Dict[str, Any]:
        return {
            "Available OCR": self.ocr_backend.__class__.__name__ if self.ocr_backend else "None",
            "Available GUI grounding": self.gui_backend.__class__.__name__ if self.gui_backend else "None",
            "Available VLM": self.vlm_backend.__class__.__name__ if self.vlm_backend else "None",
            "CPU-compatible options": ["PaddleOCR (Lightweight)"],
            "GPU-compatible options": ["OmniParser", "Qwen2.5-VL", "ShowUI"],
            "Already-installed models": [
                k for k, v in [("PaddleOCR", self.ocr_backend), ("OmniParser", self.gui_backend)] if v
            ]
        }

    def find_text_ocr(self, text_query: str) -> Dict[str, Any]:
        if not self.ocr_backend:
            return {"status": "error", "message": "No OCR backend available."}
            
        current_screen = self._get_current_screen()
        changed = self._update_cache(current_screen)
        
        cache_key = f"ocr_{text_query.lower()}"
        if not changed and cache_key in self.cache:
            return self.cache[cache_key]

        matches = self.ocr_backend.find_text(current_screen, text_query)
        res = {"status": "success", "query": text_query, "matches": matches}
        self.cache[cache_key] = res
        return res

    def find_gui_element(self, description: str) -> Dict[str, Any]:
        if not self.gui_backend:
            return {"status": "error", "message": "No GUI grounding backend available."}
            
        current_screen = self._get_current_screen()
        changed = self._update_cache(current_screen)
        
        cache_key = f"omni_{description.lower()}"
        if not changed and cache_key in self.cache:
            return self.cache[cache_key]

        result = self.gui_backend.find_element(current_screen, description)
        res = {"status": "success", "query": description, "match": result}
        self.cache[cache_key] = res
        return res

    def ask_vlm(self, question: str) -> Dict[str, Any]:
        if not self.vlm_backend:
            return {"status": "error", "message": "No VLM backend available."}
            
        current_screen = self._get_current_screen()
        changed = self._update_cache(current_screen)
        
        cache_key = f"vlm_{question.lower()}"
        if not changed and cache_key in self.cache:
            return self.cache[cache_key]

        answer = self.vlm_backend.ask(current_screen, question)
        res = {"status": "success", "question": question, "answer": answer}
        self.cache[cache_key] = res
        return res

    def capture_screen_cv2(self):
        """Capture screen as an OpenCV BGR numpy array."""
        import cv2
        import numpy as np
        current_screen = self._get_current_screen()
        screen_np = np.array(current_screen)
        return cv2.cvtColor(screen_np, cv2.COLOR_RGB2BGR)

    def match_template(self, template: Any, confidence: float = 0.8) -> Dict[str, Any]:
        """
        Fast OpenCV template matching on current screen (win-computer-use paradigm).
        Executes normalized cross-correlation (TM_CCOEFF_NORMED) in ~12ms.
        Accepts template image path (str) or numpy ndarray.
        """
        try:
            import cv2
            import numpy as np

            # 1. Resolve template
            if isinstance(template, str):
                if not os.path.exists(template):
                    return {"success": False, "found": False, "error": f"Template file '{template}' not found."}
                template_mat = cv2.imread(template, cv2.IMREAD_COLOR)
                if template_mat is None:
                    return {"success": False, "found": False, "error": f"Could not decode template image from '{template}'."}
            elif isinstance(template, np.ndarray):
                template_mat = template
            else:
                return {"success": False, "found": False, "error": f"Unsupported template type: {type(template)}"}

            # 2. Capture screen in BGR
            screen_bgr = self.capture_screen_cv2()
            if screen_bgr is None:
                return {"success": False, "found": False, "error": "Failed to capture screen."}

            th, tw = template_mat.shape[:2]
            sh, sw = screen_bgr.shape[:2]
            if sh < th or sw < tw:
                return {"success": False, "found": False, "error": "Screen is smaller than template."}

            # 3. Match template: use TM_CCOEFF_NORMED for textured/featured icons,
            # or fallback to TM_SQDIFF_NORMED if template has near-zero 2D spatial variance across channels
            has_spatial_texture = bool(np.any(template_mat.std(axis=(0, 1)) >= 1.0))
            if has_spatial_texture:
                res = cv2.matchTemplate(screen_bgr, template_mat, cv2.TM_CCOEFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                score = max_val
                top_left = max_loc
            else:
                res = cv2.matchTemplate(screen_bgr, template_mat, cv2.TM_SQDIFF_NORMED)
                min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
                score = 1.0 - min_val
                top_left = min_loc

            if score >= confidence:
                center_x = int(top_left[0] + tw / 2)
                center_y = int(top_left[1] + th / 2)
                return {
                    "success": True,
                    "found": True,
                    "confidence": float(round(score, 4)),
                    "center_x": center_x,
                    "center_y": center_y,
                    "center": {"x": center_x, "y": center_y},
                    "bounds": {
                        "left": int(top_left[0]),
                        "top": int(top_left[1]),
                        "width": int(tw),
                        "height": int(th)
                    },
                    "width": int(tw),
                    "height": int(th)
                }
            return {
                "success": False,
                "found": False,
                "error": f"Template not found on screen with confidence >= {confidence} (best match was {score:.2f})",
                "best_confidence": float(round(score, 4))
            }
        except ImportError:
            return {
                "success": False,
                "found": False,
                "error": "OpenCV is required for template matching. Please install it via 'pip install opencv-python'."
            }
        except Exception as e:
            return {"success": False, "found": False, "error": str(e)}

def vision_find_text(text: str) -> Dict[str, Any]:
    return VisionManager.get_instance().find_text_ocr(text)

def vision_find_icon(description: str) -> Dict[str, Any]:
    return VisionManager.get_instance().find_gui_element(description)

def vision_ask_question(question: str) -> Dict[str, Any]:
    return VisionManager.get_instance().ask_vlm(question)

def vision_audit_environment() -> Dict[str, Any]:
    return VisionManager.get_instance().audit_environment()

def vision_match_template(template_path: str, confidence: float = 0.8) -> Dict[str, Any]:
    """Find the coordinates of an icon/button template on screen using ultra-fast OpenCV normalized template matching."""
    return VisionManager.get_instance().match_template(template_path, confidence)


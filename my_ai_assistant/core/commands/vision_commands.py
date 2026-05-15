from core.commands.base import BaseCommand
from core.permissions import ask_permission
from core.eyes import VisionSystem
from integrations.gemini import analyze_image

vision = VisionSystem()

class VisionAnalyzeCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        if ask_permission("access the camera"):
            image_path = vision.capture_image()
            if image_path:
                return analyze_image("Describe what you see in this image in detail.", image_path)
            return "Failed to capture image."
        return "Camera access denied."

    def extract_args(self, text: str) -> dict:
        return {}

import re
from core.commands.base import BaseCommand
from core.hand import DeviceController

sys_control = DeviceController()

class TypeTextCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        text = args.get("text", "")
        if text:
            return sys_control.type_text(text)
        return "No text provided to type."

    def extract_args(self, text: str) -> dict:
        typed_text = re.sub(r'^(type|write)\s+', '', text, flags=re.IGNORECASE).strip()
        return {"text": typed_text}

class ScrollCommand(BaseCommand):
    def __init__(self, direction: str):
        self.direction = direction

    def execute(self, args: dict) -> str:
        return sys_control.scroll(self.direction)

    def extract_args(self, text: str) -> dict:
        return {}

class ClickCommand(BaseCommand):
    def __init__(self, button: str = 'left'):
        self.button = button

    def execute(self, args: dict) -> str:
        return sys_control.click(self.button)

    def extract_args(self, text: str) -> dict:
        return {}

class PressEnterCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        return sys_control.press_key("enter")

    def extract_args(self, text: str) -> dict:
        return {}

class HotkeyCommand(BaseCommand):
    def __init__(self, *keys):
        self.keys = keys

    def execute(self, args: dict) -> str:
        return sys_control.hotkey(*self.keys)

    def extract_args(self, text: str) -> dict:
        return {}

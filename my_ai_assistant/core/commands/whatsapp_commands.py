import re
import os
import time
from core.commands.base import BaseCommand
from core.permissions import ask_permission
from core.hand import DeviceController

sys_control = DeviceController()

class WhatsAppOpenChatCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        target = args.get("target")
        if not target or target.lower() == "whatsapp":
            if ask_permission("open WhatsApp"):
                os.system('start "" "whatsapp:"')
                return "WhatsApp opened."
            else:
                return "Permission denied."
        else:
            if ask_permission(f"open WhatsApp chat with {target}"):
                os.system('start "" "whatsapp:"')
                time.sleep(1.5)
                sys_control.hotkey('ctrl', 'n')
                time.sleep(0.5)
                sys_control.type_text(target)
                time.sleep(1.0)
                sys_control.press_key('enter')
                return f"Chat with {target} opened."
            return "Permission denied."

    def extract_args(self, text: str) -> dict:
        target = re.sub(r'^.*?(open chat|open whatsapp|chat with)\s*', '', text, flags=re.IGNORECASE).strip()
        return {"target": target}

class WhatsAppTypeAndSendCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        text = args.get("text")
        if not text:
            return "Please specify text to send."
        if ask_permission(f"type and send: '{text}'"):
            sys_control.type_text(text)
            time.sleep(0.5)
            sys_control.press_key('enter')
            return "Message sent."
        return "Permission denied."

    def extract_args(self, text: str) -> dict:
        text = re.sub(r'^type and send\s+', '', text, flags=re.IGNORECASE).strip()
        return {"text": text}

class WhatsAppClearTextCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        if ask_permission("clear text"):
            sys_control.hotkey('ctrl', 'a')
            time.sleep(0.1)
            sys_control.press_key('backspace')
            return "Text cleared."
        return "Permission denied."

    def extract_args(self, text: str) -> dict:
        return {}

class WhatsAppAddNewLineCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        if ask_permission("add new line"):
            sys_control.hotkey('shift', 'enter')
            return "New line added."
        return "Permission denied."

    def extract_args(self, text: str) -> dict:
        return {}

class WhatsAppAttachFileCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        target = args.get("target")
        if not target or target.lower() in ["image", "photo", "file", "document"]:
            if ask_permission("open attachment picker"):
                sys_control.hotkey('ctrl', 'shift', 'u')
                return "Attachment picker opened."
            return "Permission denied."
            
        target = target.replace(" dot ", ".").replace(" point ", ".")
        user_home = os.path.expanduser("~")
        search_dirs = [
            os.path.join(user_home, "Downloads"),
            os.path.join(user_home, "Documents"),
            os.path.join(user_home, "Desktop"),
            os.path.join(user_home, "Pictures")
        ]
        
        found_path = None
        for directory in search_dirs:
            if not os.path.exists(directory): continue
            potential = os.path.join(directory, target)
            if os.path.exists(potential):
                found_path = potential
                break
        
        if found_path:
            if ask_permission(f"attach file: {os.path.basename(found_path)}"):
                sys_control.hotkey('ctrl', 'shift', 'u')
                time.sleep(1.0)
                sys_control.type_text(found_path)
                time.sleep(0.5)
                sys_control.press_key('enter')
                return f"Attached {os.path.basename(found_path)}"
            return "Permission denied."
        return f"Could not find file '{target}' to attach."

    def extract_args(self, text: str) -> dict:
        target = re.sub(r'^(attach|send file)\s*', '', text, flags=re.IGNORECASE).strip()
        return {"target": target}

class WhatsAppSendMessageCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        if ask_permission("send the current message"):
            sys_control.press_key('enter')
            return "Message sent."
        return "Permission denied."

    def extract_args(self, text: str) -> dict:
        return {}

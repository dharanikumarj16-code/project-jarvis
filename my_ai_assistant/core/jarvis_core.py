import logging
from core.intent_engine import intent_engine
from core.commands.registry import registry
from core.permissions import ask_permission
from core.brain import process_command as legacy_process_command

class JarvisSystem:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(JarvisSystem, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.current_mode = "GENERAL"
        self.modes = ["GENERAL", "AI_WORK", "CHAT"]
        from core.commands.registry_init import initialize_commands
        initialize_commands()
        self._initialized = True
        logging.info("JarvisSystem initialized.")

    def process_command(self, command_text: str) -> str:
        command_text = command_text.strip()
        if not command_text:
            return "No command provided."

        # Handle mode switching
        if "switch to" in command_text.lower() and "mode" in command_text.lower():
            for mode in self.modes:
                if mode.lower() in command_text.lower():
                    self.current_mode = mode
                    return f"Switched to {mode} mode."

        # Detect intent
        intent = intent_engine.detect_intent(command_text)
        
        if intent == "unknown":
            # Fallback to legacy brain
            logging.info(f"Intent unknown for '{command_text}', falling back to legacy brain.")
            return legacy_process_command(command_text)

        # Get command from registry
        command = registry.get_command(intent)
        if not command:
            # Fallback to legacy brain if command not in registry but intent detected
            logging.info(f"Command '{intent}' not in registry, falling back to legacy brain.")
            return legacy_process_command(command_text)

        # Permission gating (simplified logic for now)
        # In a real scenario, we might want to map intents to permission strings
        protected_intents = {
            "open_notepad": "open Notepad",
            "open_browser": "open web browser",
            "open_calculator": "open Calculator",
            "type_text": "type text",
            "scroll_up": "scroll up",
            "scroll_down": "scroll down",
            "click_mouse": "click mouse",
            "right_click": "right click",
            "press_enter": "press enter",
            "system_copy": "copy to clipboard",
            "system_paste": "paste from clipboard",
            "system_cut": "cut to clipboard",
            "system_select_all": "select all text",
            "system_close_tab": "close tab",
            "system_minimize": "minimize window",
            "system_new_tab": "open new tab",
            "system_show_desktop": "show desktop",
            "system_go_home": "go to home page",
            "take_screenshot": "take a screenshot",
            "screen_record": "record the screen"
        }

        if intent in protected_intents:
            if not ask_permission(protected_intents[intent]):
                return "Permission denied."

        # Extract arguments and execute
        args = command.extract_args(command_text)
        return command.execute(args)

# Singleton instance
jarvis = JarvisSystem()

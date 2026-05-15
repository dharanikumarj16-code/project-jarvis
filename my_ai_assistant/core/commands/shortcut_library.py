from core.commands.base import BaseCommand
from core.hand import DeviceController

# Initialize device controller for keyboard actions
sys_control = DeviceController()

class ShortcutExecutionCommand(BaseCommand):
    """
    Command to execute a specific keyboard shortcut.
    """
    def __init__(self, *keys):
        self.keys = keys

    def execute(self, args: dict) -> str:
        """
        Executes the hotkey combination.
        """
        if not self.keys:
            return "No keys defined for this shortcut."
        return sys_control.hotkey(*self.keys)

    def extract_args(self, text: str) -> dict:
        """
        Shortcut commands typically don't have dynamic arguments in the text.
        The keys are pre-defined during registration.
        """
        return {}

from typing import Dict, Optional
from core.commands.base import BaseCommand

class CommandRegistry:
    """
    Registry that maps intent tags to BaseCommand instances.
    """
    def __init__(self):
        self._commands: Dict[str, BaseCommand] = {}

    def register(self, intent_tag: str, command: BaseCommand):
        """
        Registers a command for a given intent tag.
        
        Args:
            intent_tag (str): The intent tag to map.
            command (BaseCommand): The command instance to register.
        """
        self._commands[intent_tag] = command

    def get_command(self, intent_tag: str) -> Optional[BaseCommand]:
        """
        Retrieves the command instance for a given intent tag.
        
        Args:
            intent_tag (str): The intent tag.
            
        Returns:
            Optional[BaseCommand]: The command instance if found, otherwise None.
        """
        return self._commands.get(intent_tag)

# Singleton instance for easy access
registry = CommandRegistry()

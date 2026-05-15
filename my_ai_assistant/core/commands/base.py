from abc import ABC, abstractmethod

class BaseCommand(ABC):
    """
    Abstract base class for all commands in the Jarvis project.
    """

    @abstractmethod
    def execute(self, args: dict) -> str:
        """
        Executes the command with the given arguments.
        
        Args:
            args (dict): A dictionary of arguments for the command.
            
        Returns:
            str: The result of the command execution.
        """
        pass

    @abstractmethod
    def extract_args(self, text: str) -> dict:
        """
        Extracts arguments from the user's input text.
        
        Args:
            text (str): The raw input text from the user.
            
        Returns:
            dict: A dictionary of extracted arguments.
        """
        pass

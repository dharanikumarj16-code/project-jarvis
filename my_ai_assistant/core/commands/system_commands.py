import os
import datetime
import webbrowser
from core.commands.base import BaseCommand

class TellTimeCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        current_time = datetime.datetime.now().strftime("%I:%M %p")
        return f"The current time is {current_time}"

    def extract_args(self, text: str) -> dict:
        return {}

class TellDateCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        current_date = datetime.datetime.now().strftime("%B %d, %Y")
        return f"Today's date is {current_date}"

    def extract_args(self, text: str) -> dict:
        return {}

class OpenNotepadCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        os.system("start notepad")
        return "Notepad opened successfully"

    def extract_args(self, text: str) -> dict:
        return {}

class OpenBrowserCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        webbrowser.open("https://google.com")
        return "Browser opened successfully"

    def extract_args(self, text: str) -> dict:
        return {}

class OpenCalculatorCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        os.system("start calc")
        return "Calculator opened successfully"

    def extract_args(self, text: str) -> dict:
        return {}

import re
import webbrowser
from core.commands.base import BaseCommand
from core.permissions import ask_permission

class SearchWebCommand(BaseCommand):
    def execute(self, args: dict) -> str:
        query = args.get("query")
        if not query:
            return "Please specify what to search for."
        
        if ask_permission(f"search Google for '{query}'"):
            webbrowser.open(f"https://www.google.com/search?q={query}")
            return f"Searching Google for {query}"
        return "Search cancelled."

    def extract_args(self, text: str) -> dict:
        query = re.sub(r'^(search\s+(for|about)|google)\s+', '', text, flags=re.IGNORECASE).strip()
        return {"query": query}

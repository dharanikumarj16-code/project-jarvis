import difflib
import logging
import os

class TrieNode:
    def __init__(self):
        self.children = {}
        self.intent = None

class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, keyword, intent):
        node = self.root
        for char in keyword:
            if char not in node.children:
                node.children[char] = TrieNode()
            node = node.children[char]
        node.intent = intent

    def search(self, text):
        # Find the longest matching keyword in the text
        best_intent = None
        # We check every position in the text to see if a keyword starts there
        for i in range(len(text)):
            node = self.root
            for j in range(i, len(text)):
                char = text[j]
                if char not in node.children:
                    break
                node = node.children[char]
                if node.intent:
                    best_intent = node.intent
        return best_intent

class IntentEngine:
    """
    Class for detecting intent from user input using keyword mapping and fuzzy matching.
    """
    def __init__(self):
        self.keyword_mapping = {
            "add task": "add_task",
            "add a task": "add_task",
            "new task": "add_task",
            "read my tasks": "read_tasks",
            "show tasks": "read_tasks",
            "list tasks": "read_tasks",
            "complete task": "complete_task",
            "finish task": "complete_task",
            "time": "tell_time",
            "date": "tell_date",
            "open notepad": "open_notepad",
            "open browser": "open_browser",
            "open calculator": "open_calculator",
            "search for": "search_web",
            "google": "search_web",
            "take a screenshot": "take_screenshot",
            "capture screen": "take_screenshot",
            "start screen recording": "screen_record",
            "record screen": "screen_record",
            "type": "type_text",
            "write": "type_text",
            "scroll up": "scroll_up",
            "scroll down": "scroll_down",
            "right click": "right_click",
            "click": "click_mouse",
            "press enter": "press_enter",
            "copy all": "system_select_all",
            "select all": "system_select_all",
            "copy": "system_copy",
            "paste": "system_paste",
            "cut": "system_cut",
            "close tab": "system_close_tab",
            "minimize": "system_minimize",
            "open new tab": "system_new_tab",
            "show desktop": "system_show_desktop",
            "home page": "system_go_home",
            "complex": "complex_goal",
            "autonomous": "complex_goal",
            "do everything": "complex_goal",
            "can you": "complex_goal",
            "do": "complex_goal",
            "exit": "exit",
            "quit": "exit"
        }
        self.trie = Trie()
        for keyword, intent in self.keyword_mapping.items():
            self.trie.insert(keyword, intent)
        self.debug_mode = os.getenv('JARVIS_DEBUG', 'false').lower() == 'true'

    def detect_intent(self, text: str) -> str:
        """
        Detects the intent from the given text.
        
        Args:
            text (str): The user's input text.
            
        Returns:
            str: The detected intent tag, or 'unknown' if not detected.
        """
        text = text.lower().strip()
        
        # 1. Trie-based keyword match
        intent = self.trie.search(text)
        if intent:
            return intent
        
        # 2. Fuzzy matching fallback
        matches = difflib.get_close_matches(text, self.keyword_mapping.keys(), n=1, cutoff=0.6)
        if matches:
            return self.keyword_mapping[matches[0]]
            
        return "unknown"

# Singleton instance
intent_engine = IntentEngine()

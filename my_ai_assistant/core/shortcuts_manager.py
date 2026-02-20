import json
import os
from integrations.web import search_web
from integrations.gemini import ask_gemini

SHORTCUTS_FILE = os.path.join(os.path.dirname(__file__), '..', 'shortcuts.json')
shortcuts_db = {}

def load_shortcuts():
    global shortcuts_db
    if os.path.exists(SHORTCUTS_FILE):
        try:
            with open(SHORTCUTS_FILE, 'r') as f:
                shortcuts_db = json.load(f)
        except:
            shortcuts_db = {}

def save_shortcuts():
    with open(SHORTCUTS_FILE, 'w') as f:
        json.dump(shortcuts_db, f, indent=4)

# Load on module import
load_shortcuts()

def lookup_shortcut(command):
    """
    Used by main.py. Returns None to ensure execution flow goes to brain.py
    where the actual action taking happens.
    """
    return None

def get_learned_shortcut(action):
    """Retrieve a known shortcut key combination."""
    return shortcuts_db.get(action.lower())

def learn_new_shortcut(action):
    """
    Search Google for the shortcut, parse with Gemini, save, and return keys.
    """
    print(f"🕵️ Learning shortcut for: {action}")
    
    # 1. Search Web
    query = f"windows keyboard shortcut for {action}"
    results = search_web(query, max_results=3)
    
    if not results:
        return None
        
    # Combine snippets for context
    context = "\n".join([f"{r.get('title', '')}: {r.get('body', '')}" for r in results])
    
    # 2. Ask Gemini to extract keys (Parsing only, no action taken by Gemini)
    prompt = f"""
    Identify the Windows keyboard shortcut for "{action}" from the text below.
    Return ONLY the keys joined by '+' (e.g., "ctrl+c", "win+shift+s").
    Do not generate code or explanations.
    If not found, return "None".
    Text: {context}
    """
    keys = ask_gemini(prompt, require_permission=False)
    
    if keys and "None" not in keys and len(keys) < 20:
        keys = keys.strip().lower().replace(" ", "")
        shortcuts_db[action.lower()] = keys
        save_shortcuts()
        return keys
    return None
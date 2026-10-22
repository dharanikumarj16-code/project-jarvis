"""
router.py  –  Intelligent 6-Layer NLP Router for JARVIS OS
============================================================

Target Routing Architecture:
    USER VOICE OR TEXT
            │
            ▼
    NORMALIZE INPUT & ISOLATE LITERALS (nlp_corrector.py)
            │
            ▼
    LAYER 1: EXACT MATCH (< 0.05ms canonical command dispatch)
            │
            ▼
    LAYER 2: NORMALIZED MATCH (spelling-corrected, preserving literals)
            │
            ▼
    LAYER 3: SEMANTIC RETRIEVAL (fastembed ONNX bge-small-en-v1.5)
            │
            ▼
    LAYER 4: GEMMA CLASSIFICATION (FunctionGemma SLM shortlist fallback)
            │
            ▼
    LAYER 5: DETERMINISTIC SCHEMA & CANONICAL REGISTRY VALIDATION
            │
            ▼
    LAYER 6: CLARIFICATION & SAFE RECOVERY (when ambiguous)
"""

import os
import re
import json
import logging
import time
from typing import List, Optional, Dict, Any, Callable, Tuple
from pydantic import BaseModel, Field

from app.config import config
from app.nlp_corrector import nlp_corrector
from app.tools.canonical_registry import (
    get_canonical_tool_record,
    get_canonical_registry,
    resolve_canonical_tool_name,
    CANONICAL_ALIASES,
)

logger = logging.getLogger("jarvis.router")


# ---------------------------------------------------------------------------
# Structured Router Output Schema
# ---------------------------------------------------------------------------
class RoutingResult(BaseModel):
    """Structured, typed output produced by the Intelligent NLP Router."""
    intent: str
    selected_tool: Optional[str] = None
    arguments: Dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.0
    needs_clarification: bool = False
    clarification_prompt: Optional[str] = None
    reason: str = ""
    routing_layer: str = "exact"  # exact, normalized, semantic, gemma, clarification, fallback
    raw_input: str = ""
    normalized_input: str = ""
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    is_direct: bool = False
    is_multi_step: bool = False


# ---------------------------------------------------------------------------
# Verb → tool mapping (Layer 1 Fast Path)
# ---------------------------------------------------------------------------
VERB_TOOL_MAP: Dict[str, str] = {
    # Applications & Explorer
    "open":      "open_app",
    "launch":    "open_app",
    "start":     "open_app",
    "run":       "open_app",
    "close":     "close_app",
    "quit":      "close_app",
    "exit":      "close_app",
    "kill":      "close_app",
    "explorer":  "file_explorer_open",
    # Window management
    "maximize":  "maximize_window",
    "minimise":  "minimize_window",
    "minimize":  "minimize_window",
    "restore":   "restore_window",
    "resize":    "resize_window",
    "focus":     "focus_window",
    "switch":    "focus_window",
    # Text / keyboard
    "type":      "type_text",
    "write":     "type_text",
    "input":     "type_text",
    "press":     "press_key",
    "hit":       "press_key",
    "hotkey":    "hotkey",
    "shortcut":  "macro_shortcut",
    # Mouse
    "click":     "mouse_click",
    "rightclick":"mouse_right_click",
    "doubleclick":"mouse_double_click",
    "scroll":    "mouse_scroll",
    "move":      "move_file",
    "drag":      "mouse_drag",
    # File system & Explorer
    "save":      "save_file",
    "read":      "read_text_file",
    "delete":    "move_to_recycle_bin",
    "recycle":   "move_to_recycle_bin",
    "trash":     "move_to_recycle_bin",
    "copy":      "copy_file",
    "paste":     "paste_clipboard",
    "cd":        "change_directory",
    "ls":        "list_directory",
    "dir":       "list_directory",
    "mkdir":     "create_directory",
    "touch":     "create_file",
    "rename":    "rename_path",
    "zip":       "create_zip_archive",
    "unzip":     "extract_zip_archive",
    "undo":      "undo_supported_file_operation",
    "share":     "file_share",
    # Search / browser
    "search":    "windows_search",
    "google":    "browser_search",
    "browse":    "open_url",
    "navigate":  "open_url",
    "goto":      "open_url",
    # Screenshots / vision
    "screenshot":"take_screenshot",
    "capture":   "take_screenshot",
    # System & Terminal
    "volume":    "set_volume",
    "mute":      "mute_audio",
    "sleep":     "system_sleep",
    "shutdown":  "system_shutdown",
    "restart":   "system_restart",
    "exec":      "terminal_execute",
    "cmd":       "terminal_execute",
    "whatsapp":  "whatsapp_search_and_message",
    "play":      "play_music",
}

MULTI_WORD_VERBS: Dict[str, str] = {
    "right click":    "mouse_right_click",
    "right-click":    "mouse_right_click",
    "double click":   "mouse_double_click",
    "double-click":   "mouse_double_click",
    "left click":     "mouse_click",
    "left-click":     "mouse_click",
    "middle click":   "mouse_click",
    "middle-click":   "mouse_click",
    "mouse click":    "mouse_click",
    "mouse move":     "mouse_move",
    "move mouse":     "mouse_move",
    "mouse drag":     "mouse_drag",
    "drag mouse":     "mouse_drag",
    "mouse position": "mouse_get_position",
    "cursor position":"mouse_get_position",
    "get mouse":      "mouse_get_position",
    "where mouse":    "mouse_get_position",
    # File Explorer & Filesystem multi-word phrases
    "file explorer":  "file_explorer_open",
    "open file explorer": "file_explorer_open",
    "open the file explorer": "file_explorer_open",
    "open explorer":  "file_explorer_open",
    "show in explorer": "file_explorer_reveal",
    "reveal in explorer": "file_explorer_reveal",
    "reveal file":    "file_explorer_reveal",
    "open with":      "file_open_with",
    "open-with":      "file_open_with",
    "list files":     "list_directory",
    "list file":      "list_directory",
    "list file folders": "list_directory",
    "list files folders": "list_directory",
    "list files and folders": "list_directory",
    "list folders":   "list_directory",
    "list folder":    "list_directory",
    "list directory": "list_directory",
    "show files":     "list_directory",
    "show folders":   "list_directory",
    "show directory": "list_directory",
    "change directory": "change_directory",
    "change folder":  "change_directory",
    "create folder":  "create_directory",
    "create directory": "create_directory",
    "create file":    "create_file",
    "make folder":    "create_directory",
    "make directory": "create_directory",
    "change file name": "rename_path",
    "change name":    "rename_path",
    "rename file":    "rename_path",
    "rename path":    "rename_path",
    "move file":      "move_file",
    "move folder":    "move_directory",
    "copy file":      "copy_file",
    "copy folder":    "copy_directory",
    "delete file":    "move_to_recycle_bin",
    "delete folder":  "move_to_recycle_bin",
    "recycle file":   "move_to_recycle_bin",
    "recycle bin":    "inspect_recycle_bin",
    "restore file":   "restore_from_recycle_bin",
    "zip folder":     "create_zip_archive",
    "unzip archive":  "extract_zip_archive",
    "unzip file":     "extract_zip_archive",
    "compare files":  "compare_files",
    "find files":     "search_files",
    "search files":   "search_files",
    "find duplicates": "find_duplicate_files",
    "find duplicate file": "find_duplicate_files",
    "find duplicate files": "find_duplicate_files",
    "duplicate files": "find_duplicate_files",
    "undo file":      "undo_supported_file_operation",
    "undo operation": "undo_supported_file_operation",
    "undo last operation": "undo_supported_file_operation",
    "run terminal cmd": "terminal_execute",
    "run terminal command": "terminal_execute",
    "run terminal":   "terminal_execute",
    "terminal cmd":   "terminal_execute",
    "run command":    "terminal_execute",
    "terminal command": "terminal_execute",
    "windows search": "windows_search",
    "windows button search": "windows_search",
    "win search":     "windows_search",
    "win button search": "windows_search",
    "start menu search": "windows_search",
    "start search":   "windows_search",
    "search windows": "windows_search",
    "search on windows": "windows_search",
    "search app":     "windows_search",
    "search for":     "windows_search",
    "web search":     "web_search",
    "browser search": "browser_search",
    "google search":  "browser_search",
    "search google":  "browser_search",
    "search on google": "browser_search",
    "search in google": "browser_search",
    "search on browser": "browser_search",
    "search browser": "browser_search",
    "open google search": "browser_search",
    "current state":  "get_current_desktop_state",
    "desktop state":  "get_current_desktop_state",
    "browser state":  "get_current_desktop_state",
    "which desktop":  "get_current_desktop_state",
    "search bar":     "browser_search_bar",
    "focus search bar": "browser_search_bar",
    "ctrl k":         "browser_search_bar",
    "whatsapp message": "whatsapp_search_and_message",
    "whatsapp search": "whatsapp_search_and_message",
    "send whatsapp":  "whatsapp_search_and_message",
    "click like":     "uia_click_button",
    "like button":    "uia_click_button",
    "click send":     "uia_click_button",
    "send button":    "uia_click_button",
    "enter button":   "uia_click_button",
    "submit button":  "uia_click_button",
    "click button":   "uia_click_button",
    "click below first link": "click_first_link",
    "click below link":       "click_first_link",
    "click below":            "click_first_link",
    "click first link":       "click_first_link",
    "click 1st link":         "click_first_link",
    "click top link":         "click_first_link",
    "click first video":      "click_first_link",
    "click 1st video":        "click_first_link",
    "click top video":        "click_first_link",
    "click result link":      "click_first_link",
    "click first result":     "click_first_link",
    "click content area":     "click_ui_content",
    "click content":          "click_ui_content",
    "click box":              "click_ui_content",
    "click text":             "click_ui_content",
    "click icon":             "click_ui_content",
    "click on":               "click_ui_content",
    "play song":      "play_music",
    "play music":     "play_music",
    "play track":     "play_music",
    "play video":     "play_music",
    "play media":     "play_music",
    "resume music":   "play_music",
    "pause music":    "play_music",
    "mouse move up":    "mouse_move",
    "mouse move down":  "mouse_move",
    "mouse move left":  "mouse_move",
    "mouse move right": "mouse_move",
    "move mouse up":    "mouse_move",
    "move mouse down":  "mouse_move",
    "move mouse left":  "mouse_move",
    "move mouse right": "mouse_move",
    "move cursor up":   "mouse_move",
    "move cursor down": "mouse_move",
    "move cursor left": "mouse_move",
    "move cursor right":"mouse_move",
    "mouse up":         "mouse_move",
    "mouse down":       "mouse_move",
    "mouse left":       "mouse_move",
    "mouse right":      "mouse_move",
    # System Telemetry & Status (Deterministic Routing)
    "cpu usage":          "get_system_information",
    "cpu percent":        "get_system_information",
    "show cpu":           "get_system_information",
    "my cpu":             "get_system_information",
    "show my cpu":        "get_system_information",
    "show my cpu usage":  "get_system_information",
    "system info":        "get_system_information",
    "system information": "get_system_information",
    "system specs":       "get_system_information",
    "ram usage":          "get_system_information",
    "memory usage":       "get_system_information",
    "disk usage":         "get_system_information",
    "battery status":     "get_system_information",
    "battery percentage": "get_system_information",
    "battery level":      "get_system_information",
    # Process Inspection
    "list running processes": "list_running_processes",
    "show running processes": "list_running_processes",
    "list all processes":     "list_running_processes",
    "show all processes":     "list_running_processes",
    "list processes":         "list_running_processes",
    "show processes":         "list_running_processes",
    "running processes":      "list_running_processes",
    "process list":           "list_running_processes",
    "running apps":           "list_running_processes",
    "running tasks":          "list_running_processes",
    "task list":              "list_running_processes",
    # Window Inspection
    "active window":      "win32_get_foreground_window",
    "active windows":     "win32_get_foreground_window",
    "foreground window":  "win32_get_foreground_window",
    "foreground windows": "win32_get_foreground_window",
    "focused window":     "win32_get_foreground_window",
    "focused windows":    "win32_get_foreground_window",
    "current window":     "win32_get_foreground_window",
    "current windows":    "win32_get_foreground_window",
    "which window":       "win32_get_foreground_window",
    "list windows":       "win32_enum_windows",
    "show windows":       "win32_enum_windows",
    "open windows":       "win32_enum_windows",
    "all windows":        "win32_enum_windows",
}

PRONOUNS = {"it", "that", "this", "the app", "the window", "the file", "this file", "this folder"}


# ---------------------------------------------------------------------------
# Execution Context – carries state across steps & resolves references
# ---------------------------------------------------------------------------
class ExecutionContext(BaseModel):
    """Mutable context bag threaded through all steps of a user session."""
    last_app_name: Optional[str] = None
    last_window_title: Optional[str] = None
    last_command: Optional[str] = None
    last_url: Optional[str] = None
    last_path: Optional[str] = None
    last_selection: Optional[str] = None
    last_items: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = {"arbitrary_types_allowed": True}

    def update(self, key: str, value: Dict[str, Any]) -> None:
        """Update internal state from a completed tool execution."""
        if not isinstance(value, dict):
            return
        if key in ("open_app", "launch_app"):
            self.last_app_name = value.get("app_name") or next(iter(value.values()), None)
        elif key == "focus_window":
            self.last_window_title = value.get("app_name") or value.get("title")
        elif key == "open_url":
            self.last_url = value.get("url")
        elif key in ("list_directory", "change_directory", "file_explorer_open"):
            p = value.get("path") or value.get("folder_path")
            if p:
                self.last_path = p
            if "entries" in value:
                self.last_items = value["entries"]
        elif key in ("search_files", "find_duplicate_files") and "matches" in value:
            self.last_items = [{"path": m, "name": os.path.basename(m)} for m in value["matches"]]


# ---------------------------------------------------------------------------
# Step – one parsed command fragment
# ---------------------------------------------------------------------------
class Step(BaseModel):
    """Represents a single parsed command fragment with routing telemetry."""
    command: str
    is_direct: bool = False
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    categories: List[str] = Field(default_factory=list)
    routing_result: Optional[RoutingResult] = None


def split_commands(user_input: str) -> List[str]:
    """Split user text into separate command fragments."""
    parts = re.split(r"\s*(?:&&|;|\n|,|\band\s+then\b|\band\b)\s*", user_input.strip(), flags=re.IGNORECASE)
    return [p.strip() for p in parts if p.strip()]


# ---------------------------------------------------------------------------
# Argument Extractor Strategy Handlers
# ---------------------------------------------------------------------------
def _resolve_pronouns(words: List[str], ctx: ExecutionContext) -> List[str]:
    phrase = " ".join(words).strip().lower()
    if phrase in PRONOUNS:
        target = ctx.last_selection or ctx.last_path or ctx.last_app_name
        return [target] if target else []
    return [
        (ctx.last_selection or ctx.last_path or ctx.last_app_name if w.lower() in PRONOUNS and (ctx.last_selection or ctx.last_path or ctx.last_app_name) else w)
        for w in words
    ]

def _extract_app_or_window(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    target = " ".join(rest).strip() if rest else (ctx.last_app_name or "")
    return {"app_name": target} if target else {}

def _extract_text(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    return {"text": " ".join(rest)} if rest else {}

def _extract_key_or_shortcut(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    if rest and rest[0].lower() == "shortcut":
        rest = rest[1:]
    return {"key": " ".join(rest)} if rest else {}

def _extract_action(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    return {"action": " ".join(rest)} if rest else {}

def _extract_query(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    text = " ".join(rest).strip()
    if text:
        text = re.sub(
            r"^(?:for\s+|windows\s+(?:for\s+)?|button\s+(?:for\s+)?|app\s+|the\s+|google\s+(?:for\s+)?|on\s+google\s+(?:for\s+)?|in\s+google\s+(?:for\s+)?|browser\s+(?:for\s+)?|on\s+browser\s+(?:for\s+)?)",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
    return {"query": text} if text else {}

def _extract_url(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    return {"url": " ".join(rest)} if rest else {}

def _extract_path(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    if rest:
        raw = " ".join(rest).strip()
        # Clean out conversational filler
        m = re.search(r"\b(?:named|called|name)\s+([a-zA-Z0-9_\-\.]+)", raw, flags=re.IGNORECASE)
        if m:
            return {"path": m.group(1)}
        return {"path": raw}
    if ctx.last_path or ctx.last_selection:
        return {"path": ctx.last_selection or ctx.last_path or ""}
    return {}

def _extract_mouse_click(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    args: Dict[str, Any] = {}
    rest_str = " ".join(rest).strip()
    if rest_str:
        args["target"] = rest_str
    coords = re.findall(r"\b\d+\b", rest_str)
    if len(coords) >= 2:
        args["x"] = int(coords[0])
        args["y"] = int(coords[1])
    if "center" in rest_str.lower():
        args["target"] = "center"
    return args

def _extract_mouse_move(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    args: Dict[str, Any] = {}
    rest_str = " ".join(rest).strip()
    if rest_str:
        args["args"] = rest_str
        args["target"] = rest_str
    coords = re.findall(r"\b\d+\b", rest_str)
    if len(coords) >= 2:
        args["x"] = int(coords[0])
        args["y"] = int(coords[1])
    elif len(coords) == 1:
        args["distance"] = int(coords[0])

    combined = f"{verb} {rest_str}".lower()
    for d in ("up", "down", "left", "right"):
        if d in combined:
            args["direction"] = d
            break

    if "center" in rest_str.lower():
        args["target"] = "center"
    return args

def _extract_play_query(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    text = " ".join(rest).strip()
    platform = "youtube"
    lower = text.lower()
    if any(k in lower for k in ("hotstar", "hostar", "jiohotstar", "jiohostar", "jio hotstar", "jio hostar", "jio cinema", "jiocinema")):
        platform = "hotstar"
        text = re.sub(r"\b(?:on\s+)?(?:jio\s*hott?star|hott?star|jio\s*cinema|jiocinema)\b", "", text, flags=re.IGNORECASE).strip()
    elif "spotify" in lower:
        platform = "spotify"
        text = re.sub(r"\b(?:on\s+)?spotify\b", "", text, flags=re.IGNORECASE).strip()
    elif "netflix" in lower:
        platform = "netflix"
        text = re.sub(r"\b(?:on\s+)?netflix\b", "", text, flags=re.IGNORECASE).strip()
    elif any(k in lower for k in ("prime video", "prime", "amazon prime")):
        platform = "prime"
        text = re.sub(r"\b(?:on\s+)?(?:amazon\s+)?prime(?:\s+video)?\b", "", text, flags=re.IGNORECASE).strip()
    elif "soundcloud" in lower:
        platform = "soundcloud"
        text = re.sub(r"\b(?:on\s+)?soundcloud\b", "", text, flags=re.IGNORECASE).strip()
    elif "youtube" in lower or "yt" in lower:
        platform = "youtube"
        text = re.sub(r"\b(?:on\s+)?(?:youtube|yt)\b", "", text, flags=re.IGNORECASE).strip()

    text = re.sub(r"^(?:the\s+)?(?:song\s+|music\s+|track\s+|video\s+|movie\s+|match\s+)?", "", text, flags=re.IGNORECASE).strip()
    return {"query": text, "platform": platform}

def _extract_mouse_scroll(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    args: Dict[str, Any] = {}
    rest_str = " ".join(rest).lower()
    if rest:
        args["args"] = " ".join(rest)
    nums = re.findall(r"-?\b\d+\b", rest_str)
    amount = int(nums[0]) if nums else 5
    if "down" in rest_str or "dwn" in rest_str:
        args["clicks"] = -abs(amount)
    elif "up" in rest_str:
        args["clicks"] = abs(amount)
    elif nums:
        args["clicks"] = int(nums[0])
    else:
        args["clicks"] = 5
    return args

def _extract_mouse_scroll_horizontal(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    args: Dict[str, Any] = {}
    rest_str = " ".join(rest).lower()
    if rest:
        args["args"] = " ".join(rest)
    nums = re.findall(r"-?\b\d+\b", rest_str)
    amount = int(nums[0]) if nums else 5
    if "left" in rest_str:
        args["clicks"] = -abs(amount)
    elif "right" in rest_str:
        args["clicks"] = abs(amount)
    elif nums:
        args["clicks"] = int(nums[0])
    else:
        args["clicks"] = 5
    return args

def _extract_volume(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    if not rest:
        return {}
    try:
        return {"level": int(rest[0].rstrip("%"))}
    except ValueError:
        return {"level": rest[0]}

def _extract_noop(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    return {}

def _extract_process_filter(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    raw = " ".join(rest).strip()
    if not raw:
        return {}
    m = re.search(r"\b(?:is|check if|find whether)?\s*([a-zA-Z0-9_\-\.]+)\s+(?:is\s+)?running\b", raw, flags=re.IGNORECASE)
    if m:
        return {"filter_name": m.group(1).strip()}
    cleaned = re.sub(r"^(?:matching|named|called|for|with|like)\s+", "", raw, flags=re.IGNORECASE).strip()
    return {"filter_name": cleaned} if cleaned else {}

def _extract_generic(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    return {"args": " ".join(rest)} if rest else {}

def _extract_path_or_default(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    raw = " ".join(rest).strip()
    if not raw:
        return {"path": "."}

    cleaned = raw
    cleaned = re.sub(
        r"^(?:all\s+)?(?:files\s+and\s+folders|file\s+folders|files\s+folders|files|folders|folder|directory|dir)\s*",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    cleaned = re.sub(r"^(?:in|inside|from|at|of|under)\s+", "", cleaned, flags=re.IGNORECASE).strip()

    lower = cleaned.lower()
    if lower in ("", ".", "here", "all", "all files", "current folder", "current directory", "this folder", "this directory"):
        return {"path": "."}

    m = re.match(r"^(?:folder|directory|dir)\s+(.+)$", cleaned, flags=re.IGNORECASE)
    if m:
        cleaned = m.group(1).strip()

    return {"path": cleaned if cleaned else "."}

def _extract_source_dest(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    text = " ".join(rest).strip()
    m = re.split(r"\s+(?:to|into)\s+", text, maxsplit=1)
    if len(m) == 2:
        src = m[0].strip()
        dst = m[1].strip()
        if src.lower() in PRONOUNS:
            src = ctx.last_selection or ctx.last_path or src
        if dst.lower() in ("documents", "downloads", "desktop", "pictures", "music", "videos"):
            user_profile = os.environ.get("USERPROFILE", "")
            dst = os.path.join(user_profile, dst.capitalize())
        return {"source": src, "destination": dst}
    parts = text.split()
    if len(parts) >= 2:
        return {"source": parts[0].strip(), "destination": parts[1].strip()}
    return {"source": text, "destination": ""}

def _extract_batch_move(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    text = " ".join(rest).strip()
    m = re.split(r"\s+(?:to|into)\s+", text, maxsplit=1)
    if len(m) == 2:
        src = m[0].strip()
        dst = m[1].strip()
        # e.g. "pdfs" -> "*.pdf"
        if src.lower() in ("pdfs", "pdf files", "pdf"):
            src = "*.pdf"
        elif src.lower() in ("py files", "python files", "pys"):
            src = "*.py"
        elif src.endswith("s") and not src.startswith("*."):
            src = f"*.{src[:-1]}"
        if dst.lower() in ("documents", "downloads", "desktop", "pictures"):
            user_profile = os.environ.get("USERPROFILE", "")
            dst = os.path.join(user_profile, dst.capitalize())
        return {"source": src, "destination": dst}
    return _extract_source_dest(verb, rest, ctx)

def _extract_rename(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    text = " ".join(rest).strip()
    m = re.split(r"\s+(?:to|as)\s+", text, maxsplit=1)
    if len(m) == 2:
        src = m[0].strip()
        dst = m[1].strip()
        src = re.sub(r"^(?:the\s+)?(?:file\s+)?(?:name\s+)?", "", src, flags=re.IGNORECASE).strip()
        if src.lower() in PRONOUNS:
            src = ctx.last_selection or ctx.last_path or src
        return {"source": src, "new_name_or_path": dst}
    parts = text.split()
    filtered = [p for p in parts if p.lower() not in ("file", "name", "filename", "path")]
    if len(filtered) >= 2:
        return {"source": filtered[0].strip(), "new_name_or_path": filtered[1].strip()}
    if filtered and filtered[0].lower() in PRONOUNS and ctx.last_selection:
        return {"source": ctx.last_selection, "new_name_or_path": ""}
    if filtered:
        return {"source": filtered[0], "new_name_or_path": ""}
    return {"source": "", "new_name_or_path": ""}

def _extract_command(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    cmd = " ".join(rest).strip()
    return {"command": cmd} if cmd else {}

def _extract_open_with(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    text = " ".join(rest).strip()
    m = re.split(r"\s+(?:with|using)\s+", text, maxsplit=1)
    if len(m) == 2:
        return {"path": m[0].strip(), "app_name": m[1].strip()}
    parts = text.split()
    if len(parts) >= 2:
        return {"path": parts[0].strip(), "app_name": parts[1].strip()}
    return {"path": text}

def _extract_explorer(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    folder = " ".join(rest).strip() if rest else ""
    if folder.lower() in ("downloads", "documents", "desktop", "pictures", "music", "videos"):
        user_profile = os.environ.get("USERPROFILE", "")
        folder = os.path.join(user_profile, folder.capitalize())
    return {"folder_path": folder}

def _extract_write_file(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    text = " ".join(rest).strip()
    m = re.split(r"\s+(?:to|into)\s+", text, maxsplit=1)
    if len(m) == 2:
        return {"content": m[0].strip(), "path": m[1].strip()}
    parts = text.split(maxsplit=1)
    if len(parts) == 2:
        if "." in parts[0] or "/" in parts[0] or "\\" in parts[0]:
            return {"path": parts[0].strip(), "content": parts[1].strip()}
        if "." in parts[1]:
            return {"content": parts[0].strip(), "path": parts[1].strip()}
    return {"path": text, "content": ""}

def _extract_search_files(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    text = " ".join(rest).strip()
    clean_text = re.sub(r"^(?:list|find|search|show)\s+", "", text, flags=re.IGNORECASE).strip()
    m_ext = re.search(r"\b(?:all\s+)?([a-zA-Z0-9]+)\s+files?\b", clean_text, flags=re.IGNORECASE)
    if m_ext:
        ext = m_ext.group(1).lower()
        return {"query": f"*.{ext}", "root_dir": "."}
    if clean_text.startswith("*.") or clean_text.startswith("."):
        return {"query": clean_text if clean_text.startswith("*") else f"*{clean_text}", "root_dir": "."}
    return {"query": clean_text if clean_text else "*", "root_dir": "."}

def _extract_whatsapp(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    text = " ".join(rest).strip()
    text = re.sub(r"^(?:message|to|contact|search)\s+", "", text, flags=re.IGNORECASE).strip()
    m = re.split(r"\s+(?:message|msg|saying|text|and\s+say|and\s+send)\s+", text, maxsplit=1, flags=re.IGNORECASE)
    if len(m) == 2:
        return {"contact": m[0].strip(), "message": m[1].strip()}
    parts = text.split(maxsplit=1)
    if len(parts) == 2:
        return {"contact": parts[0], "message": parts[1]}
    return {"contact": text, "message": ""}

def _extract_uia_button(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    text = " ".join(rest).strip()
    lower = f"{verb} {text}".lower()
    role = "button"
    if "like" in lower: role = "like"
    elif "send" in lower: role = "send"
    elif "submit" in lower: role = "submit"
    elif "enter" in lower: role = "enter"
    elif "close" in lower: role = "close"
    elif "box" in lower: role = "box"
    return {"role": role, "query": text}

def _extract_uia_content(verb: str, rest: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    text = " ".join(rest).strip()
    element_type = "any"
    verb_low = verb.lower()
    text_low = text.lower()
    if "box" in verb_low or text_low.startswith("box ") or text_low.endswith(" box"):
        element_type = "box"
        text = re.sub(r"^(?:box|input\s+box|text\s+box)\s+|\s+box$", "", text, flags=re.IGNORECASE).strip()
    elif "text" in verb_low or text_low.startswith("text ") or text_low.endswith(" text"):
        element_type = "text"
        text = re.sub(r"^text\s+|\s+text$", "", text, flags=re.IGNORECASE).strip()
    elif "icon" in verb_low or text_low.startswith("icon ") or text_low.endswith(" icon"):
        element_type = "icon"
        text = re.sub(r"^icon\s+|\s+icon$", "", text, flags=re.IGNORECASE).strip()
    elif "button" in verb_low or text_low.startswith("button ") or text_low.endswith(" button"):
        element_type = "button"
        text = re.sub(r"^button\s+|\s+button$", "", text, flags=re.IGNORECASE).strip()

    if "content area" in text.lower():
        text = re.sub(r"\bcontent\s+area\b", "", text, flags=re.IGNORECASE).strip()

    clean_q = text.strip("\"' ")
    return {"query": clean_q, "element_type": element_type}


# Dispatch Table: O(1) map from tool_name to extractor strategy
ARG_EXTRACTORS: Dict[str, Callable[[str, List[str], ExecutionContext], Dict[str, Any]]] = {
    "open_app": _extract_app_or_window,
    "close_app": _extract_app_or_window,
    "focus_window": _extract_app_or_window,
    "maximize_window": _extract_app_or_window,
    "minimize_window": _extract_app_or_window,
    "restore_window": _extract_app_or_window,
    "resize_window": _extract_app_or_window,
    "type_text": _extract_text,
    "write_text": _extract_text,
    "press_key": _extract_key_or_shortcut,
    "hotkey": _extract_key_or_shortcut,
    "macro_shortcut": _extract_action,
    "windows_search": _extract_query,
    "macro_windows_search": _extract_query,
    "browser_search": _extract_query,
    "google_search": _extract_query,
    "macro_browser_search": _extract_query,
    "browser_search_bar": _extract_query,
    "get_current_desktop_state": _extract_noop,
    "whatsapp_search_and_message": _extract_whatsapp,
    "uia_click_button": _extract_uia_button,
    "click_ui_content": _extract_uia_content,
    "click_content": _extract_uia_content,
    "play_music": _extract_play_query,
    "play_song": _extract_play_query,
    "click_first_link": _extract_noop,
    "click_below_link": _extract_noop,
    "web_search": _extract_query,
    "open_url": _extract_url,
    "browse": _extract_url,
    "save_file": _extract_path,
    "mouse_click": _extract_mouse_click,
    "mouse_right_click": _extract_mouse_click,
    "mouse_double_click": _extract_mouse_click,
    "mouse_move": _extract_mouse_move,
    "mouse_drag": _extract_mouse_move,
    "mouse_scroll": _extract_mouse_scroll,
    "mouse_scroll_horizontal": _extract_mouse_scroll_horizontal,
    "mouse_get_position": _extract_noop,
    "set_volume": _extract_volume,
    "mute_audio": _extract_noop,
    "take_screenshot": _extract_noop,
    "list_directory": _extract_path_or_default,
    "change_directory": _extract_path,
    "create_directory": _extract_path,
    "create_file": _extract_path,
    "read_text_file": _extract_path,
    "write_text_file": _extract_write_file,
    "move_to_recycle_bin": _extract_path,
    "move_file": _extract_source_dest,
    "move_directory": _extract_source_dest,
    "batch_move": _extract_batch_move,
    "copy_file": _extract_source_dest,
    "copy_directory": _extract_source_dest,
    "rename_path": _extract_rename,
    "file_explorer_open": _extract_explorer,
    "file_explorer_reveal": _extract_path,
    "file_open_with": _extract_open_with,
    "file_share": _extract_path,
    "terminal_execute": _extract_command,
    "execute_and_validate": _extract_command,
    "undo_supported_file_operation": _extract_noop,
    "inspect_recycle_bin": _extract_noop,
    "restore_from_recycle_bin": _extract_path,
    "search_files": _extract_search_files,
    "search_file_contents": _extract_query,
    "find_duplicate_files": _extract_path_or_default,
    "compare_files": _extract_source_dest,
    "create_zip_archive": _extract_source_dest,
    "extract_zip_archive": _extract_source_dest,
    "get_system_information": _extract_noop,
    "list_running_processes": _extract_process_filter,
    "win32_get_foreground_window": _extract_noop,
    "win32_enum_windows": _extract_noop,
}

def _extract_args(verb: str, tool_name: str, parts: List[str], ctx: ExecutionContext) -> Dict[str, Any]:
    resolved_rest = _resolve_pronouns(parts[1:], ctx)
    extractor = ARG_EXTRACTORS.get(tool_name, _extract_generic)
    return extractor(verb, resolved_rest, ctx)


# ---------------------------------------------------------------------------
# Command Verb Resolver
# ---------------------------------------------------------------------------
def resolve_command_verb(parts: List[str]) -> Tuple[Optional[str], Optional[str], List[str]]:
    """Resolve verb and tool_name using multi-word phrase (up to 4 words) or single-word lookup."""
    if not parts:
        return None, None, parts

    for n in (4, 3, 2):
        if len(parts) >= n:
            phrase = " ".join(parts[:n]).lower()
            if phrase in MULTI_WORD_VERBS:
                return phrase, MULTI_WORD_VERBS[phrase], [phrase] + parts[n:]

    verb = parts[0].lower()

    if verb == "write" and ("to" in parts or "into" in parts):
        return "write", "write_text_file", parts

    if verb == "open" and len(parts) > 1:
        lower_rest = " ".join(parts[1:]).lower()
        if "explorer" in lower_rest:
            return "open explorer", "file_explorer_open", ["file explorer"] + [p for p in parts[1:] if p.lower() not in ("file", "explorer", "the")]
        second = parts[1].lower()
        if second in ("folder", "directory", "dir"):
            return "open explorer", "file_explorer_open", ["file explorer"] + parts[2:]
        if second in ("file", "document"):
            return "read", "read_text_file", parts[2:]
        target_path = " ".join(parts[1:]).strip()
        if os.path.exists(target_path):
            if os.path.isdir(target_path):
                return "open explorer", "file_explorer_open", parts[1:]
            return "open", "file_open_with", parts[1:]

    if verb == "search" and len(parts) > 1:
        lower_rest = " ".join(parts[1:]).lower()
        if "windows" in lower_rest:
            return "windows search", "windows_search", ["windows search"] + [p for p in parts[1:] if p.lower() not in ("windows", "on", "the")]
        if "google" in lower_rest or "browser" in lower_rest:
            cleaned_parts = [p for p in parts[1:] if p.lower() not in ("google", "browser", "on", "in", "the", "for")]
            return "browser search", "browser_search", ["browser search"] + cleaned_parts
        if "web" in lower_rest or "online" in lower_rest or "internet" in lower_rest:
            return "web search", "web_search", ["web search"] + [p for p in parts[1:] if p.lower() not in ("web", "online", "internet")]
        if re.search(r"\b(?:all\s+)?([a-zA-Z0-9]+)\s+files\b", lower_rest) or lower_rest.startswith("*.") or "files" in lower_rest:
            return "search files", "search_files", parts
        return "windows search", "windows_search", ["windows search"] + parts[1:]

    if verb == "click" and len(parts) > 1:
        rest_str = " ".join(parts[1:]).strip()
        if (
            (rest_str.startswith('"') and rest_str.endswith('"'))
            or (rest_str.startswith("'") and rest_str.endswith("'"))
            or any(rest_str.lower().startswith(p) for p in ("box", "text", "icon", "content", "area"))
            or "content area" in rest_str.lower()
        ):
            return "click content", "click_ui_content", ["click content"] + parts[1:]

    return verb, VERB_TOOL_MAP.get(verb), parts


# ---------------------------------------------------------------------------
# Layer 3: Semantic Candidate Retrieval (fastembed ONNX)
# ---------------------------------------------------------------------------
class SemanticIntentRouter:
    """Fast semantic intent matcher using fastembed ONNX embeddings."""

    def __init__(self):
        self._model = None
        self._exemplars: List[Tuple[str, str]] = [
            ("launch application", "open_app"),
            ("start the program", "open_app"),
            ("open up software", "open_app"),
            ("run application", "open_app"),
            ("open chrome", "open_app"),
            ("kill the application", "close_app"),
            ("terminate the program", "close_app"),
            ("shut down the program", "close_app"),
            ("quit the application", "close_app"),
            ("make window full screen", "maximize_window"),
            ("expand window to full size", "maximize_window"),
            ("maximize current window", "maximize_window"),
            ("minimize window to taskbar", "minimize_window"),
            ("hide window into taskbar", "minimize_window"),
            ("bring window to the front", "focus_window"),
            ("switch over to app", "focus_window"),
            ("turn up the sound", "set_volume"),
            ("increase volume level", "set_volume"),
            ("decrease sound volume", "set_volume"),
            ("turn down the audio", "set_volume"),
            ("silence computer sound", "mute_audio"),
            ("mute all audio", "mute_audio"),
            ("take a screenshot of the screen", "take_screenshot"),
            ("capture current display", "take_screenshot"),
            ("snap photo of screen", "take_screenshot"),
            ("find information online", "web_search"),
            ("search Google for query", "web_search"),
            ("visit website address", "open_url"),
            ("go to web page", "open_url"),
            ("windows button search", "windows_search"),
            ("search using windows button", "windows_search"),
            ("search with start menu", "windows_search"),
            ("windows search for app", "windows_search"),
            ("search on windows", "windows_search"),
            ("open my downloads folder", "file_explorer_open"),
            ("open file explorer", "file_explorer_open"),
            ("browse files in directory", "file_explorer_open"),
            ("list files in directory", "list_directory"),
            ("show files in current folder", "list_directory"),
            ("display folder contents", "list_directory"),
            ("what is inside downloads", "list_directory"),
            ("change working directory", "change_directory"),
            ("create a new folder", "create_directory"),
            ("make a new directory", "create_directory"),
            ("create folder for projects", "create_directory"),
            ("create a new text file", "create_file"),
            ("touch new file", "create_file"),
            ("rename this file", "rename_path"),
            ("change the file name", "rename_path"),
            ("move file to another folder", "move_file"),
            ("transfer file into documents", "move_file"),
            ("move pdfs to documents", "batch_move"),
            ("copy file to destination", "copy_file"),
            ("delete file and move to recycle bin", "move_to_recycle_bin"),
            ("delete this folder", "move_to_recycle_bin"),
            ("trash this directory", "move_to_recycle_bin"),
            ("restore file from recycle bin", "restore_from_recycle_bin"),
            ("check the recycle bin", "inspect_recycle_bin"),
            ("find files by name", "search_files"),
            ("list all py files", "search_files"),
            ("find python files", "search_files"),
            ("search for python files", "search_files"),
            ("find duplicate files", "find_duplicate_files"),
            ("detect duplicate documents", "find_duplicate_files"),
            ("read text file content", "read_text_file"),
            ("write text into file", "write_text_file"),
            ("create zip archive of folder", "create_zip_archive"),
            ("extract zip archive contents", "extract_zip_archive"),
            ("compare two files", "compare_files"),
            ("undo the last file operation", "undo_supported_file_operation"),
            ("undo last action", "undo_supported_file_operation"),
            ("run terminal command", "terminal_execute"),
            ("execute shell command", "terminal_execute"),
            ("right click on element", "mouse_right_click"),
            ("scroll down page", "mouse_scroll"),
            ("scroll up document", "mouse_scroll"),
        ]
        self._exemplar_texts = [e[0] for e in self._exemplars]
        self._exemplar_embeddings = None
        self._init_failed = False

    def get_model(self):
        """Lazily initialize the fastembed ONNX model and embed exemplars."""
        if self._model is None and not self._init_failed:
            try:
                from fastembed import TextEmbedding
                import numpy as np

                # Primary: all-MiniLM-L6-v2 (ultralight, fast inference)
                try:
                    self._model = TextEmbedding("sentence-transformers/all-MiniLM-L6-v2")
                except Exception:
                    self._model = TextEmbedding("BAAI/bge-small-en-v1.5")

                raw_embeds = list(self._model.embed(self._exemplar_texts))
                normed = [v / (np.linalg.norm(v) + 1e-9) for v in raw_embeds]
                self._exemplar_embeddings = np.array(normed)
            except Exception:
                self._init_failed = True
                self._model = None
        return self._model

    def match_candidates(self, text: str, top_k: int = 5) -> List[Tuple[str, float]]:
        """Return top candidate tools ranked by similarity."""
        model = self.get_model()
        if model is None or self._exemplar_embeddings is None:
            return []

        import numpy as np
        try:
            query_raw = list(model.embed([text]))[0]
            query_norm = query_raw / (np.linalg.norm(query_raw) + 1e-9)
            similarities = np.dot(self._exemplar_embeddings, query_norm)

            # Aggregate best score per tool
            tool_scores: Dict[str, float] = {}
            for idx, score in enumerate(similarities):
                tool = self._exemplars[idx][1]
                tool_scores[tool] = max(tool_scores.get(tool, 0.0), float(score))

            ranked = sorted(tool_scores.items(), key=lambda x: x[1], reverse=True)
            return ranked[:top_k]
        except Exception:
            return []

    def match(self, text: str, threshold: float = 0.78) -> Optional[Tuple[str, float]]:
        candidates = self.match_candidates(text, top_k=2)
        if candidates and candidates[0][1] >= threshold:
            return candidates[0]
        return None


_semantic_router = SemanticIntentRouter()


def _extract_semantic_args(tool_name: str, text: str, ctx: ExecutionContext) -> Dict[str, Any]:
    """Extract slots and arguments from a semantically-matched phrase."""
    lower = text.lower().strip()

    if tool_name in ("open_app", "close_app", "maximize_window", "minimize_window", "focus_window"):
        stop_words = {
            "please", "could", "you", "can", "would", "launch", "start", "open", "up",
            "run", "kill", "close", "shut", "down", "exit", "quit", "terminate",
            "maximize", "minimise", "minimize", "focus", "switch", "to", "the",
            "app", "program", "application", "window", "software", "screen",
        }
        words = [w for w in re.findall(r"\b\w+\b", lower) if w not in stop_words]
        resolved = _resolve_pronouns(words, ctx)
        target = " ".join(resolved).strip() or (ctx.last_app_name or "")
        return {"app_name": target} if target else {}

    if tool_name == "set_volume":
        vol_match = re.search(r"\b(\d{1,3})\b", lower)
        if vol_match:
            return {"level": int(vol_match.group(1))}
        if any(w in lower for w in ("up", "louder", "increase", "raise")):
            return {"level": "+10"}
        if any(w in lower for w in ("down", "lower", "decrease", "softer")):
            return {"level": "-10"}
        return {"level": 50}

    if tool_name == "mute_audio":
        return {}

    if tool_name == "take_screenshot":
        return {}

    if tool_name == "web_search":
        stop_words = {"search", "find", "google", "online", "for", "look", "up"}
        query_words = [w for w in lower.split() if w not in stop_words]
        return {"query": " ".join(query_words)}

    if tool_name == "open_url":
        url_match = re.search(r"https?://\S+|www\.\S+", text)
        if url_match:
            return {"url": url_match.group(0)}
        return {"url": text.strip()}

    if tool_name == "file_explorer_open":
        m = re.search(r"\b(?:open|show|explore)\s+(?:my\s+)?(\w+|[a-zA-Z]:[\\/][^\s]+)", lower)
        folder = m.group(1) if m else ""
        if folder in ("downloads", "documents", "desktop", "pictures", "music", "videos"):
            user_profile = os.environ.get("USERPROFILE", "")
            target = os.path.join(user_profile, folder.capitalize())
            return {"folder_path": target}
        return {"folder_path": folder}

    if tool_name in ("list_directory", "change_directory", "create_directory", "move_to_recycle_bin", "read_text_file", "find_duplicate_files"):
        parts = text.strip().split()
        return _extract_path_or_default("", parts[1:] if len(parts) > 1 else [], ctx)

    if tool_name == "search_files":
        parts = text.strip().split()
        return _extract_search_files("", parts[1:] if len(parts) > 1 else [], ctx)

    if tool_name == "batch_move":
        parts = text.strip().split()
        return _extract_batch_move("", parts[1:] if len(parts) > 1 else [], ctx)

    if tool_name in ("move_file", "copy_file", "rename_path"):
        parts = text.strip().split()
        return _extract_source_dest("", parts[1:] if len(parts) > 1 else [], ctx)

    if tool_name in ("terminal_execute", "execute_and_validate"):
        return {"command": text.strip()}

    return {}


# ---------------------------------------------------------------------------
# Intelligent 6-Layer NLP Router
# ---------------------------------------------------------------------------
class IntelligentNLPRouter:
    """Intelligent, multi-layered NLP routing engine for JARVIS OS."""

    def __init__(self):
        self.corrector = nlp_corrector
        self.semantic = _semantic_router
        self._ollama_url = getattr(config, "ollama_host", "http://127.0.0.1:11434")
        self._gemma_model = getattr(config, "local_brain_model", "functiongemma:latest")

    def classify_with_gemma(self, text: str, candidate_names: List[str]) -> Optional[Dict[str, Any]]:
        """Layer 4: Call FunctionGemma with top candidate tools to resolve ambiguity."""
        import urllib.request
        try:
            tools_payload = []
            for name in candidate_names:
                rec = get_canonical_tool_record(name)
                if rec:
                    tools_payload.append({
                        "type": "function",
                        "function": {
                            "name": rec.name,
                            "description": rec.description,
                            "parameters": {
                                "type": "object",
                                "properties": rec.argument_schema,
                                "required": rec.required_arguments,
                            }
                        }
                    })

            if not tools_payload:
                return None

            req_data = {
                "model": self._gemma_model,
                "messages": [{"role": "user", "content": text}],
                "tools": tools_payload,
                "stream": False,
            }

            url = f"{self._ollama_url.rstrip('/')}/api/chat"
            req = urllib.request.Request(
                url,
                data=json.dumps(req_data).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                msg = data.get("message", {})
                calls = msg.get("tool_calls")
                if calls and isinstance(calls, list):
                    fn = calls[0].get("function", {})
                    call_name = resolve_canonical_tool_name(fn.get("name", ""))
                    if call_name:
                        return {"tool": call_name, "arguments": fn.get("arguments", {})}
        except Exception as e:
            logger.debug(f"Gemma classification fallback skipped: {e}")
        return None

    def route_command(self, raw_command: str, ctx: ExecutionContext) -> RoutingResult:
        """Route a single command through the 6-layer pipeline."""
        raw = raw_command.strip()
        if not raw:
            return RoutingResult(intent="empty", reason="Empty command", is_direct=False)

        # -------------------------------------------------------------------
        # NORMALIZE & TEXT CORRECTION (Spelling corrected, literals preserved)
        # -------------------------------------------------------------------
        normalized, masked, literals = self.corrector.normalize(raw)
        is_exact = (normalized.strip().lower() == raw.strip().lower())

        # -------------------------------------------------------------------
        # LAYER 1 & 2: DETERMINISTIC DIRECT MATCH (Exact or Normalized)
        # -------------------------------------------------------------------
        norm_parts = normalized.split()
        verb, tool_name, resolved_parts = resolve_command_verb(norm_parts)

        # Pattern-based normalization rules for prompt examples
        norm_lower = normalized.lower()
        if not tool_name:
            if re.search(r"\b(?:list|find|search|show)\s+(?:all\s+)?([a-zA-Z0-9]+)\s+files\b", norm_lower):
                tool_name = "search_files"
            elif "duplicate" in norm_lower:
                tool_name = "find_duplicate_files"
            elif "undo" in norm_lower:
                tool_name = "undo_supported_file_operation"
            elif re.search(r"\bmov(?:e)?\s+([a-zA-Z0-9]+)s?\s+to\s+", norm_lower):
                tool_name = "batch_move"
            elif re.search(r"\b(?:del|delete|recycle|trash)\s+(?:this\s+)?(?:folder|directory)\b", norm_lower):
                tool_name = "move_to_recycle_bin"
            elif re.search(r"\b(?:change|rename)\s+(?:file\s+)?name\b", norm_lower):
                tool_name = "rename_path"
            elif re.search(r"\b(?:show|get|check|display|what is|what's)?\s*(?:my\s+)?(?:cpu|ram|memory|disk|battery|system info|system specs)\b", norm_lower):
                tool_name = "get_system_information"
                verb = "get_system_information"
                resolved_parts = ["get_system_information"]
            elif re.search(r"\b(?:is|check if|find whether)\s+([a-zA-Z0-9_\-\.]+)\s+(?:is\s+)?running\b", norm_lower):
                tool_name = "list_running_processes"
                verb = "list_running_processes"
                resolved_parts = ["list_running_processes", norm_lower]
            elif re.search(r"\b(?:list|show|get)?\s*(?:all\s+)?(?:running\s+)?(?:processes|process list|tasks)\b", norm_lower):
                tool_name = "list_running_processes"
                verb = "list_running_processes"
                resolved_parts = ["list_running_processes"]

        if tool_name is not None and verb is not None:
            canonical = resolve_canonical_tool_name(tool_name) or tool_name
            args = _extract_args(verb, canonical, resolved_parts, ctx)
            
            # Check for missing required arguments (e.g. "change file name" without args)
            rec = get_canonical_tool_record(canonical)
            if canonical == "rename_path" and (not args.get("source") or not args.get("new_name_or_path")):
                return RoutingResult(
                    intent="rename_path",
                    selected_tool=canonical,
                    arguments=args,
                    confidence=0.85,
                    needs_clarification=True,
                    clarification_prompt="Which file would you like to rename and what should the new name be?",
                    routing_layer="clarification",
                    raw_input=raw,
                    normalized_input=normalized,
                    is_direct=False,
                    reason="Required file paths missing for rename operation",
                )
            if canonical == "terminal_execute" and not args.get("command"):
                return RoutingResult(
                    intent="terminal_execute",
                    selected_tool=canonical,
                    arguments={},
                    confidence=0.85,
                    needs_clarification=True,
                    clarification_prompt="What terminal command would you like me to run?",
                    routing_layer="clarification",
                    raw_input=raw,
                    normalized_input=normalized,
                    is_direct=False,
                    reason="Command string missing for terminal execution",
                )

            routing_layer = "exact" if is_exact else "normalized"
            confidence = 1.0 if is_exact else 0.95
            reason = f"Exact match on verb phrase '{verb}'" if is_exact else f"Normalized match on '{normalized}'"

            return RoutingResult(
                intent=canonical,
                selected_tool=canonical,
                arguments=args,
                confidence=confidence,
                routing_layer=routing_layer,
                raw_input=raw,
                normalized_input=normalized,
                is_direct=True,
                reason=reason,
            )
        elif tool_name is not None:
            # Pattern matched without a leading verb
            canonical = resolve_canonical_tool_name(tool_name) or tool_name
            args = _extract_args(canonical, canonical, [canonical] + norm_parts, ctx)
            return RoutingResult(
                intent=canonical,
                selected_tool=canonical,
                arguments=args,
                confidence=0.95,
                routing_layer="normalized",
                raw_input=raw,
                normalized_input=normalized,
                is_direct=True,
                reason=f"Pattern match on '{normalized}'",
            )

        # -------------------------------------------------------------------
        # LAYER 3: SEMANTIC RETRIEVAL (2-5ms ONNX)
        # -------------------------------------------------------------------
        query_text = normalized if normalized else raw
        candidates = self.semantic.match_candidates(query_text, top_k=5)
        candidate_info = [{"tool": c[0], "score": round(c[1], 4)} for c in candidates]

        if candidates:
            top_tool, top_score = candidates[0]
            runner_up_score = candidates[1][1] if len(candidates) > 1 else 0.0
            margin = top_score - runner_up_score

            # Confident, unambiguous semantic match
            if top_score >= 0.78 and margin >= 0.05:
                canonical = resolve_canonical_tool_name(top_tool) or top_tool
                args = _extract_semantic_args(canonical, query_text, ctx)
                return RoutingResult(
                    intent=canonical,
                    selected_tool=canonical,
                    arguments=args,
                    confidence=round(top_score, 4),
                    routing_layer="semantic",
                    raw_input=raw,
                    normalized_input=normalized,
                    candidates=candidate_info,
                    is_direct=True,
                    reason=f"High-confidence semantic match (score={top_score:.3f}, margin={margin:.3f})",
                )

            # ---------------------------------------------------------------
            # LAYER 4: GEMMA CLASSIFICATION (SLM Shortlist Fallback)
            # ---------------------------------------------------------------
            if 0.55 <= top_score < 0.78 or margin < 0.05:
                shortlist = [c[0] for c in candidates[:3]]
                gemma_res = self.classify_with_gemma(query_text, shortlist)
                if gemma_res:
                    canonical = resolve_canonical_tool_name(gemma_res["tool"]) or gemma_res["tool"]
                    return RoutingResult(
                        intent=canonical,
                        selected_tool=canonical,
                        arguments=gemma_res.get("arguments", {}),
                        confidence=0.90,
                        routing_layer="gemma",
                        raw_input=raw,
                        normalized_input=normalized,
                        candidates=candidate_info,
                        is_direct=True,
                        reason="Disambiguated via local FunctionGemma router",
                    )

            # ---------------------------------------------------------------
            # LAYER 6: CLARIFICATION (Ambiguity Detected)
            # ---------------------------------------------------------------
            if margin < 0.04 and top_score >= 0.70 and len(query_text.split()) >= 2 and len(candidates) >= 2:
                t1, t2 = candidates[0][0], candidates[1][0]
                return RoutingResult(
                    intent="ambiguous",
                    selected_tool=None,
                    confidence=round(top_score, 4),
                    needs_clarification=True,
                    clarification_prompt=f"Did you want to use '{t1}' or '{t2}'?",
                    routing_layer="clarification",
                    raw_input=raw,
                    normalized_input=normalized,
                    candidates=candidate_info,
                    is_direct=False,
                    reason=f"Ambiguous candidates within margin {margin:.3f}",
                )

            # Moderate semantic match fallback
            if top_score >= 0.70:
                canonical = resolve_canonical_tool_name(top_tool) or top_tool
                args = _extract_semantic_args(canonical, query_text, ctx)
                return RoutingResult(
                    intent=canonical,
                    selected_tool=canonical,
                    arguments=args,
                    confidence=round(top_score, 4),
                    routing_layer="semantic",
                    raw_input=raw,
                    normalized_input=normalized,
                    candidates=candidate_info,
                    is_direct=True,
                    reason=f"Moderate semantic match (score={top_score:.3f})",
                )

        return RoutingResult(
            intent="unknown",
            selected_tool=None,
            confidence=0.0,
            routing_layer="fallback",
            raw_input=raw,
            normalized_input=normalized,
            candidates=candidate_info,
            is_direct=False,
            reason="No registered tool matched user instruction",
        )


_nlp_router = IntelligentNLPRouter()


# ---------------------------------------------------------------------------
# Planner & Re-matching Interface (Preserving complete backward compatibility)
# ---------------------------------------------------------------------------
def match_direct_command(command: str, ctx: ExecutionContext) -> Step:
    """Parse a single command through the Intelligent NLP Router."""
    res = _nlp_router.route_command(command, ctx)
    is_direct = (res.selected_tool is not None) and (not res.needs_clarification)
    step = Step(
        command=command,
        is_direct=is_direct,
        tool_name=res.selected_tool,
        tool_args=res.arguments,
        categories=[_infer_category(res.selected_tool or "")],
        routing_result=res,
    )
    return step


def plan_user_input(user_input: str, ctx: ExecutionContext) -> List[Step]:
    """Parse *user_input* into a list of Steps with 6-layer intelligence."""
    fragments = split_commands(user_input)
    steps: List[Step] = []

    for fragment in fragments:
        step = match_direct_command(fragment, ctx)
        steps.append(step)

    ctx.last_command = user_input
    return steps


TOOL_CATEGORY_MAP: Dict[str, str] = {
    "open_app": "computer", "close_app": "computer",
    "maximize_window": "computer", "minimize_window": "computer",
    "restore_window": "computer", "focus_window": "computer",
    "resize_window": "computer", "type_text": "computer",
    "press_key": "computer", "hotkey": "computer",
    "mouse_click": "computer", "mouse_right_click": "computer",
    "mouse_double_click": "computer", "mouse_scroll": "computer",
    "mouse_scroll_horizontal": "computer", "mouse_drag": "computer",
    "mouse_move": "computer", "mouse_get_position": "computer",
    "take_screenshot": "computer",
    # Filesystem & Explorer
    "save_file": "filesystem", "read_file": "filesystem",
    "delete_file": "filesystem", "copy_file": "filesystem",
    "read_text_file": "filesystem", "write_text_file": "filesystem",
    "append_text_file": "filesystem", "edit_text_file": "filesystem",
    "list_directory": "filesystem", "get_current_directory": "filesystem",
    "change_directory": "filesystem", "create_directory": "filesystem",
    "create_file": "filesystem", "move_file": "filesystem",
    "move_directory": "filesystem", "copy_directory": "filesystem",
    "batch_move": "filesystem", "batch_copy": "filesystem",
    "rename_path": "filesystem", "move_to_recycle_bin": "filesystem",
    "restore_from_recycle_bin": "filesystem", "inspect_recycle_bin": "filesystem",
    "permanently_delete": "filesystem", "undo_supported_file_operation": "filesystem",
    "create_zip_archive": "filesystem", "extract_zip_archive": "filesystem",
    "search_files": "filesystem", "search_file_contents": "filesystem",
    "find_duplicate_files": "filesystem", "compare_files": "filesystem",
    "file_explorer_open": "computer", "file_explorer_reveal": "computer",
    "file_open_with": "computer", "file_share": "computer",
    # Terminal
    "terminal_execute": "terminal", "execute_and_validate": "terminal",
    "terminal_run_safe": "terminal", "terminal_run_action": "terminal",
    "terminal_run_sudo": "terminal",
    # Search / browser / windows
    "windows_search": "windows", "macro_windows_search": "windows",
    "browser_search": "browser", "google_search": "browser", "macro_browser_search": "browser",
    "browser_search_bar": "browser",
    "get_current_desktop_state": "system",
    "whatsapp_search_and_message": "communication",
    "uia_click_button": "input",
    "click_ui_content": "input",
    "click_content": "input",
    "play_music": "media",
    "play_song": "media",
    "web_search": "search", "open_url": "browser",
    "set_volume": "system", "mute_audio": "system",
    "system_sleep": "system", "system_shutdown": "system",
    "system_restart": "system",
    "get_system_information": "system",
    "list_running_processes": "system",
    "process_info": "system",
    "win32_get_foreground_window": "windows",
    "win32_enum_windows": "windows",
    "win32_set_window_pos": "windows",
}

def _infer_category(tool_or_verb: str) -> str:
    return TOOL_CATEGORY_MAP.get(tool_or_verb, "general")


async def route_user_input(user_input: str, ctx: ExecutionContext) -> List[Step]:
    return plan_user_input(user_input, ctx)

def get_router_model():
    try:
        from app.model import get_model
        return get_model()
    except Exception:
        return None

def get_fastembed_model():
    return _semantic_router.get_model()

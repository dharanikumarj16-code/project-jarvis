"""
app/tools/canonical_registry.py  –  Authoritative Canonical Tool Registry & Metadata
=====================================================================================

Provides a single source of truth for all tools registered in UnifiedToolBus.
Extracts live schemas, maps supported intents, canonical aliases, execution risks,
and argument requirements dynamically without duplicating tool implementations.
"""

from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field
from app.tools.bus import tool_bus, ToolDefinition
from app.permissions import PermissionLevel


class CanonicalToolRecord(BaseModel):
    """Structured canonical representation of a registered JARVIS tool."""
    name: str
    description: str
    category: str
    intents: List[str] = Field(default_factory=list)
    synonyms: List[str] = Field(default_factory=list)
    argument_schema: Dict[str, Any] = Field(default_factory=dict)
    required_arguments: List[str] = Field(default_factory=list)
    optional_arguments: List[str] = Field(default_factory=list)
    risk: str = "low"  # low, moderate, sensitive
    available: bool = True
    required_capability: Optional[str] = None


# Intent and synonym metadata mappings to enrich registered tools
TOOL_METADATA_EXTENSIONS: Dict[str, Dict[str, Any]] = {
    "open_app": {
        "intents": ["launch_app", "start_program", "open_application", "run_software"],
        "synonyms": ["launch", "start", "run", "open", "activate"],
        "risk": "low",
    },
    "close_app": {
        "intents": ["close_application", "terminate_program", "kill_app", "exit_software"],
        "synonyms": ["close", "quit", "exit", "kill", "terminate", "shut down"],
        "risk": "moderate",
    },
    "file_explorer_open": {
        "intents": ["open_file_explorer", "open_explorer", "browse_folder", "open_folder", "view_directory"],
        "synonyms": ["file explorer", "explorer", "open folder", "browse folder", "file manager"],
        "risk": "low",
    },
    "file_explorer_reveal": {
        "intents": ["reveal_in_explorer", "show_file", "locate_file", "highlight_file"],
        "synonyms": ["reveal file", "show in explorer", "locate in explorer"],
        "risk": "low",
    },
    "file_open_with": {
        "intents": ["open_file_with_app", "choose_application_for_file"],
        "synonyms": ["open with", "run with"],
        "risk": "low",
    },
    "list_directory": {
        "intents": ["list_files", "show_files", "list_directory", "view_folder_contents", "dir", "ls"],
        "synonyms": ["list", "dir", "ls", "show files", "list files", "list folders", "list file folders"],
        "risk": "low",
    },
    "change_directory": {
        "intents": ["change_directory", "cd", "navigate_directory", "switch_folder"],
        "synonyms": ["cd", "change folder", "switch directory", "navigate to"],
        "risk": "low",
    },
    "create_directory": {
        "intents": ["create_folder", "mkdir", "make_directory", "new_folder"],
        "synonyms": ["create folder", "mkdir", "make folder", "make directory", "new folder"],
        "risk": "low",
    },
    "create_file": {
        "intents": ["create_file", "touch", "make_file", "new_file"],
        "synonyms": ["touch", "create file", "make file", "new file"],
        "risk": "low",
    },
    "rename_path": {
        "intents": ["rename_file", "rename_directory", "rename_path", "change_filename"],
        "synonyms": ["rename", "change name", "rename file", "rename folder", "move"],
        "risk": "moderate",
    },
    "copy_file": {
        "intents": ["copy_file", "duplicate_file", "cp"],
        "synonyms": ["copy", "copy file", "duplicate"],
        "risk": "low",
    },
    "copy_directory": {
        "intents": ["copy_folder", "copy_directory"],
        "synonyms": ["copy folder", "copy directory"],
        "risk": "low",
    },
    "move_file": {
        "intents": ["move_file", "relocate_file", "mv"],
        "synonyms": ["move", "move file", "transfer file"],
        "risk": "moderate",
    },
    "move_directory": {
        "intents": ["move_folder", "move_directory"],
        "synonyms": ["move folder", "move directory"],
        "risk": "moderate",
    },
    "batch_move": {
        "intents": ["batch_move_files", "move_multiple_files", "move_pdfs", "move_images"],
        "synonyms": ["batch move", "move all", "move files"],
        "risk": "moderate",
    },
    "batch_copy": {
        "intents": ["batch_copy_files", "copy_multiple_files"],
        "synonyms": ["batch copy", "copy all", "copy files"],
        "risk": "low",
    },
    "move_to_recycle_bin": {
        "intents": ["delete_file", "delete_folder", "recycle_file", "trash_file", "remove_file"],
        "synonyms": ["delete", "recycle", "trash", "delete file", "delete folder", "remove"],
        "risk": "sensitive",
    },
    "restore_from_recycle_bin": {
        "intents": ["restore_file", "untrash_file", "recover_file"],
        "synonyms": ["restore", "recover", "restore file"],
        "risk": "moderate",
    },
    "inspect_recycle_bin": {
        "intents": ["view_recycle_bin", "check_trash", "inspect_recycle_bin"],
        "synonyms": ["recycle bin", "trash bin", "view trash"],
        "risk": "low",
    },
    "undo_supported_file_operation": {
        "intents": ["undo_operation", "revert_last_action", "undo_file_change"],
        "synonyms": ["undo", "undo file", "undo operation", "revert"],
        "risk": "moderate",
    },
    "search_files": {
        "intents": ["find_files", "search_directory", "locate_file", "list_matching_files"],
        "synonyms": ["find", "search", "find files", "search files", "locate file"],
        "risk": "low",
    },
    "search_file_contents": {
        "intents": ["grep", "search_text_in_files", "find_in_files"],
        "synonyms": ["grep", "search content", "find text"],
        "risk": "low",
    },
    "find_duplicate_files": {
        "intents": ["find_duplicates", "detect_duplicate_files", "duplicate_cleaner"],
        "synonyms": ["duplicate files", "find duplicates", "find duplicate fil"],
        "risk": "low",
    },
    "read_text_file": {
        "intents": ["read_file", "view_text_file", "display_file_content", "inspect_file"],
        "synonyms": ["read", "view", "cat", "open file"],
        "risk": "low",
    },
    "write_text_file": {
        "intents": ["write_file", "save_text_file", "create_content_in_file"],
        "synonyms": ["write", "save text", "write to file"],
        "risk": "moderate",
    },
    "terminal_execute": {
        "intents": ["run_terminal_command", "execute_cmd", "run_shell", "terminal_command"],
        "synonyms": ["exec", "cmd", "run command", "terminal command", "terminal"],
        "risk": "moderate",
    },
    "execute_and_validate": {
        "intents": ["execute_terminal_and_validate", "run_command_with_checks"],
        "synonyms": ["run and validate", "validated exec"],
        "risk": "moderate",
    },
    "mouse_click": {
        "intents": ["click_element", "left_click"],
        "synonyms": ["click", "left click", "press button"],
        "risk": "low",
    },
    "mouse_right_click": {
        "intents": ["right_click", "context_menu"],
        "synonyms": ["right click", "rightclick", "context menu"],
        "risk": "low",
    },
    "mouse_scroll": {
        "intents": ["scroll_page", "scroll_down", "scroll_up"],
        "synonyms": ["scroll", "scroll down", "scroll up"],
        "risk": "low",
    },
    "type_text": {
        "intents": ["type_text", "enter_text", "write_into_window"],
        "synonyms": ["type", "input text"],
        "risk": "low",
    },
    "press_key": {
        "intents": ["press_keyboard_key", "hit_key", "press_enter"],
        "synonyms": ["press", "hit", "key"],
        "risk": "low",
    },
    "take_screenshot": {
        "intents": ["take_screenshot", "capture_screen", "snapshot"],
        "synonyms": ["screenshot", "capture", "screen grab"],
        "risk": "low",
    },
    "windows_search": {
        "intents": ["windows_search", "search_windows", "start_menu_search", "win_search", "search_app", "windows_button_search"],
        "synonyms": ["windows search", "search windows", "search", "windows button search", "start menu search", "win search", "search app", "find app"],
        "risk": "low",
    },
    "browser_search": {
        "intents": ["browser_search", "google_search", "search_google", "search_on_google", "open_google"],
        "synonyms": ["browser search", "google search", "search google", "search on google", "google"],
        "risk": "low",
    },
    "web_search": {
        "intents": ["search_web", "google_search", "find_online"],
        "synonyms": ["web search", "google", "search the web"],
        "risk": "low",
    },
    "open_url": {
        "intents": ["open_browser_url", "navigate_website", "goto_url"],
        "synonyms": ["browse", "goto", "open url", "navigate"],
        "risk": "low",
    },
    "get_current_desktop_state": {
        "intents": ["get_current_desktop_state", "desktop_state", "current_state", "which_desktop"],
        "synonyms": ["desktop state", "browser state", "which desktop", "current state", "active window state"],
        "risk": "low",
    },
    "browser_search_bar": {
        "intents": ["browser_search_bar", "search_bar", "focus_search_bar", "ctrl_k"],
        "synonyms": ["search bar", "browser search bar", "focus search bar", "ctrl k", "address bar search"],
        "risk": "low",
    },
    "whatsapp_search_and_message": {
        "intents": ["whatsapp_search_and_message", "whatsapp_message", "whatsapp_search", "send_whatsapp"],
        "synonyms": ["whatsapp", "whatsapp search", "whatsapp message", "send whatsapp", "whatsapp contact"],
        "risk": "medium",
    },
    "uia_click_button": {
        "intents": ["uia_click_button", "click_button", "click_like", "click_send", "click_submit"],
        "synonyms": ["click button", "like button", "send button", "submit button", "enter button", "box button"],
        "risk": "low",
    },
    "play_music": {
        "intents": ["play_music", "play_song", "play_media", "play_track", "toggle_play", "music"],
        "synonyms": ["play song", "play music", "play", "play on youtube", "play on spotify", "play video"],
        "risk": "low",
    },
    "click_first_link": {
        "intents": ["click_first_link", "click_below_link", "click_top_link", "click_first_video", "click_result"],
        "synonyms": ["click below link", "click first link", "click below first link", "click top link", "click first video", "click below"],
        "risk": "low",
    },
    "click_ui_content": {
        "intents": ["click_ui_content", "click_content", "click_content_area", "click_box", "click_text", "click_icon"],
        "synonyms": ["click content", "click content area", "click box", "click text", "click icon", "click inside box"],
        "risk": "low",
    },
    "get_system_information": {
        "intents": ["get_system_information", "get_system_info", "cpu_usage", "ram_usage", "system_status", "system_specs"],
        "synonyms": ["system info", "cpu usage", "system information", "ram usage", "memory usage", "battery status", "system specs"],
        "risk": "low",
    },
    "list_running_processes": {
        "intents": ["list_running_processes", "list_processes", "running_processes", "task_list", "check_process"],
        "synonyms": ["list processes", "running processes", "process list", "show processes", "running apps", "tasks"],
        "risk": "low",
    },
    "win32_get_foreground_window": {
        "intents": ["win32_get_foreground_window", "active_window", "foreground_window", "focused_window"],
        "synonyms": ["active window", "foreground window", "focused window", "current window"],
        "risk": "low",
    },
    "win32_enum_windows": {
        "intents": ["win32_enum_windows", "list_windows", "show_windows"],
        "synonyms": ["list windows", "show windows", "open windows", "all windows"],
        "risk": "low",
    },
}

# Canonical alias mapping for model hallucinations and informal tool names
CANONICAL_ALIASES: Dict[str, str] = {
    "click_content": "click_ui_content",
    "click_content_area": "click_ui_content",
    "click_box": "click_ui_content",
    "click_text": "click_ui_content",
    "click_icon": "click_ui_content",
    "click_below_link": "click_first_link",
    "click_first_video": "click_first_link",
    "click_top_link": "click_first_link",
    "google_search": "browser_search",
    "macro_browser_search": "browser_search",
    "search_google": "browser_search",
    "google": "browser_search",
    "whatsapp": "whatsapp_search_and_message",
    "whatsapp_search": "whatsapp_search_and_message",
    "whatsapp_message": "whatsapp_search_and_message",
    "whatsapp_serach_message": "whatsapp_search_and_message",
    "whatsapp_search_message": "whatsapp_search_and_message",
    "send_whatsapp": "whatsapp_search_and_message",
    "play_song": "play_music",
    "play_media": "play_music",
    "play_track": "play_music",
    "search_bar": "browser_search_bar",
    "focus_search_bar": "browser_search_bar",
    "current_state": "get_current_desktop_state",
    "desktop_state": "get_current_desktop_state",
    "which_desktop": "get_current_desktop_state",
    "click_button": "uia_click_button",
    "click_like": "uia_click_button",
    "click_send": "uia_click_button",
    "macro_windows_search": "windows_search",
    "win_search": "windows_search",
    "start_menu_search": "windows_search",
    "search_windows": "windows_search",
    "windows_button_search": "windows_search",
    "file_manager_open": "file_explorer_open",
    "open_file_manager": "file_explorer_open",
    "open_file_explorer": "file_explorer_open",
    "explorer_open": "file_explorer_open",
    "file_manager": "file_explorer_open",
    "delete_path": "move_to_recycle_bin",
    "delete_file": "move_to_recycle_bin",
    "remove_file": "move_to_recycle_bin",
    "trash_file": "move_to_recycle_bin",
    "trash": "move_to_recycle_bin",
    "make_directory": "create_directory",
    "mkdir": "create_directory",
    "new_folder": "create_directory",
    "touch": "create_file",
    "make_file": "create_file",
    "new_file": "create_file",
    "find_files": "search_files",
    "locate_file": "search_files",
    "search_directory": "search_files",
    "find_file": "search_files",
    "change_filename": "rename_path",
    "rename_file": "rename_path",
    "rename_folder": "rename_path",
    "execute_command": "terminal_execute",
    "run_terminal": "terminal_execute",
    "run_command": "terminal_execute",
    "shell_exec": "terminal_execute",
    "bash": "terminal_execute",
    "powershell": "terminal_execute",
    "cmd": "terminal_execute",
    "undo": "undo_supported_file_operation",
    "revert_file_operation": "undo_supported_file_operation",
    "undo_operation": "undo_supported_file_operation",
    "show_files": "list_directory",
    "dir": "list_directory",
    "ls": "list_directory",
    "list_folder": "list_directory",
    "find_duplicates": "find_duplicate_files",
    "find_duplicate_file": "find_duplicate_files",
    "duplicate_files": "find_duplicate_files",
    "read_file": "read_text_file",
    "view_file": "read_text_file",
    "cat": "read_text_file",
    "write_file": "write_text_file",
    "right_click": "mouse_right_click",
    "scroll": "mouse_scroll",
    "scroll_down": "mouse_scroll",
    "scroll_up": "mouse_scroll",
    "get_system_info": "get_system_information",
    "system_info": "get_system_information",
    "cpu_usage": "get_system_information",
    "ram_usage": "get_system_information",
    "memory_usage": "get_system_information",
    "list_processes": "list_running_processes",
    "running_processes": "list_running_processes",
    "process_list": "list_running_processes",
    "active_window": "win32_get_foreground_window",
    "foreground_window": "win32_get_foreground_window",
    "enum_windows": "win32_enum_windows",
    "list_windows": "win32_enum_windows",
}


def get_canonical_tool_record(tool_name: str) -> Optional[CanonicalToolRecord]:
    """Retrieve full canonical metadata for a registered tool."""
    canonical_name = CANONICAL_ALIASES.get(tool_name, tool_name)
    if canonical_name not in tool_bus.tools:
        return None

    tool_def: ToolDefinition = tool_bus.tools[canonical_name]
    ext = TOOL_METADATA_EXTENSIONS.get(canonical_name, {})

    # Extract required / optional parameters from schema
    raw_schema = tool_def.input_schema or {}
    if raw_schema.get("type") == "object" and "properties" in raw_schema:
        properties = raw_schema.get("properties", {})
        required = raw_schema.get("required", [])
        optional = [p for p in properties if p not in required]
    else:
        properties = raw_schema
        required = []
        optional = []
        for p_name, p_info in properties.items():
            if isinstance(p_info, dict):
                desc = p_info.get("description", "")
                if "optional" in desc.lower() or p_info.get("default", ...) is not ...:
                    optional.append(p_name)
                else:
                    required.append(p_name)
            else:
                required.append(p_name)

    # Determine risk from permission level or extension override
    risk = ext.get("risk")
    if not risk:
        if tool_def.permission_level in (PermissionLevel.SENSITIVE, PermissionLevel.DESTRUCTIVE):
            risk = "sensitive"
        elif tool_def.permission_level == PermissionLevel.ACTION:
            risk = "moderate"
        else:
            risk = "low"

    return CanonicalToolRecord(
        name=canonical_name,
        description=tool_def.description,
        category=tool_def.category.lower(),
        intents=ext.get("intents", [canonical_name]),
        synonyms=ext.get("synonyms", []),
        argument_schema=properties,
        required_arguments=required,
        optional_arguments=optional,
        risk=risk,
        available=(canonical_name not in getattr(tool_bus, "disabled_tools", set())),
    )


def _ensure_tools_registered():
    if not tool_bus.tools:
        try:
            from app.tools.registry import register_all_tools
            register_all_tools()
        except Exception:
            pass


def get_canonical_registry(only_available: bool = False) -> Dict[str, CanonicalToolRecord]:
    """Get authoritative dictionary of all currently registered tools."""
    _ensure_tools_registered()
    registry: Dict[str, CanonicalToolRecord] = {}
    for name in tool_bus.tools.keys():
        record = get_canonical_tool_record(name)
        if record:
            if only_available and not record.available:
                continue
            registry[record.name] = record
    return registry


def resolve_canonical_tool_name(tool_or_alias: str) -> Optional[str]:
    """Resolve an informal or model-hallucinated function name to canonical registered name."""
    _ensure_tools_registered()
    clean = tool_or_alias.strip().lower()
    if clean in tool_bus.tools:
        return clean
    if clean in CANONICAL_ALIASES and CANONICAL_ALIASES[clean] in tool_bus.tools:
        return CANONICAL_ALIASES[clean]
    # Check underscore variations (e.g. "open-app" or "open app")
    normalized = clean.replace("-", "_").replace(" ", "_")
    if normalized in tool_bus.tools:
        return normalized
    if normalized in CANONICAL_ALIASES and CANONICAL_ALIASES[normalized] in tool_bus.tools:
        return CANONICAL_ALIASES[normalized]
    return None

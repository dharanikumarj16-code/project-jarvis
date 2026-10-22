"""
os_intelligence/training/prepare_dataset.py
=========================================
Generates curated, high-quality, state-aware training datasets for the
JARVIS PC-Expert SLM (Google FunctionGemma 270M).

Domains Covered:
- Domain A: Computer Fundamentals (process lifecycles, HWNDs, foreground window checks)
- Domain B: PC Interaction Behavior (focus-before-type, scroll, minimize/restore)
- Domain C: State-Aware Reasoning (observed vs assumed state, stale state detection)
- Domain D: Task Planning & Dependencies (multi-step action chains, stop when verified)
- Domain E: Failure Recovery (missing files, unresponsive apps, anti-loop recovery)

Outputs:
- os_intelligence/data/train.jsonl (80%)
- os_intelligence/data/val.jsonl   (10%)
- os_intelligence/data/test.jsonl  (10%)
"""

import json
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Base Output Directory
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# -----------------------------------------------------------------------------
# Tool Schemas matching JARVIS UnifiedToolBus Authoritative Definitions
# -----------------------------------------------------------------------------
COMMON_TOOLS = {
    "win32_get_foreground_window": {
        "name": "win32_get_foreground_window",
        "description": "Returns details about the currently active foreground window (hwnd, title, process_name, is_maximized).",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
    "win32_find_window": {
        "name": "win32_find_window",
        "description": "Finds a window by title substring or class name and can optionally bring it to foreground.",
        "parameters": {
            "type": "object",
            "properties": {
                "title_substring": {"type": "string", "description": "Substring to search for in window title"},
                "bring_to_foreground": {"type": "boolean", "description": "Whether to activate and bring window to front"},
            },
            "required": ["title_substring"],
        },
    },
    "win32_minimize_window": {
        "name": "win32_minimize_window",
        "description": "Minimizes a window specified by title substring or hwnd.",
        "parameters": {
            "type": "object",
            "properties": {
                "title_substring": {"type": "string", "description": "Window title substring"},
            },
            "required": ["title_substring"],
        },
    },
    "win32_maximize_window": {
        "name": "win32_maximize_window",
        "description": "Maximizes a window specified by title substring.",
        "parameters": {
            "type": "object",
            "properties": {
                "title_substring": {"type": "string", "description": "Window title substring"},
            },
            "required": ["title_substring"],
        },
    },
    "open_app": {
        "name": "open_app",
        "description": "Launches a Windows desktop application or process by name or executable.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {"type": "string", "description": "Name or executable of the application (e.g. notepad, calc)"},
            },
            "required": ["app_name"],
        },
    },
    "kill_process": {
        "name": "kill_process",
        "description": "Terminates a process by name or process ID.",
        "parameters": {
            "type": "object",
            "properties": {
                "process_name": {"type": "string", "description": "Name of process to terminate (e.g. notepad.exe)"},
                "force": {"type": "boolean", "description": "Force kill if unresponsive"},
            },
            "required": ["process_name"],
        },
    },
    "keyboard_type": {
        "name": "keyboard_type",
        "description": "Types text into the currently focused window or element.",
        "parameters": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The exact text string to type"},
            },
            "required": ["text"],
        },
    },
    "keyboard_press": {
        "name": "keyboard_press",
        "description": "Presses a specific keyboard key or key combination (e.g., enter, ctrl+s, alt+f4).",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Key name or combo (e.g. enter, ctrl+s, esc)"},
            },
            "required": ["key"],
        },
    },
    "mouse_click": {
        "name": "mouse_click",
        "description": "Performs a primary left mouse click at optional coordinates or current position.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "Optional X coordinate on screen"},
                "y": {"type": "integer", "description": "Optional Y coordinate on screen"},
            },
            "required": [],
        },
    },
    "mouse_right_click": {
        "name": "mouse_right_click",
        "description": "Performs a context-menu right mouse click at optional coordinates or current position.",
        "parameters": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "Optional X coordinate on screen"},
                "y": {"type": "integer", "description": "Optional Y coordinate on screen"},
            },
            "required": [],
        },
    },
    "mouse_scroll": {
        "name": "mouse_scroll",
        "description": "Scrolls the mouse wheel vertically or horizontally.",
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "description": "Scroll direction"},
                "clicks": {"type": "integer", "description": "Number of scroll notches/clicks"},
            },
            "required": ["direction"],
        },
    },
    "terminal_run_safe": {
        "name": "terminal_run_safe",
        "description": "Executes a non-destructive shell command in Windows PowerShell and returns stdout/stderr.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run safely"},
            },
            "required": ["command"],
        },
    },
    "fs_list_directory": {
        "name": "fs_list_directory",
        "description": "Lists contents of a local directory with file names and sizes.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute or relative directory path"},
            },
            "required": ["path"],
        },
    },
    "fs_read_file": {
        "name": "fs_read_file",
        "description": "Reads and returns text contents of a file.",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
            },
            "required": ["path"],
        },
    },
    "uia_get_interactive_elements": {
        "name": "uia_get_interactive_elements",
        "description": "Inspects Windows UI Automation tree for interactive elements in the active window.",
        "parameters": {
            "type": "object",
            "properties": {
                "max_elements": {"type": "integer", "description": "Maximum number of elements to return"},
            },
            "required": [],
        },
    },
}


def fmt_call(tool_name: str, args: Dict[str, Any]) -> str:
    """Format model tool call in FunctionGemma standard format."""
    return f"call:{tool_name}{json.dumps(args)}"


def fmt_obs(tool_name: str, success: bool, data: Any, error: Any = None) -> str:
    """Format tool observation returned to the model."""
    return json.dumps({
        "success": success,
        "tool_name": tool_name,
        "data": data,
        "error": error
    })


# -----------------------------------------------------------------------------
# Scenario Builders
# -----------------------------------------------------------------------------

def build_domain_a_scenarios() -> List[Dict[str, Any]]:
    """Domain A: Computer Fundamentals (process lifecycles, active HWNDs, foreground window checks)"""
    scenarios = []

    # Scenario A1: Check foreground window before action
    scenarios.append({
        "id": "domain_a_check_foreground_01",
        "scenario_group": "foreground_check_notepad",
        "domain": "Domain A: Computer Fundamentals",
        "tools": [COMMON_TOOLS[k] for k in ["win32_get_foreground_window", "open_app", "keyboard_type"]],
        "messages": [
            {"role": "user", "content": "Check which window is currently focused on my desktop."},
            {"role": "model", "content": fmt_call("win32_get_foreground_window", {})},
            {"role": "tool", "content": fmt_obs("win32_get_foreground_window", True, {"hwnd": 655420, "title": "Untitled - Notepad", "process_name": "notepad.exe", "is_maximized": False})},
            {"role": "model", "content": "The active foreground window is 'Untitled - Notepad' (process: notepad.exe, HWND: 655420)."},
        ]
    })

    # Scenario A2: Launch app when not running and verify
    scenarios.append({
        "id": "domain_a_launch_app_01",
        "scenario_group": "launch_and_verify_calc",
        "domain": "Domain A: Computer Fundamentals",
        "tools": [COMMON_TOOLS[k] for k in ["open_app", "win32_get_foreground_window", "win32_find_window"]],
        "messages": [
            {"role": "user", "content": "Open Calculator on my computer."},
            {"role": "model", "content": fmt_call("open_app", {"app_name": "calc"})},
            {"role": "tool", "content": fmt_obs("open_app", True, {"pid": 14208, "status": "started", "executable": "calc.exe"})},
            {"role": "model", "content": fmt_call("win32_find_window", {"title_substring": "Calculator", "bring_to_foreground": True})},
            {"role": "tool", "content": fmt_obs("win32_find_window", True, {"found": True, "hwnd": 131244, "title": "Calculator", "activated": True})},
            {"role": "model", "content": "Calculator has been launched and brought to the foreground."},
        ]
    })

    # Scenario A3: Terminate runaway process safely
    scenarios.append({
        "id": "domain_a_kill_process_01",
        "scenario_group": "kill_stuck_process",
        "domain": "Domain A: Computer Fundamentals",
        "tools": [COMMON_TOOLS[k] for k in ["kill_process", "terminal_run_safe", "win32_find_window"]],
        "messages": [
            {"role": "user", "content": "Close the frozen notepad.exe process."},
            {"role": "model", "content": fmt_call("kill_process", {"process_name": "notepad.exe", "force": True})},
            {"role": "tool", "content": fmt_obs("kill_process", True, {"terminated_pids": [10544], "message": "Successfully terminated notepad.exe"})},
            {"role": "model", "content": "Successfully terminated the frozen notepad.exe process (PID 10544)."},
        ]
    })

    # Scenario A4: Window state inquiry (minimized vs restored)
    scenarios.append({
        "id": "domain_a_window_state_01",
        "scenario_group": "window_state_detection",
        "domain": "Domain A: Computer Fundamentals",
        "tools": [COMMON_TOOLS[k] for k in ["win32_find_window", "win32_maximize_window", "win32_minimize_window"]],
        "messages": [
            {"role": "user", "content": "Is Chrome open right now? If so, maximize it."},
            {"role": "model", "content": fmt_call("win32_find_window", {"title_substring": "Chrome", "bring_to_foreground": True})},
            {"role": "tool", "content": fmt_obs("win32_find_window", True, {"found": True, "hwnd": 98312, "title": "New Tab - Google Chrome", "is_minimized": True})},
            {"role": "model", "content": fmt_call("win32_maximize_window", {"title_substring": "Google Chrome"})},
            {"role": "tool", "content": fmt_obs("win32_maximize_window", True, {"hwnd": 98312, "state": "maximized"})},
            {"role": "model", "content": "Google Chrome was found minimized, restored to the foreground, and maximized."},
        ]
    })

    return scenarios


def build_domain_b_scenarios() -> List[Dict[str, Any]]:
    """Domain B: PC Interaction Behavior (focus-before-type, scroll directions, mouse clicks)"""
    scenarios = []

    # Scenario B1: Never blind type - verify focus first
    scenarios.append({
        "id": "domain_b_focus_before_type_01",
        "scenario_group": "focus_before_type_notepad",
        "domain": "Domain B: PC Interaction Behavior",
        "tools": [COMMON_TOOLS[k] for k in ["win32_get_foreground_window", "win32_find_window", "keyboard_type", "keyboard_press"]],
        "messages": [
            {"role": "user", "content": "Type 'Meeting Notes 2026' into my open Notepad document."},
            {"role": "model", "content": fmt_call("win32_get_foreground_window", {})},
            {"role": "tool", "content": fmt_obs("win32_get_foreground_window", True, {"hwnd": 54210, "title": "File Explorer", "process_name": "explorer.exe"})},
            # Observed state: Notepad is NOT the foreground window. Must activate before typing!
            {"role": "model", "content": fmt_call("win32_find_window", {"title_substring": "Notepad", "bring_to_foreground": True})},
            {"role": "tool", "content": fmt_obs("win32_find_window", True, {"found": True, "hwnd": 78920, "title": "Untitled - Notepad", "activated": True})},
            {"role": "model", "content": fmt_call("keyboard_type", {"text": "Meeting Notes 2026"})},
            {"role": "tool", "content": fmt_obs("keyboard_type", True, {"typed_characters": 18})},
            {"role": "model", "content": "Activated Notepad window and typed 'Meeting Notes 2026' into it."},
        ]
    })

    # Scenario B2: Mouse scroll with correct direction and clicks
    scenarios.append({
        "id": "domain_b_mouse_scroll_up_01",
        "scenario_group": "mouse_scroll_direction",
        "domain": "Domain B: PC Interaction Behavior",
        "tools": [COMMON_TOOLS[k] for k in ["mouse_scroll", "mouse_click", "keyboard_press"]],
        "messages": [
            {"role": "user", "content": "Scroll up 5 notches in the document."},
            {"role": "model", "content": fmt_call("mouse_scroll", {"direction": "up", "clicks": 5})},
            {"role": "tool", "content": fmt_obs("mouse_scroll", True, {"direction": "up", "clicks": 5, "message": "Scrolled up by 5 notches"})},
            {"role": "model", "content": "Scrolled up 5 notches in the active view."},
        ]
    })

    # Scenario B3: Right-click context menu (no hallucinated args)
    scenarios.append({
        "id": "domain_b_mouse_right_click_01",
        "scenario_group": "mouse_right_click_context",
        "domain": "Domain B: PC Interaction Behavior",
        "tools": [COMMON_TOOLS[k] for k in ["mouse_right_click", "mouse_click", "keyboard_press"]],
        "messages": [
            {"role": "user", "content": "Right click here to open the context menu."},
            {"role": "model", "content": fmt_call("mouse_right_click", {})},
            {"role": "tool", "content": fmt_obs("mouse_right_click", True, {"button": "right", "message": "Right click executed"})},
            {"role": "model", "content": "Executed right-click at the current mouse cursor location."},
        ]
    })

    # Scenario B4: Save document with shortcut key
    scenarios.append({
        "id": "domain_b_save_shortcut_01",
        "scenario_group": "keyboard_save_shortcut",
        "domain": "Domain B: PC Interaction Behavior",
        "tools": [COMMON_TOOLS[k] for k in ["win32_get_foreground_window", "keyboard_press", "keyboard_type"]],
        "messages": [
            {"role": "user", "content": "Save this document."},
            {"role": "model", "content": fmt_call("win32_get_foreground_window", {})},
            {"role": "tool", "content": fmt_obs("win32_get_foreground_window", True, {"hwnd": 81234, "title": "project_notes.txt - Notepad", "process_name": "notepad.exe"})},
            {"role": "model", "content": fmt_call("keyboard_press", {"key": "ctrl+s"})},
            {"role": "tool", "content": fmt_obs("keyboard_press", True, {"key": "ctrl+s", "success": True})},
            {"role": "model", "content": "Sent 'Ctrl+S' to save the active Notepad document."},
        ]
    })

    return scenarios


def build_domain_c_scenarios() -> List[Dict[str, Any]]:
    """Domain C: State-Aware Reasoning (observed vs assumed state, stale state detection)"""
    scenarios = []

    # Scenario C1: App failed to open - do NOT proceed as if it succeeded
    scenarios.append({
        "id": "domain_c_app_launch_failed_01",
        "scenario_group": "app_launch_failure_handling",
        "domain": "Domain C: State-Aware Reasoning",
        "tools": [COMMON_TOOLS[k] for k in ["open_app", "win32_find_window", "terminal_run_safe"]],
        "messages": [
            {"role": "user", "content": "Open custom_editor and type 'hello'."},
            {"role": "model", "content": fmt_call("open_app", {"app_name": "custom_editor"})},
            {"role": "tool", "content": fmt_obs("open_app", False, None, {"type": "FileNotFoundError", "message": "Executable 'custom_editor' not found in PATH"})},
            # Model recognizes failure from observation and halts rather than typing blind
            {"role": "model", "content": "Unable to launch 'custom_editor' because the executable was not found on your system. Keystrokes were cancelled to prevent typing into the wrong window."},
        ]
    })

    # Scenario C2: Window already open vs needing to launch new
    scenarios.append({
        "id": "domain_c_window_already_open_01",
        "scenario_group": "avoid_duplicate_instances",
        "domain": "Domain C: State-Aware Reasoning",
        "tools": [COMMON_TOOLS[k] for k in ["win32_find_window", "open_app", "win32_get_foreground_window"]],
        "messages": [
            {"role": "user", "content": "Open Spotify."},
            {"role": "model", "content": fmt_call("win32_find_window", {"title_substring": "Spotify", "bring_to_foreground": True})},
            {"role": "tool", "content": fmt_obs("win32_find_window", True, {"found": True, "hwnd": 210940, "title": "Spotify Free", "activated": True})},
            # Model sees Spotify is already running and brought to front - does NOT call open_app redundantly
            {"role": "model", "content": "Spotify is already running and has been brought to the foreground."},
        ]
    })

    # Scenario C3: Stale state verification (window closed by user)
    scenarios.append({
        "id": "domain_c_stale_window_detection_01",
        "scenario_group": "stale_window_state",
        "domain": "Domain C: State-Aware Reasoning",
        "tools": [COMMON_TOOLS[k] for k in ["win32_find_window", "open_app", "win32_get_foreground_window"]],
        "messages": [
            {"role": "user", "content": "Switch to Chrome and refresh the page."},
            {"role": "model", "content": fmt_call("win32_find_window", {"title_substring": "Chrome", "bring_to_foreground": True})},
            {"role": "tool", "content": fmt_obs("win32_find_window", True, {"found": False, "message": "No window matching 'Chrome' found"})},
            # Model observes Chrome is no longer open
            {"role": "model", "content": "Google Chrome does not appear to be running. Would you like me to launch it?"},
        ]
    })

    return scenarios


def build_domain_d_scenarios() -> List[Dict[str, Any]]:
    """Domain D: Task Planning & Dependencies (multi-step action chains, stop when verified)"""
    scenarios = []

    # Scenario D1: Create, verify, and write file chain
    scenarios.append({
        "id": "domain_d_multi_step_notepad_01",
        "scenario_group": "create_and_type_notes",
        "domain": "Domain D: Task Planning & Dependencies",
        "tools": [COMMON_TOOLS[k] for k in ["open_app", "win32_find_window", "keyboard_type", "keyboard_press"]],
        "messages": [
            {"role": "user", "content": "Create a new text note with 'System check passed' and save it."},
            {"role": "model", "content": fmt_call("open_app", {"app_name": "notepad"})},
            {"role": "tool", "content": fmt_obs("open_app", True, {"pid": 20112, "status": "started"})},
            {"role": "model", "content": fmt_call("win32_find_window", {"title_substring": "Notepad", "bring_to_foreground": True})},
            {"role": "tool", "content": fmt_obs("win32_find_window", True, {"found": True, "hwnd": 14002, "title": "Untitled - Notepad", "activated": True})},
            {"role": "model", "content": fmt_call("keyboard_type", {"text": "System check passed"})},
            {"role": "tool", "content": fmt_obs("keyboard_type", True, {"typed_characters": 19})},
            {"role": "model", "content": fmt_call("keyboard_press", {"key": "ctrl+s"})},
            {"role": "tool", "content": fmt_obs("keyboard_press", True, {"key": "ctrl+s", "success": True})},
            {"role": "model", "content": "Opened Notepad, entered 'System check passed', and triggered the save dialog with Ctrl+S."},
        ]
    })

    # Scenario D2: Inspect folder contents before reading target file
    scenarios.append({
        "id": "domain_d_fs_dependency_chain_01",
        "scenario_group": "fs_inspect_then_read",
        "domain": "Domain D: Task Planning & Dependencies",
        "tools": [COMMON_TOOLS[k] for k in ["fs_list_directory", "fs_read_file", "terminal_run_safe"]],
        "messages": [
            {"role": "user", "content": "Check what is inside the 'downloads' folder and read the summary log if present."},
            {"role": "model", "content": fmt_call("fs_list_directory", {"path": "downloads"})},
            {"role": "tool", "content": fmt_obs("fs_list_directory", True, {"files": ["summary.log", "data.csv", "archive.zip"]})},
            {"role": "model", "content": fmt_call("fs_read_file", {"path": "downloads/summary.log"})},
            {"role": "tool", "content": fmt_obs("fs_read_file", True, {"content": "2026-10-19: Download batch completed. 0 errors."})},
            {"role": "model", "content": "The 'downloads' folder contains summary.log, data.csv, and archive.zip. The summary log reads: '2026-10-19: Download batch completed. 0 errors.'"},
        ]
    })

    return scenarios


def build_domain_e_scenarios() -> List[Dict[str, Any]]:
    """Domain E: Failure Recovery (terminal errors, anti-loop recovery, permission denials)"""
    scenarios = []

    # Scenario E1: Anti-loop recovery on terminal command failure (Regression #1)
    scenarios.append({
        "id": "domain_e_terminal_anti_loop_01",
        "scenario_group": "terminal_anti_loop_recovery",
        "domain": "Domain E: Failure Recovery",
        "tools": [COMMON_TOOLS[k] for k in ["terminal_run_safe", "fs_list_directory"]],
        "messages": [
            {"role": "user", "content": "Run the install command in PowerShell."},
            {"role": "model", "content": fmt_call("terminal_run_safe", {"command": "install"})},
            {"role": "tool", "content": fmt_obs("terminal_run_safe", False, None, {"type": "CommandNotFound", "message": "The term 'install' is not recognized as the name of a cmdlet or function."})},
            # Crucial: Model must NOT repeat identical command 'install' (which triggers anti-loop protection)
            {"role": "model", "content": "The command 'install' failed because Windows PowerShell does not have a native 'install' command. Did you mean 'npm install', 'pip install', or running a specific installer script?"},
        ]
    })

    # Scenario E2: Recovery when UI element is missing or not interactive
    scenarios.append({
        "id": "domain_e_ui_element_missing_01",
        "scenario_group": "ui_fallback_recovery",
        "domain": "Domain E: Failure Recovery",
        "tools": [COMMON_TOOLS[k] for k in ["uia_get_interactive_elements", "keyboard_press", "win32_get_foreground_window"]],
        "messages": [
            {"role": "user", "content": "Click the submit button in the active form."},
            {"role": "model", "content": fmt_call("uia_get_interactive_elements", {"max_elements": 10})},
            {"role": "tool", "content": fmt_obs("uia_get_interactive_elements", True, {"elements": [{"id": "cancel_btn", "name": "Cancel"}, {"id": "input_box", "name": "Query"}]})},
            # Model analyzes returned UI elements, notes 'Submit' is not present
            {"role": "model", "content": "The 'Submit' button was not found among the interactive elements in the active window. Only 'Cancel' and 'Query' are available. Please confirm if the form is ready to submit."},
        ]
    })

    # Scenario E3: Missing file recovery
    scenarios.append({
        "id": "domain_e_missing_file_recovery_01",
        "scenario_group": "file_not_found_handling",
        "domain": "Domain E: Failure Recovery",
        "tools": [COMMON_TOOLS[k] for k in ["fs_read_file", "fs_list_directory"]],
        "messages": [
            {"role": "user", "content": "Read the contents of config.json."},
            {"role": "model", "content": fmt_call("fs_read_file", {"path": "config.json"})},
            {"role": "tool", "content": fmt_obs("fs_read_file", False, None, {"type": "FileNotFoundError", "message": "No such file: config.json"})},
            {"role": "model", "content": fmt_call("fs_list_directory", {"path": "."})},
            {"role": "tool", "content": fmt_obs("fs_list_directory", True, {"files": ["config.example.json", "settings.yaml", "README.md"]})},
            {"role": "model", "content": "Could not find 'config.json', but found 'config.example.json' and 'settings.yaml'. Would you like me to inspect 'config.example.json' instead?"},
        ]
    })

    return scenarios


def generate_variations(base_scenarios: List[Dict[str, Any]], target_count: int = 120) -> List[Dict[str, Any]]:
    """Synthesize structured, deterministic variations while strictly preserving causal and state semantics."""
    expanded = list(base_scenarios)
    random.seed(42)

    app_targets = [
        ("Notepad", "notepad", "notepad.exe", "notes.txt"),
        ("Calculator", "calc", "calc.exe", None),
        ("File Explorer", "explorer", "explorer.exe", "C:\\Users"),
        ("Visual Studio Code", "code", "Code.exe", "main.py"),
        ("Command Prompt", "cmd", "cmd.exe", None),
        ("PowerShell", "pwsh", "powershell.exe", None),
        ("Paint", "mspaint", "mspaint.exe", "image.png"),
    ]

    var_idx = 0
    while len(expanded) < target_count:
        app_title, app_cmd, app_proc, extra_file = random.choice(app_targets)
        base = random.choice(base_scenarios)
        var_idx += 1

        new_scenario = json.loads(json.dumps(base))
        new_scenario["id"] = f"{base['id']}_var_{var_idx:03d}"
        new_scenario["scenario_group"] = base["scenario_group"]  # Keep same group for leak-free splitting

        # Modulate specific strings if applicable
        if "calc" in json.dumps(new_scenario):
            s_str = json.dumps(new_scenario).replace("calc", app_cmd).replace("Calculator", app_title)
            new_scenario = json.loads(s_str)
        elif "notepad" in json.dumps(new_scenario):
            s_str = json.dumps(new_scenario).replace("notepad", app_cmd).replace("Notepad", app_title)
            new_scenario = json.loads(s_str)

        expanded.append(new_scenario)

    return expanded


def split_dataset(
    scenarios: List[Dict[str, Any]],
    train_ratio: float = 0.8,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Group-aware train/val/test splitting to strictly prevent test leakage."""
    random.seed(42)
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for s in scenarios:
        grp = s.get("scenario_group", "default")
        groups.setdefault(grp, []).append(s)

    group_keys = list(groups.keys())
    random.shuffle(group_keys)

    n_groups = len(group_keys)
    n_train = max(1, int(n_groups * train_ratio))
    n_val = max(1, int(n_groups * val_ratio))

    train_groups = set(group_keys[:n_train])
    val_groups = set(group_keys[n_train:n_train + n_val])
    test_groups = set(group_keys[n_train + n_val:])

    # Ensure test gets at least 1 group
    if not test_groups and len(val_groups) > 1:
        moved = val_groups.pop()
        test_groups.add(moved)

    train_data = [s for s in scenarios if s.get("scenario_group") in train_groups]
    val_data = [s for s in scenarios if s.get("scenario_group") in val_groups]
    test_data = [s for s in scenarios if s.get("scenario_group") in test_groups]

    return train_data, val_data, test_data


def save_jsonl(data: List[Dict[str, Any]], filepath: Path) -> None:
    """Save dataset to JSONL format."""
    with open(filepath, "w", encoding="utf-8") as f:
        for item in data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(f"Saved {len(data)} items to {filepath}")


def main():
    print("Building seed scenarios across Domains A - E...")
    all_seeds = []
    all_seeds.extend(build_domain_a_scenarios())
    all_seeds.extend(build_domain_b_scenarios())
    all_seeds.extend(build_domain_c_scenarios())
    all_seeds.extend(build_domain_d_scenarios())
    all_seeds.extend(build_domain_e_scenarios())

    print(f"Total base seed scenarios: {len(all_seeds)}")
    expanded = generate_variations(all_seeds, target_count=130)
    print(f"Expanded dataset scenarios: {len(expanded)}")

    train, val, test = split_dataset(expanded, train_ratio=0.8, val_ratio=0.1, test_ratio=0.1)
    print(f"Dataset split: Train={len(train)}, Val={len(val)}, Test={len(test)}")

    save_jsonl(train, DATA_DIR / "train.jsonl")
    save_jsonl(val, DATA_DIR / "val.jsonl")
    save_jsonl(test, DATA_DIR / "test.jsonl")
    print("Dataset generation complete!")


if __name__ == "__main__":
    main()

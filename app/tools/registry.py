from app.tools.bus import tool_bus, ToolDefinition
from app.permissions import PermissionLevel
import json

def register_all_tools(mcp_client=None):
    # System Information
    from app.tools.system import get_system_info, take_screenshot
    tool_bus.register_tool(
        ToolDefinition(
            name="get_system_information",
            description="Retrieve system information like CPU, RAM, Disk, OS, and battery.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="SYSTEM"
        ),
        get_system_info
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="system_take_screenshot",
            description="Take a screenshot of the entire computer screen and save it to a file on the desktop. Do NOT use this for web browsing snapshots.",
            input_schema={"filename": {"type": "string", "description": "Optional filename, defaults to screenshot.png"}},
            permission_level=PermissionLevel.READ,
            category="SYSTEM"
        ),
        lambda filename="screenshot.png", **kwargs: take_screenshot(filename)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="take_screenshot",
            description="Take a screenshot of the entire computer screen and save it to a file on the desktop.",
            input_schema={"filename": {"type": "string", "description": "Optional filename, defaults to screenshot.png"}},
            permission_level=PermissionLevel.READ,
            category="SYSTEM"
        ),
        lambda filename="screenshot.png", **kwargs: take_screenshot(filename)
    )

    # Audio & Power Management
    from app.tools.system import mute_audio, set_volume, system_sleep, system_shutdown, system_restart
    tool_bus.register_tool(
        ToolDefinition(
            name="mute_audio",
            description="Toggle system audio mute.",
            input_schema={},
            permission_level=PermissionLevel.ACTION,
            category="SYSTEM"
        ),
        mute_audio
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="set_volume",
            description="Set system volume level (0-100).",
            input_schema={"level": {"type": "integer"}},
            permission_level=PermissionLevel.ACTION,
            category="SYSTEM"
        ),
        lambda level=50, **kwargs: set_volume(level)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="system_sleep",
            description="Put the system into sleep state.",
            input_schema={},
            permission_level=PermissionLevel.ACTION,
            category="SYSTEM"
        ),
        system_sleep
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="system_shutdown",
            description="Schedule system shutdown.",
            input_schema={"delay_seconds": {"type": "integer"}},
            permission_level=PermissionLevel.SENSITIVE,
            category="SYSTEM"
        ),
        lambda delay_seconds=60, **kwargs: system_shutdown(delay_seconds)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="system_restart",
            description="Schedule system restart.",
            input_schema={"delay_seconds": {"type": "integer"}},
            permission_level=PermissionLevel.SENSITIVE,
            category="SYSTEM"
        ),
        lambda delay_seconds=60, **kwargs: system_restart(delay_seconds)
    )

    # WiFi Diagnostics
    from app.tools.implementations.wifi_tool import WifiNetworksTool
    tool_bus.register_tool(WifiNetworksTool())

    # Speech / Audio
    def _speak_text_executor(text: str, **kwargs):
        try:
            from app.voice.tts import TTSManager
            tts = TTSManager()
            tts.speak(text)
            return {"success": True, "message": f"Spoke: {text}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    tool_bus.register_tool(
        ToolDefinition(
            name="speak_text",
            description="Speak a message or response aloud to the user using text-to-speech.",
            input_schema={"text": {"type": "string", "description": "Text to speak aloud"}},
            permission_level=PermissionLevel.ACTION,
            category="SYSTEM"
        ),
        _speak_text_executor
    )

    # Local Brain & Ollama Telemetry
    async def _ollama_status_executor(**kwargs):
        from app.local_brain import local_brain
        return await local_brain.check_health()

    tool_bus.register_tool(
        ToolDefinition(
            name="check_ollama_status",
            description="Check local Ollama health, active host endpoint, latency, and available models.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="SYSTEM"
        ),
        _ollama_status_executor
    )

    # Processes
    from app.tools.processes import list_processes, get_process_info, kill_process
    tool_bus.register_tool(
        ToolDefinition(
            name="list_running_processes",
            description="List running processes on the system, optionally filtered by a name.",
            input_schema={"filter_name": {"type": "string", "description": "Optional filter"}},
            permission_level=PermissionLevel.READ,
            category="SYSTEM"
        ),
        list_processes
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="process_info",
            description="Get detailed information about a specific process by its PID.",
            input_schema={"pid": {"type": "integer"}},
            permission_level=PermissionLevel.READ,
            category="SYSTEM"
        ),
        get_process_info
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="kill_process",
            description="Terminate a running process by its PID or process name.",
            input_schema={
                "pid": {"type": "integer", "description": "Optional PID of the process to terminate"},
                "name": {"type": "string", "description": "Optional name of the process to terminate"}
            },
            permission_level=PermissionLevel.SENSITIVE,
            category="SYSTEM"
        ),
        kill_process
    )

    # Terminal
    from app.tools.terminal import (
        terminal_run_safe,
        terminal_run_action,
        terminal_run_sudo,
        terminal_execute,
        execute_and_validate
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="terminal_run_safe",
            description="Run a safe, read-only shell command (e.g., dir, git status). Do not use this for builds or modifications.",
            input_schema={"command": {"type": "string"}, "cwd": {"type": "string", "description": "Optional working directory"}},
            permission_level=PermissionLevel.READ,
            category="TERMINAL",
            timeout_seconds=10
        ),
        terminal_run_safe
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="terminal_run_action",
            description="Run a mutative command, build process, or git action (e.g., npm install, pytest).",
            input_schema={"command": {"type": "string"}, "cwd": {"type": "string", "description": "Optional working directory"}},
            permission_level=PermissionLevel.ACTION,
            category="TERMINAL",
            timeout_seconds=60
        ),
        terminal_run_action
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="terminal_run_sudo",
            description="Run an administrative or highly sensitive shell command. This requires explicit human approval.",
            input_schema={"command": {"type": "string"}, "cwd": {"type": "string", "description": "Optional working directory"}},
            permission_level=PermissionLevel.SENSITIVE,
            category="TERMINAL",
            timeout_seconds=60
        ),
        terminal_run_sudo
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="terminal_execute",
            description="Execute arbitrary terminal commands via PowerShell or CMD and capture stdout, stderr, exit code, and execution time.",
            input_schema={
                "command": {"type": "string", "description": "Command string to execute"},
                "cwd": {"type": "string", "description": "Optional working directory"},
                "timeout": {"type": "integer", "description": "Timeout in seconds, default 30"},
                "shell_type": {"type": "string", "description": "powershell or cmd", "enum": ["powershell", "cmd"]}
            },
            permission_level=PermissionLevel.ACTION,
            category="TERMINAL",
            timeout_seconds=60
        ),
        terminal_execute
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="execute_and_validate",
            description="Execute terminal command and automatically validate output against pattern, exit code, or file changes on disk.",
            input_schema={
                "command": {"type": "string", "description": "Command string to execute"},
                "validation_type": {"type": "string", "enum": ["exit_code", "output_contains", "file_created", "file_deleted", "file_modified"]},
                "expected_pattern": {"type": "string", "description": "Regex or substring to find in stdout/stderr"},
                "check_path": {"type": "string", "description": "Path to verify on disk"},
                "cwd": {"type": "string"},
                "timeout": {"type": "integer"}
            },
            permission_level=PermissionLevel.ACTION,
            category="TERMINAL",
            timeout_seconds=60
        ),
        execute_and_validate
    )

    # Applications
    from app.tools.applications import open_application, is_application_running, get_running_applications, close_application
    tool_bus.register_tool(
        ToolDefinition(
            name="open_app",
            description="Open an approved application. Provide the application name (e.g. 'chrome', 'vscode').",
            input_schema={"application": {"type": "string"}, "app_name": {"type": "string"}},
            permission_level=PermissionLevel.LOW_RISK,
            category="WINDOWS",
            verification_required=True
        ),
        executor=lambda application=None, app_name=None, **kwargs: open_application(app_name or application),
        verifier=lambda application=None, app_name=None, **kwargs: is_application_running(app_name or application)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="close_app",
            description="Close an application by name or window title.",
            input_schema={"app_name": {"type": "string"}, "application": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="WINDOWS"
        ),
        lambda app_name=None, application=None, **kwargs: close_application(app_name or application)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="check_app_running",
            description="Check if a specific application is currently running.",
            input_schema={"application": {"type": "string"}, "app_name": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="WINDOWS"
        ),
        lambda application=None, app_name=None, **kwargs: is_application_running(app_name or application)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="list_running_apps",
            description="Get a list of all recognized running applications.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="WINDOWS"
        ),
        get_running_applications
    )

    # System Window Management (The Eyes)
    from app.tools.computer.windows import WindowsController
    win_ctrl = WindowsController()
    tool_bus.register_tool(
        ToolDefinition(
            name="win_list_visible",
            description="List all visible windows, returning their HWND handles and titles.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="WINDOWS"
        ),
        lambda **kwargs: [{"handle": w.handle, "title": w.title} for w in win_ctrl.list_visible_windows()]
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="win_focus",
            description="Focus a visible window by exactly matching its title.",
            input_schema={"title": {"type": "string"}},
            permission_level=PermissionLevel.LOW_RISK,
            category="WINDOWS"
        ),
        lambda title, **kwargs: {"handle": win_ctrl.focus_exact_title(title).handle, "title": title}
    )

    from app.tools.window_manager import window_focus, window_set_state
    tool_bus.register_tool(
        ToolDefinition(
            name="window_search_and_focus",
            description="Bring a specific window to the foreground by matching a string in its title.",
            input_schema={"title_pattern": {"type": "string"}},
            permission_level=PermissionLevel.LOW_RISK,
            category="WINDOWS"
        ),
        lambda title_pattern, **kwargs: window_focus(title_pattern)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="window_set_state",
            description="Minimize, maximize, restore, or close a specific window by matching its title.",
            input_schema={"title_pattern": {"type": "string"}, "state": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="WINDOWS"
        ),
        lambda title_pattern, state, **kwargs: window_set_state(title_pattern, state)
    )
    from app.tools.window_manager import window_move_resize
    tool_bus.register_tool(
        ToolDefinition(
            name="window_move_resize",
            description="Move and resize a specific window.",
            input_schema={
                "title_pattern": {"type": "string"},
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "width": {"type": "integer"},
                "height": {"type": "integer"}
            },
            permission_level=PermissionLevel.ACTION,
            category="WINDOWS"
        ),
        lambda title_pattern, x, y, width, height, **kwargs: window_move_resize(title_pattern, x, y, width, height)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="maximize_window",
            description="Maximize a specific window by application or title.",
            input_schema={"app_name": {"type": "string"}, "title_pattern": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="WINDOWS"
        ),
        lambda app_name="", title_pattern="", **kwargs: window_set_state(app_name or title_pattern, "maximize")
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="minimize_window",
            description="Minimize a specific window by application or title.",
            input_schema={"app_name": {"type": "string"}, "title_pattern": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="WINDOWS"
        ),
        lambda app_name="", title_pattern="", **kwargs: window_set_state(app_name or title_pattern, "minimize")
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="restore_window",
            description="Restore a specific window by application or title.",
            input_schema={"app_name": {"type": "string"}, "title_pattern": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="WINDOWS"
        ),
        lambda app_name="", title_pattern="", **kwargs: window_set_state(app_name or title_pattern, "restore")
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="focus_window",
            description="Focus a window matching application or title name.",
            input_schema={"app_name": {"type": "string"}, "title_pattern": {"type": "string"}},
            permission_level=PermissionLevel.LOW_RISK,
            category="WINDOWS"
        ),
        lambda app_name="", title_pattern="", **kwargs: window_focus(app_name or title_pattern)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="get_active_window",
            description="Get information about the currently active foreground window.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="WINDOWS"
        ),
        lambda **kwargs: {"handle": win_ctrl.active_window().handle, "title": win_ctrl.active_window().title}
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="close_window",
            description="Close a window matching an application name or title pattern.",
            input_schema={"title_pattern": {"type": "string"}, "app_name": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="WINDOWS"
        ),
        lambda title_pattern="", app_name="", **kwargs: window_set_state(title_pattern or app_name, "close")
    )

    # Input Primitives (The Hands)
    from app.tools.computer.keyboard import KeyboardController
    from app.tools.computer.mouse import MouseController
    kbd = KeyboardController()
    mouse = MouseController()
    
    tool_bus.register_tool(
        ToolDefinition(
            name="keyboard_type",
            description="Type a string of text directly into the focused window.",
            input_schema={"text": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda text="", **kwargs: kbd.type_text(text)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="type_text",
            description="Type a string of text directly into the focused window.",
            input_schema={"text": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda text="", **kwargs: kbd.type_text(text)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="keyboard_hotkey",
            description="Press a combination of keys (e.g. 'ctrl', 'c' or 'win', 'r').",
            input_schema={"keys": {"type": "array", "items": {"type": "string"}}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda keys=[], **kwargs: kbd.hotkey(*keys)
    )
    def _smart_keyboard_press(key="", **kwargs):
        if not key:
            return {"success": False, "error": "No key specified"}
        clean = str(key).strip().casefold()
        
        # 1. Check if semantic shortcut exists (e.g. "task manager", "copy", "close window")
        from app.tools.macros import SHORTCUT_MAP, execute_mapped_shortcut
        if clean in SHORTCUT_MAP:
            return execute_mapped_shortcut(clean)
            
        # 2. Check for multi-key chords separated by '+', ' and ', or spaces
        from app.tools.computer.keyboard import normalize_key, KeyboardController
        kbd_ctrl = KeyboardController()
        keys = None
        if "+" in clean:
            keys = [k.strip() for k in clean.split("+") if k.strip()]
        elif " and " in clean:
            keys = [k.strip() for k in clean.split(" and ") if k.strip()]
        elif " " in clean:
            tokens = [k.strip() for k in clean.split() if k.strip()]
            if len(tokens) >= 2:
                try:
                    normalized = [normalize_key(t) for t in tokens]
                    keys = normalized
                except Exception:
                    keys = None  # Multi-word single key name, e.g. 'window button'
                    
        try:
            if keys and len(keys) >= 2:
                kbd_ctrl.hotkey(*keys)
                return {"success": True, "message": f"Pressed hotkey: {'+'.join(keys)}"}
            else:
                norm = normalize_key(clean)
                kbd_ctrl.press(norm)
                return {"success": True, "message": f"Pressed key: {norm}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    tool_bus.register_tool(
        ToolDefinition(
            name="hotkey",
            description="Press a hotkey combination (e.g. 'ctrl+c', 'alt+f4', 'win+d').",
            input_schema={"key": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        _smart_keyboard_press
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="keyboard_press",
            description="Press a single key or key combination (e.g. 'win', 'enter', 'esc', 'window button').",
            input_schema={"key": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        _smart_keyboard_press
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="press_key",
            description="Press a single key or key combination (e.g. 'win', 'enter', 'esc', 'window button').",
            input_schema={"key": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        _smart_keyboard_press
    )
    def _get_mouse():
        from app.tools.computer.mouse import MouseController
        return MouseController()

    def _parse_mouse_coords(x=None, y=None, target=None, args=None, to=None, **kwargs):
        """Helper to resolve x, y coordinates from numbers, strings, or 'center'."""
        if x is not None and y is not None:
            try:
                return int(round(float(x))), int(round(float(y)))
            except (ValueError, TypeError):
                pass
        for candidate in (target, args, to, x):
            if isinstance(candidate, str):
                c_clean = candidate.strip().casefold()
                if "center" in c_clean:
                    center_pt = _get_mouse().center()
                    return center_pt.x, center_pt.y
                import re
                nums = re.findall(r"\b\d+\b", c_clean)
                if len(nums) >= 2:
                    return int(nums[0]), int(nums[1])
        return None, None

    def _smart_mouse_click(x=None, y=None, button="left", target=None, clicks=1, **kwargs):
        try:
            m_ctrl = _get_mouse()
            rx, ry = _parse_mouse_coords(x=x, y=y, target=target, **kwargs)

            # If no coordinates and a non-empty target text is given (and not "center"), click the UI content area
            if rx is None and ry is None and target and str(target).strip().lower() not in ("center", ""):
                from app.tools.macros import click_ui_content
                content_res = click_ui_content(query=str(target), window_title=kwargs.get("window_title", ""))
                if content_res.get("success"):
                    return content_res

            if isinstance(target, str):
                t_low = target.lower()
                if "right" in t_low:
                    button = "right"
                elif "middle" in t_low:
                    button = "middle"
                if "double" in t_low:
                    clicks = 2

            if clicks == 2:
                m_ctrl.double_click(x=rx, y=ry, button=button)
                desc = f"Double-clicked {button} button"
            elif button == "right":
                m_ctrl.right_click(x=rx, y=ry)
                desc = "Right-clicked"
            else:
                m_ctrl.click(x=rx, y=ry, button=button)
                desc = f"Clicked {button} button"

            pos = m_ctrl.position()
            loc_str = f"at ({rx}, {ry})" if rx is not None else f"at ({pos.x}, {pos.y})"
            return {"success": True, "message": f"{desc} {loc_str}", "position": {"x": pos.x, "y": pos.y}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _smart_mouse_move(x=None, y=None, target=None, args=None, to=None, direction=None, distance=None, duration=0.2, **kwargs):
        try:
            m_ctrl = _get_mouse()
            combined = f"{target or ''} {args or ''} {direction or ''}".lower()

            # Check relative directional moves (up, down, left, right)
            detected_dir = None
            for d in ("up", "down", "left", "right"):
                if d in combined:
                    detected_dir = d
                    break

            if detected_dir:
                import re
                import pyautogui
                nums = re.findall(r"\b\d+\b", combined)
                step = distance if distance is not None else (int(nums[0]) if nums else 100)
                pos = m_ctrl.position()
                dx, dy = 0, 0
                if detected_dir == "up": dy = -abs(step)
                elif detected_dir == "down": dy = abs(step)
                elif detected_dir == "left": dx = -abs(step)
                elif detected_dir == "right": dx = abs(step)

                width, height = pyautogui.size()
                nx = max(0, min(width - 1, pos.x + dx))
                ny = max(0, min(height - 1, pos.y + dy))
                pt = m_ctrl.move(nx, ny, duration=duration)
                return {"success": True, "message": f"Moved mouse {detected_dir} by {step}px to ({pt.x}, {pt.y})", "position": {"x": pt.x, "y": pt.y}, "x": pt.x, "y": pt.y}

            rx, ry = _parse_mouse_coords(x=x, y=y, target=target, args=args, to=to, **kwargs)
            if rx is None or ry is None:
                return {"success": False, "error": "Target coordinates (x, y) or direction (up, down, left, right) required for mouse move"}
            pt = m_ctrl.move(rx, ry, duration=duration)
            return {"success": True, "message": f"Moved mouse to ({pt.x}, {pt.y})", "position": {"x": pt.x, "y": pt.y}, "x": pt.x, "y": pt.y}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _smart_mouse_scroll(clicks=None, direction=None, args=None, **kwargs):
        try:
            m_ctrl = _get_mouse()
            resolved_clicks = None
            for candidate in (clicks, direction, args):
                if candidate is not None:
                    if isinstance(candidate, (int, float)):
                        resolved_clicks = int(candidate)
                        break
                    elif isinstance(candidate, str):
                        c_low = candidate.lower()
                        import re
                        nums = re.findall(r"-?\b\d+\b", c_low)
                        if "down" in c_low:
                            amount = int(nums[0]) if nums else 5
                            resolved_clicks = -abs(amount)
                            break
                        elif "up" in c_low:
                            amount = int(nums[0]) if nums else 5
                            resolved_clicks = abs(amount)
                            break
                        elif nums:
                            resolved_clicks = int(nums[0])
                            break
            if resolved_clicks is None or resolved_clicks == 0:
                resolved_clicks = 5
            m_ctrl.scroll(resolved_clicks)
            direction_str = "up" if resolved_clicks > 0 else "down"
            return {"success": True, "message": f"Scrolled mouse wheel {abs(resolved_clicks)} clicks {direction_str}", "clicks": resolved_clicks}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _smart_mouse_scroll_horizontal(clicks=None, direction=None, args=None, **kwargs):
        try:
            m_ctrl = _get_mouse()
            resolved_clicks = None
            for candidate in (clicks, direction, args):
                if candidate is not None:
                    if isinstance(candidate, (int, float)):
                        resolved_clicks = int(candidate)
                        break
                    elif isinstance(candidate, str):
                        c_low = candidate.lower()
                        import re
                        nums = re.findall(r"-?\b\d+\b", c_low)
                        if "left" in c_low:
                            amount = int(nums[0]) if nums else 5
                            resolved_clicks = -abs(amount)
                            break
                        elif "right" in c_low:
                            amount = int(nums[0]) if nums else 5
                            resolved_clicks = abs(amount)
                            break
                        elif nums:
                            resolved_clicks = int(nums[0])
                            break
            if resolved_clicks is None or resolved_clicks == 0:
                resolved_clicks = 5
            m_ctrl.hscroll(resolved_clicks)
            direction_str = "right" if resolved_clicks > 0 else "left"
            return {"success": True, "message": f"Scrolled horizontally {abs(resolved_clicks)} clicks {direction_str}", "clicks": resolved_clicks}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _smart_mouse_drag(x=None, y=None, target=None, args=None, to=None, button="left", duration=0.5, **kwargs):
        try:
            m_ctrl = _get_mouse()
            rx, ry = _parse_mouse_coords(x=x, y=y, target=target, args=args, to=to, **kwargs)
            if rx is None or ry is None:
                return {"success": False, "error": "Target coordinates (x, y) required for mouse drag"}
            pt = m_ctrl.drag(rx, ry, duration=duration, button=button)
            return {"success": True, "message": f"Dragged mouse to ({pt.x}, {pt.y})", "position": {"x": pt.x, "y": pt.y}}
        except Exception as e:
            return {"success": False, "error": str(e)}

    tool_bus.register_tool(
        ToolDefinition(
            name="mouse_click",
            description="Click the mouse at absolute coordinates (x, y) or at current cursor location.",
            input_schema={
                "x": {"type": "integer"}, 
                "y": {"type": "integer"},
                "button": {"type": "string", "description": "left, right, or middle"},
                "target": {"type": "string", "description": "Optional coordinate string or 'center'"}
            },
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        _smart_mouse_click
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="mouse_move",
            description="Move the mouse smoothly to absolute coordinates (x, y) or relatively in a direction (up, down, left, right by optional distance in pixels).",
            input_schema={
                "x": {"type": "integer", "description": "Absolute X coordinate"},
                "y": {"type": "integer", "description": "Absolute Y coordinate"},
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"], "description": "Direction to move cursor"},
                "distance": {"type": "integer", "description": "Pixels to move in direction (default 100)"},
                "target": {"type": "string", "description": "Coordinate string or directional phrase"}
            },
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        _smart_mouse_move
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="mouse_scroll",
            description="Scroll the mouse wheel up (positive) or down (negative).",
            input_schema={"clicks": {"type": "integer"}, "direction": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        _smart_mouse_scroll
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="mouse_scroll_horizontal",
            description="Scroll the mouse wheel left (negative) or right (positive).",
            input_schema={"clicks": {"type": "integer"}, "direction": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        _smart_mouse_scroll_horizontal
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="mouse_right_click",
            description="Right click the mouse at absolute coordinates, or at current location if x/y omitted.",
            input_schema={
                "x": {"type": "integer"}, 
                "y": {"type": "integer"},
                "target": {"type": "string"}
            },
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda x=None, y=None, target=None, **kwargs: _smart_mouse_click(x=x, y=y, button="right", target=target, **kwargs)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="mouse_double_click",
            description="Double click the mouse at absolute coordinates, or at current location if x/y omitted.",
            input_schema={
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "button": {"type": "string", "description": "left, right, or middle"},
                "target": {"type": "string"}
            },
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda x=None, y=None, button="left", target=None, **kwargs: _smart_mouse_click(x=x, y=y, button=button, clicks=2, target=target, **kwargs)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="mouse_drag",
            description="Click and drag the mouse from current location to target coordinates (x, y).",
            input_schema={
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "button": {"type": "string", "description": "left, right, or middle"}
            },
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        _smart_mouse_drag
    )
    def _smart_get_mouse_position(**kwargs):
        try:
            m_ctrl = _get_mouse()
            pos = m_ctrl.position()
            return {"success": True, "message": f"Cursor at ({pos.x}, {pos.y})", "position": {"x": pos.x, "y": pos.y}, "x": pos.x, "y": pos.y}
        except Exception as e:
            return {"success": False, "error": str(e), "x": 0, "y": 0}

    tool_bus.register_tool(
        ToolDefinition(
            name="mouse_get_position",
            description="Get the current cursor coordinates (x, y) on the screen.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="INPUT"
        ),
        _smart_get_mouse_position
    )

    # Macros / Consolidated Logic
    from app.tools.macros import (
        windows_menu_search, browser_search, mouse_access_logic, execute_mapped_shortcut, SHORTCUT_MAP,
        get_current_desktop_state, browser_search_bar_focus_and_search, whatsapp_search_and_message,
        uia_click_button_by_semantic_role, play_music_or_media, click_first_link_below,
        click_ui_content
    )
    
    tool_bus.register_tool(
        ToolDefinition(
            name="macro_shortcut",
            description=f"Trigger a known keyboard shortcut by semantic name. Available shortcuts: {', '.join(SHORTCUT_MAP.keys())}",
            input_schema={"action": {"type": "string", "description": "The semantic name of the shortcut to execute"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda action, **kwargs: execute_mapped_shortcut(action)
    )
    
    tool_bus.register_tool(
        ToolDefinition(
            name="windows_search",
            description="Open Windows Search via the Windows button (Win key) / Start Menu, type a query, and press Enter to launch apps, settings, or files.",
            input_schema={
                "query": {"type": "string", "description": "Search query to type into Windows Search"},
                "press_enter": {"type": "boolean", "description": "Whether to press Enter to launch top result (default True)"}
            },
            permission_level=PermissionLevel.ACTION,
            category="WINDOWS"
        ),
        lambda query, press_enter=True, **kwargs: windows_menu_search(query, press_enter=press_enter)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="macro_windows_search",
            description="Open the Windows Start Menu, type a query, and press Enter. Best for opening apps or finding system settings.",
            input_schema={"query": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="WINDOWS"
        ),
        lambda query, press_enter=True, **kwargs: windows_menu_search(query, press_enter=press_enter)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="browser_search",
            description="Open the default browser directly to search Google for the specified query.",
            input_schema={"query": {"type": "string", "description": "The search query to look up on Google"}},
            permission_level=PermissionLevel.ACTION,
            category="BROWSER"
        ),
        lambda query, **kwargs: browser_search(query)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="google_search",
            description="Search Google using the default browser.",
            input_schema={"query": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="BROWSER"
        ),
        lambda query, **kwargs: browser_search(query)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="macro_browser_search",
            description="Open browser and search Google for query.",
            input_schema={"query": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda query, **kwargs: browser_search(query)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="macro_mouse_action",
            description="Consolidated mouse logic to scroll down, scroll up, or move to x/y and click (e.g. clicking a login link). Actions: 'scroll_down', 'scroll_up', 'move_and_click'.",
            input_schema={
                "action": {"type": "string", "enum": ["scroll_down", "scroll_up", "move_and_click"]},
                "amount": {"type": "integer", "description": "Amount to scroll (optional)"},
                "x": {"type": "integer", "description": "X coordinate for move_and_click"},
                "y": {"type": "integer", "description": "Y coordinate for move_and_click"}
            },
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda action, amount=None, x=None, y=None, **kwargs: mouse_access_logic(action, amount, x, y)
    )

    tool_bus.register_tool(
        ToolDefinition(
            name="get_current_desktop_state",
            description="Inspect active desktop state: foreground window, whether user is on a browser/desktop/whatsapp, active process name, and contextual shortcut recommendations.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="SYSTEM"
        ),
        lambda **kwargs: get_current_desktop_state()
    )

    tool_bus.register_tool(
        ToolDefinition(
            name="browser_search_bar",
            description="Focus browser search/address bar using Ctrl+K, type search query, and optionally click the top result link below.",
            input_schema={
                "query": {"type": "string", "description": "Search query to type into search bar"},
                "click_first_result": {"type": "boolean", "description": "Whether to click the first link/result below the search bar"}
            },
            permission_level=PermissionLevel.ACTION,
            category="BROWSER"
        ),
        lambda query="", click_first_result=False, **kwargs: browser_search_bar_focus_and_search(query, click_first_result)
    )

    tool_bus.register_tool(
        ToolDefinition(
            name="whatsapp_search_and_message",
            description="Focus WhatsApp, search for a contact name with Ctrl+F, click their contact chat below, and optionally send a message.",
            input_schema={
                "contact": {"type": "string", "description": "Name of contact or group to search in WhatsApp"},
                "message": {"type": "string", "description": "Optional message to send to the contact"}
            },
            permission_level=PermissionLevel.ACTION,
            category="COMMUNICATION"
        ),
        lambda contact, message="", **kwargs: whatsapp_search_and_message(contact, message)
    )

    tool_bus.register_tool(
        ToolDefinition(
            name="uia_click_button",
            description="Click a button by semantic role ('like', 'send', 'submit', 'enter', 'box', 'close') or query label using the UIA accessibility tree.",
            input_schema={
                "role": {"type": "string", "description": "Role of button: 'like', 'send', 'submit', 'enter', 'box', or 'close'"},
                "query": {"type": "string", "description": "Optional specific text or element name to match"},
                "window_title": {"type": "string", "description": "Optional window title filter"}
            },
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda role="button", query="", window_title="", **kwargs: uia_click_button_by_semantic_role(role, query, window_title)
    )

    tool_bus.register_tool(
        ToolDefinition(
            name="play_music",
            description="Play a song or music on YouTube (default), JioHotstar/Hotstar, Spotify, Netflix, Prime Video, or toggle media play/pause if no song name is provided.",
            input_schema={
                "query": {"type": "string", "description": "Optional name of the song, artist, video, or movie to play"},
                "platform": {"type": "string", "description": "Streaming platform: 'youtube' (default), 'hotstar', 'spotify', 'netflix', 'prime', or 'soundcloud'"}
            },
            permission_level=PermissionLevel.ACTION,
            category="MEDIA"
        ),
        lambda query="", platform="youtube", **kwargs: play_music_or_media(query, platform=platform)
    )

    tool_bus.register_tool(
        ToolDefinition(
            name="play_song",
            description="Play a specific song on YouTube (default) or other platforms (Hotstar, Spotify, Netflix), or resume/pause media playback.",
            input_schema={
                "query": {"type": "string", "description": "Song title or artist to play"},
                "platform": {"type": "string", "description": "Streaming platform: 'youtube' (default), 'hotstar', 'spotify', 'netflix', 'prime'"}
            },
            permission_level=PermissionLevel.ACTION,
            category="MEDIA"
        ),
        lambda query="", platform="youtube", **kwargs: play_music_or_media(query, platform=platform)
    )

    tool_bus.register_tool(
        ToolDefinition(
            name="click_first_link",
            description="Find and click the first search result link or video below the search bar in the active browser window.",
            input_schema={"window_title": {"type": "string", "description": "Optional window title"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda window_title="", **kwargs: click_first_link_below(window_title)
    )

    tool_bus.register_tool(
        ToolDefinition(
            name="click_below_link",
            description="Automate clicking the first result link or video below the search bar.",
            input_schema={"window_title": {"type": "string", "description": "Optional window title"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda window_title="", **kwargs: click_first_link_below(window_title)
    )

    tool_bus.register_tool(
        ToolDefinition(
            name="click_ui_content",
            description="Find and click an on-screen content area — whether it is a box, text, icon, button, link, or container.",
            input_schema={
                "query": {"type": "string", "description": "The text, label, or name of the box, text, icon, or button to click"},
                "element_type": {"type": "string", "description": "Optional element type: 'any' (default), 'box', 'text', 'icon', 'button'"},
                "window_title": {"type": "string", "description": "Optional target window title"}
            },
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda query="", element_type="any", window_title="", **kwargs: click_ui_content(query=query, element_type=element_type, window_title=window_title)
    )

    tool_bus.register_tool(
        ToolDefinition(
            name="click_content",
            description="Find and click an on-screen content area — box, text, icon, button, or container.",
            input_schema={
                "query": {"type": "string", "description": "The text, label, or name of the content area to click"},
                "element_type": {"type": "string", "description": "Optional element type: 'any', 'box', 'text', 'icon', 'button'"},
                "window_title": {"type": "string", "description": "Optional target window title"}
            },
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda query="", element_type="any", window_title="", **kwargs: click_ui_content(query=query, element_type=element_type, window_title=window_title)
    )

    # Clipboard
    from app.tools.clipboard_manager import clipboard_read, clipboard_write, clipboard_clear
    tool_bus.register_tool(
        ToolDefinition(
            name="clipboard_read",
            description="Read text from the system clipboard.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="INPUT"
        ),
        lambda **kwargs: clipboard_read()
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="clipboard_write",
            description="Write text to the system clipboard.",
            input_schema={"text": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda text, **kwargs: clipboard_write(text)
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="clipboard_clear",
            description="Clear all text from the system clipboard.",
            input_schema={},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        lambda **kwargs: clipboard_clear()
    )

    # Windows UI Automation (Semantic Desktop Control)
    from app.tools.uia import (
        uia_get_tree,
        uia_find,
        uia_detect_elements,
        uia_detect_box_content,
        uia_click_inside_box,
        uia_get_element_location,
        uia_click_element,
        uia_type_into_element,
        uia_toggle_element,
        uia_set_slider,
        uia_select_option,
        uia_get_table_data,
        uia_invoke,
        uia_set_value,
        uia_get_text,
        uia_get_state,
        uia_focus,
        uia_toggle,
        uia_select,
        uia_expand,
        uia_scroll
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_get_tree",
            description="Get the semantic accessibility tree of a window to find elements. Returns element_ids for interactive controls.",
            input_schema={"window_title": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="UIA"
        ),
        uia_get_tree
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_find",
            description="Find a UI element by name or automation ID within a target window.",
            input_schema={"window_title": {"type": "string"}, "query": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="UIA"
        ),
        uia_find
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_detect_elements",
            description="Detect, classify, and locate UI elements (buttons, search bars, text inputs, submit buttons, close buttons, boxes) with exact bounding boxes and center (x, y) coordinates.",
            input_schema={
                "window_title": {"type": "string"},
                "category": {"type": "string", "enum": ["all", "buttons", "search_bars", "inputs", "close_buttons", "submit_buttons", "clickable"]},
                "max_depth": {"type": "integer"}
            },
            permission_level=PermissionLevel.READ,
            category="UIA"
        ),
        uia_detect_elements
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_detect_box_content",
            description="Detect an outer container/box (ad box, modal, popup, dialog, card, banner) and all elements inside it (such as Skip buttons, Enter buttons, text inputs, close buttons).",
            input_schema={"box_query": {"type": "string"}, "window_title": {"type": "string"}, "max_depth": {"type": "integer"}},
            permission_level=PermissionLevel.READ,
            category="UIA"
        ),
        uia_detect_box_content
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_click_inside_box",
            description="Find a container/box (ad box, modal, popup, dialog) and click a button inside it (e.g., 'skip', 'skip ad', 'enter', 'next', 'close').",
            input_schema={"box_query": {"type": "string"}, "target": {"type": "string"}, "window_title": {"type": "string"}, "button": {"type": "string", "enum": ["left", "right", "double"]}},
            permission_level=PermissionLevel.ACTION,
            category="UIA"
        ),
        uia_click_inside_box
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_get_element_location",
            description="Find the physical screen location (bounding box and center x, y coordinates) of a UI element by name, query, or element_id.",
            input_schema={"window_title": {"type": "string"}, "query": {"type": "string"}, "element_id": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="UIA"
        ),
        uia_get_element_location
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_click_element",
            description="Directly click a UI element (button, search bar, close button, etc.) by name or element_id using physical center screen coordinates or UIA Invoke.",
            input_schema={"window_title": {"type": "string"}, "query": {"type": "string"}, "element_id": {"type": "string"}, "button": {"type": "string", "enum": ["left", "right", "double"]}},
            permission_level=PermissionLevel.ACTION,
            category="UIA"
        ),
        uia_click_element
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_type_into_element",
            description="Type text into a detected UI element (search bar, text field, input box) by name or element_id using ValuePattern or coordinate click-and-type.",
            input_schema={"window_title": {"type": "string"}, "query": {"type": "string"}, "text": {"type": "string"}, "element_id": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="UIA"
        ),
        uia_type_into_element
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_invoke",
            description="Click or invoke an element discovered via uia_get_tree or uia_find.",
            input_schema={"element_id": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="UIA"
        ),
        uia_invoke
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_set_value",
            description="Type text into an editable element discovered via uia_get_tree or uia_find.",
            input_schema={"element_id": {"type": "string"}, "value": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="UIA"
        ),
        uia_set_value
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_get_text",
            description="Extract text content or value from a discovered UI element.",
            input_schema={"element_id": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="UIA"
        ),
        uia_get_text
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_get_state",
            description="Check the interaction state (enabled, focused, toggled, selected) of a UI element.",
            input_schema={"element_id": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="UIA"
        ),
        uia_get_state
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_focus",
            description="Set keyboard focus directly to a discovered UI element.",
            input_schema={"element_id": {"type": "string"}},
            permission_level=PermissionLevel.LOW_RISK,
            category="UIA"
        ),
        uia_focus
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_toggle",
            description="Toggle a checkbox or switch element discovered via uia_find/uia_get_tree.",
            input_schema={"element_id": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="UIA"
        ),
        uia_toggle
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_select",
            description="Select an item or option control discovered via uia_find/uia_get_tree.",
            input_schema={"element_id": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="UIA"
        ),
        uia_select
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_expand",
            description="Expand or collapse a dropdown, combobox, or tree item discovered via UIA.",
            input_schema={"element_id": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="UIA"
        ),
        uia_expand
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_scroll",
            description="Scroll a UIA scrollable control in a specified direction ('up', 'down', 'left', 'right').",
            input_schema={
                "element_id": {"type": "string"},
                "direction": {"type": "string", "enum": ["up", "down", "left", "right"]},
                "amount": {"type": "integer", "description": "Scroll percentage from 0 to 100"}
            },
            permission_level=PermissionLevel.ACTION,
            category="UIA"
        ),
        uia_scroll
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_toggle_element",
            description="Toggle a checkbox, radio button, or switch control by name, query, or element ID.",
            input_schema={"window_title": {"type": "string"}, "query": {"type": "string"}, "element_id": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="UIA"
        ),
        uia_toggle_element
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_set_slider",
            description="Set the position or value of a slider, volume bar, or range control (0 to 100).",
            input_schema={"window_title": {"type": "string"}, "query": {"type": "string"}, "value": {"type": "number"}, "element_id": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="UIA"
        ),
        uia_set_slider
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_select_option",
            description="Expand a dropdown/combobox or list control and select a specific option by name.",
            input_schema={"window_title": {"type": "string"}, "query": {"type": "string"}, "option_name": {"type": "string"}, "element_id": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="UIA"
        ),
        uia_select_option
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="uia_get_table_data",
            description="Extract rows, columns, and headers from a Table, DataGrid, or List control as structured JSON data.",
            input_schema={"window_title": {"type": "string"}, "query": {"type": "string"}, "max_rows": {"type": "integer"}},
            permission_level=PermissionLevel.READ,
            category="UIA"
        ),
        uia_get_table_data
    )

    # Universal User Action Patterns (Human-Felt Desktop & Browser Automation)
    from app.tools.action_patterns import (
        pattern_search_and_navigate,
        pattern_form_fill_and_submit,
        pattern_handle_dialog,
        pattern_tab_and_window,
        pattern_scroll_and_find,
        pattern_context_action,
        pattern_smart_click_or_type
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="pattern_search_and_navigate",
            description="Natural human search pattern: locates search/address bar (Ctrl+L for browsers or UIA search box), clears, types query, and submits with Enter.",
            input_schema={"query": {"type": "string"}, "window_title": {"type": "string"}, "submit": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="PATTERNS"
        ),
        pattern_search_and_navigate
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="pattern_form_fill_and_submit",
            description="Natural human form-filling pattern: iterates through field name/value mappings, focuses each input, types values, and clicks submit button.",
            input_schema={"fields": {"type": "object"}, "submit_button": {"type": "string"}, "window_title": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="PATTERNS"
        ),
        pattern_form_fill_and_submit
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="pattern_handle_dialog",
            description="Natural human dialog/popup pattern: responds to confirmations and alerts with 'affirmative' (OK, Save, Yes), 'negative' (Cancel, No), or 'close' (dismiss).",
            input_schema={"decision": {"type": "string", "enum": ["affirmative", "negative", "close"]}, "window_title": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="PATTERNS"
        ),
        pattern_handle_dialog
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="pattern_tab_and_window",
            description="Natural human tab and window pattern: handles tab lifecycle ('new_tab', 'close_tab', 'next_tab', 'prev_tab') and window states ('minimize', 'maximize', 'close_window').",
            input_schema={"action": {"type": "string", "enum": ["new_tab", "close_tab", "reopen_tab", "next_tab", "prev_tab", "minimize", "maximize", "close_window"]}, "target": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="PATTERNS"
        ),
        pattern_tab_and_window
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="pattern_scroll_and_find",
            description="Natural human scroll-and-discover pattern: scans active viewport for an element; scrolls downward or upward until located.",
            input_schema={"target_text": {"type": "string"}, "max_scrolls": {"type": "integer"}, "direction": {"type": "string", "enum": ["down", "up"]}, "window_title": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="PATTERNS"
        ),
        pattern_scroll_and_find
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="pattern_context_action",
            description="Natural human context menu pattern: right-clicks an element or coordinate and selects a context menu option.",
            input_schema={"target_element": {"type": "string"}, "menu_item": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}, "window_title": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="PATTERNS"
        ),
        pattern_context_action
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="pattern_smart_click_or_type",
            description="Universal human element handler: detects target element; if text is provided types into it, otherwise clicks it directly.",
            input_schema={"target": {"type": "string"}, "text": {"type": "string"}, "window_title": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="PATTERNS"
        ),
        pattern_smart_click_or_type
    )

    # Web Search
    from app.tools.search import web_search
    tool_bus.register_tool(
        ToolDefinition(
            name="search_web",
            description="Search the web for information.",
            input_schema={"query": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="WEB"
        ),
        web_search
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="web_search",
            description="Search the web for information using DuckDuckGo.",
            input_schema={"query": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="WEB"
        ),
        web_search
    )

    # Advanced Browser (Leon Migration)
    try:
        from app.tools.advanced_browser.playwright import PlaywrightBrowserController
        from app.tools.advanced_browser.actions import BrowserActionService
        
        # Instantiate the advanced Playwright controller
        browser_controller = PlaywrightBrowserController(headless=True)
        browser_service = BrowserActionService(browser_controller)
        
        async def browser_start_wrapper(**kwargs):
            await browser_service.start()
            return {"status": "Browser started"}
            
        tool_bus.register_tool(
            ToolDefinition(
                name="browser_start",
                description="Start an isolated browser automation session.",
                input_schema={},
                permission_level=PermissionLevel.ACTION,
                category="BROWSER"
            ),
            browser_start_wrapper
        )
        
        async def browser_navigate_wrapper(url, **kwargs):
            dest = await browser_service.navigate(url)
            return {"status": "Navigated", "url": dest}
            
        tool_bus.register_tool(
            ToolDefinition(
                name="browser_navigate",
                description="Navigate the active browser tab to a URL.",
                input_schema={"url": {"type": "string"}},
                permission_level=PermissionLevel.LOW_RISK,
                category="BROWSER"
            ),
            browser_navigate_wrapper
        )
        tool_bus.register_tool(
            ToolDefinition(
                name="open_url",
                description="Navigate the active browser to a URL.",
                input_schema={"url": {"type": "string"}},
                permission_level=PermissionLevel.LOW_RISK,
                category="BROWSER"
            ),
            browser_navigate_wrapper
        )
        tool_bus.register_tool(
            ToolDefinition(
                name="browser_open_url",
                description="Open a URL in the browser automation engine.",
                input_schema={"url": {"type": "string"}},
                permission_level=PermissionLevel.LOW_RISK,
                category="BROWSER"
            ),
            browser_navigate_wrapper
        )
        
        async def browser_snapshot_wrapper(**kwargs):
            snap = await browser_service.snapshot()
            from dataclasses import asdict
            return asdict(snap)
            
        tool_bus.register_tool(
            ToolDefinition(
                name="browser_snapshot",
                description="Read a bounded DOM/accessibility snapshot.",
                input_schema={},
                permission_level=PermissionLevel.READ,
                category="BROWSER"
            ),
            browser_snapshot_wrapper
        )
        
        async def browser_click_wrapper(element_id, expected_role, expected_name, **kwargs):
            await browser_service.click(element_id, expected_role, expected_name)
            return {"status": "Clicked"}
            
        tool_bus.register_tool(
            ToolDefinition(
                name="browser_click",
                description="Click a verified element from the latest browser snapshot.",
                input_schema={
                    "element_id": {"type": "string"},
                    "expected_role": {"type": "string"},
                    "expected_name": {"type": "string"}
                },
                permission_level=PermissionLevel.ACTION,
                category="BROWSER"
            ),
            browser_click_wrapper
        )
        
        async def browser_type_wrapper(element_id, expected_role, expected_name, text, **kwargs):
            await browser_service.type_text(element_id, expected_role, expected_name, text, clear=True)
            return {"status": "Typed text"}
            
        tool_bus.register_tool(
            ToolDefinition(
                name="browser_type",
                description="Type text into a verified element from the latest snapshot.",
                input_schema={
                    "element_id": {"type": "string"},
                    "expected_role": {"type": "string"},
                    "expected_name": {"type": "string"},
                    "text": {"type": "string"}
                },
                permission_level=PermissionLevel.ACTION,
                category="BROWSER"
            ),
            browser_type_wrapper
        )
        async def browser_close_wrapper(**kwargs):
            await browser_service.close()
            return {"status": "Browser closed"}

        tool_bus.register_tool(
            ToolDefinition(
                name="browser_close",
                description="Close the active browser automation session.",
                input_schema={},
                permission_level=PermissionLevel.ACTION,
                category="BROWSER"
            ),
            browser_close_wrapper
        )

        async def browser_press_key_wrapper(element_id: str, expected_role: str, expected_name: str, key: str, **kwargs):
            await browser_service.press_key(element_id, expected_role, expected_name, key)
            return {"status": "Key pressed"}

        tool_bus.register_tool(
            ToolDefinition(
                name="browser_press_key",
                description="Press a specific key on a verified element from the latest browser snapshot.",
                input_schema={
                    "element_id": {"type": "string"},
                    "expected_role": {"type": "string"},
                    "expected_name": {"type": "string"},
                    "key": {"type": "string"}
                },
                permission_level=PermissionLevel.ACTION,
                category="BROWSER"
            ),
            browser_press_key_wrapper
        )
    except ImportError as e:
        print(f"Warning: Could not load advanced browser module: {e}")

    # Filesystem & Windows File Explorer (Native Python + Win32 + MCP bridge)
    import app.tools.filesystem as fs

    # 1. Discovery & Inspection
    tool_bus.register_tool(
        ToolDefinition(
            name="get_current_directory",
            description="Get the current working directory path.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.get_current_directory
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="change_directory",
            description="Change the active working directory with path validation.",
            input_schema={"path": {"type": "string", "description": "Target folder path"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.change_directory
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="list_directory",
            description="List files and directories with metadata (size, dates, hidden status).",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Optional directory path, defaults to '.'"},
                    "recursive": {"type": "boolean", "description": "Optional: whether to list subfolders recursively"},
                    "max_depth": {"type": "integer", "description": "Optional: max recursion depth"},
                    "show_hidden": {"type": "boolean", "description": "Optional: include hidden files"},
                    "sort_by": {"type": "string", "enum": ["name", "size", "date"], "description": "Optional: sort field"}
                },
                "required": []
            },
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.list_directory
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="search_files",
            description="Search for files by name pattern or substring across directories.",
            input_schema={
                "query": {"type": "string", "description": "Pattern or name substring to search"},
                "root_dir": {"type": "string", "description": "Root folder to search from, defaults to '.'"},
                "recursive": {"type": "boolean", "description": "Search recursively"}
            },
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.search_files
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="search_file_contents",
            description="Search for text or string occurrences inside files in a folder.",
            input_schema={
                "query": {"type": "string", "description": "Text to search inside files"},
                "root_dir": {"type": "string"},
                "file_pattern": {"type": "string", "description": "File glob, e.g. *.py, *.txt"},
                "case_sensitive": {"type": "boolean"}
            },
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.search_file_contents
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="get_file_info",
            description="Get detailed file metadata, size, timestamps, and attributes.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.get_file_info
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="get_directory_tree",
            description="Generate a visual directory hierarchy tree string.",
            input_schema={"path": {"type": "string"}, "max_depth": {"type": "integer"}, "show_files": {"type": "boolean"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.get_directory_tree
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="find_recent_files",
            description="Find files modified within the last N hours.",
            input_schema={"root_dir": {"type": "string"}, "hours": {"type": "integer"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.find_recent_files
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="find_large_files",
            description="Find files exceeding a minimum size threshold in MB.",
            input_schema={"root_dir": {"type": "string"}, "min_size_mb": {"type": "number"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.find_large_files
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="find_empty_directories",
            description="Find empty directories containing no files or subfolders.",
            input_schema={"root_dir": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.find_empty_directories
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="find_duplicate_files",
            description="Identify duplicate files based on size and checksum.",
            input_schema={"root_dir": {"type": "string"}, "min_size_bytes": {"type": "integer"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.find_duplicate_files
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="compare_files",
            description="Compare two files by hash or line-by-line unified diff.",
            input_schema={"path1": {"type": "string"}, "path2": {"type": "string"}, "mode": {"type": "string", "enum": ["diff", "hash"]}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.compare_files
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="compare_directories",
            description="Compare contents and differences between two directory trees.",
            input_schema={"dir1": {"type": "string"}, "dir2": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.compare_directories
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="check_path_exists",
            description="Check whether a path exists and whether it is a file, folder, or symlink.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.check_path_exists
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="inspect_file_permissions",
            description="Inspect read/write/execute permissions for a target path.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.inspect_file_permissions
    )

    # 2. File & Folder Creation
    tool_bus.register_tool(
        ToolDefinition(
            name="create_file",
            description="Create a new file with optional initial content and conflict detection.",
            input_schema={"path": {"type": "string"}, "content": {"type": "string"}, "overwrite": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.create_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="create_directory",
            description="Create a directory and any required parent directories.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.create_directory
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="create_directory_tree",
            description="Create multiple directory structures under a base path in one validated operation.",
            input_schema={"base_path": {"type": "string"}, "subdirectories": {"type": "array", "items": {"type": "string"}}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.create_directory_tree
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="create_project_structure",
            description="Create a nested project directory and files structure from a schema.",
            input_schema={"base_path": {"type": "string"}, "structure": {"type": "object"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.create_project_structure
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="create_shortcut",
            description="Create a Windows .lnk shortcut pointing to a file or folder.",
            input_schema={"target_path": {"type": "string"}, "shortcut_path": {"type": "string"}, "description": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.create_shortcut
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="create_temporary_file",
            description="Create a managed temporary file.",
            input_schema={"prefix": {"type": "string"}, "suffix": {"type": "string"}, "content": {"type": "string"}},
            permission_level=PermissionLevel.LOW_RISK,
            category="FILESYSTEM"
        ),
        fs.create_temporary_file
    )

    # 3. Rename, Copy, Move
    tool_bus.register_tool(
        ToolDefinition(
            name="rename_path",
            description="Rename a file or directory safely with post-verification.",
            input_schema={"source": {"type": "string"}, "new_name_or_path": {"type": "string"}, "overwrite": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.rename_path
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="copy_file",
            description="Copy a file to a destination preserving metadata.",
            input_schema={"source": {"type": "string"}, "destination": {"type": "string"}, "overwrite": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.copy_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="copy_directory",
            description="Recursively copy an entire directory tree.",
            input_schema={"source": {"type": "string"}, "destination": {"type": "string"}, "overwrite": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.copy_directory
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="move_file",
            description="Move a file to a destination folder or new name.",
            input_schema={"source": {"type": "string"}, "destination": {"type": "string"}, "overwrite": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.move_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="move_directory",
            description="Move an entire directory tree to a new location.",
            input_schema={"source": {"type": "string"}, "destination": {"type": "string"}, "overwrite": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.move_directory
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="duplicate_file",
            description="Duplicate a file in the same directory with a copy suffix.",
            input_schema={"source": {"type": "string"}, "new_name": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.duplicate_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="batch_rename",
            description="Batch rename multiple files matching a regex pattern.",
            input_schema={"directory": {"type": "string"}, "pattern": {"type": "string"}, "replacement": {"type": "string"}, "dry_run": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.batch_rename
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="batch_copy",
            description="Copy multiple files or folders into a target directory.",
            input_schema={"source_paths": {"type": "array", "items": {"type": "string"}}, "destination_dir": {"type": "string"}, "overwrite": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.batch_copy
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="batch_move",
            description="Move multiple files or folders into a target directory.",
            input_schema={"source_paths": {"type": "array", "items": {"type": "string"}}, "destination_dir": {"type": "string"}, "overwrite": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.batch_move
    )

    # 4. Delete & Recovery
    tool_bus.register_tool(
        ToolDefinition(
            name="move_to_recycle_bin",
            description="Safely send a file or folder to the Windows Recycle Bin so it can be restored.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.LOW_RISK,
            category="FILESYSTEM"
        ),
        fs.move_to_recycle_bin
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="restore_from_recycle_bin",
            description="Restore a previously deleted file or folder from the Windows Recycle Bin.",
            input_schema={"original_filename_or_path": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.restore_from_recycle_bin
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="inspect_recycle_bin",
            description="Inspect the contents of the Windows Recycle Bin.",
            input_schema={"limit": {"type": "integer"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.inspect_recycle_bin
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="permanently_delete",
            description="Permanently delete a file or directory (irreversible).",
            input_schema={"path": {"type": "string"}, "recursive": {"type": "boolean"}, "force": {"type": "boolean"}},
            permission_level=PermissionLevel.DESTRUCTIVE,
            category="FILESYSTEM"
        ),
        fs.permanently_delete
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="delete_empty_directory",
            description="Delete an empty directory.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.delete_empty_directory
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="undo_supported_file_operation",
            description="Undo the last supported file operation (rename, move, copy, edit).",
            input_schema={"operation_id": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.undo_supported_file_operation
    )

    # 5. Content Operations
    tool_bus.register_tool(
        ToolDefinition(
            name="read_text_file",
            description="Read text lines from a file with line bounds and encoding safety.",
            input_schema={"path": {"type": "string"}, "offset": {"type": "integer"}, "limit": {"type": "integer"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.read_text_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="write_text_file",
            description="Write text to a file atomically with optional backup.",
            input_schema={"path": {"type": "string"}, "content": {"type": "string"}, "atomic": {"type": "boolean"}, "create_backup": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.write_text_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="append_text_file",
            description="Append text to the end of an existing file.",
            input_schema={"path": {"type": "string"}, "content": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.append_text_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="edit_text_file",
            description="Replace a 1-indexed line range in a text file with backup creation.",
            input_schema={"path": {"type": "string"}, "line_start": {"type": "integer"}, "line_end": {"type": "integer"}, "replacement_text": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.edit_text_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="replace_text",
            description="Replace occurrences of a substring inside a file.",
            input_schema={"path": {"type": "string"}, "target": {"type": "string"}, "replacement": {"type": "string"}, "count": {"type": "integer"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.replace_text
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="read_json_file",
            description="Read and parse a JSON file.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.read_json_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="write_json_file",
            description="Serialize and atomically save data to a JSON file.",
            input_schema={"path": {"type": "string"}, "data": {"type": "object"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.write_json_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="read_configuration_file",
            description="Read a .env, .ini, or configuration file into structured dictionary.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.read_configuration_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="write_configuration_file",
            description="Write a structured dictionary to config or .env format.",
            input_schema={"path": {"type": "string"}, "data": {"type": "object"}, "format_type": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.write_configuration_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="inspect_source_file",
            description="Analyze a Python source file: line counts, classes, functions, and imports.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.inspect_source_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="apply_approved_file_changes",
            description="Apply a batch of approved file modifications across multiple files atomically.",
            input_schema={"changes": {"type": "array", "items": {"type": "object"}}, "dry_run": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.apply_approved_file_changes
    )

    # 6. Archives & Metadata
    tool_bus.register_tool(
        ToolDefinition(
            name="create_zip_archive",
            description="Create a compressed ZIP archive from multiple files or folders.",
            input_schema={"source_paths": {"type": "array", "items": {"type": "string"}}, "archive_path": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.create_zip_archive
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="extract_zip_archive",
            description="Extract a ZIP archive with Anti-ZipSlip path traversal protection.",
            input_schema={"archive_path": {"type": "string"}, "destination_dir": {"type": "string"}, "overwrite": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.extract_zip_archive
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="inspect_archive",
            description="Inspect the contents and file listing of a ZIP archive.",
            input_schema={"archive_path": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.inspect_archive
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="calculate_file_hash",
            description="Compute the SHA-256 or MD5 cryptographic hash of a file.",
            input_schema={"path": {"type": "string"}, "algorithm": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.calculate_file_hash
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="compare_file_hashes",
            description="Compare the cryptographic hash of two files.",
            input_schema={"path1": {"type": "string"}, "path2": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.compare_file_hashes
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="inspect_file_attributes",
            description="Inspect Windows file attributes (hidden, readonly, archive, system).",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.inspect_file_attributes
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="modify_supported_file_attributes",
            description="Modify Windows file attributes (hidden, readonly).",
            input_schema={"path": {"type": "string"}, "readonly": {"type": "boolean"}, "hidden": {"type": "boolean"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.modify_supported_file_attributes
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="inspect_disk_usage",
            description="Inspect drive storage capacity, used space, and free space.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.inspect_disk_usage
    )

    # 7. File Explorer & Windows Desktop Shell Integration
    tool_bus.register_tool(
        ToolDefinition(
            name="file_explorer_open",
            description="Open Windows File Explorer at a folder or default directory.",
            input_schema={"folder_path": {"type": "string"}},
            permission_level=PermissionLevel.LOW_RISK,
            category="WINDOWS"
        ),
        fs.file_explorer_open
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="file_explorer_reveal",
            description="Open Windows File Explorer with the specific file or folder highlighted/selected.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.LOW_RISK,
            category="WINDOWS"
        ),
        fs.file_explorer_reveal
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="file_explorer_navigate",
            description="Navigate an open File Explorer window to a new directory path.",
            input_schema={"folder_path": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="WINDOWS"
        ),
        fs.file_explorer_navigate
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="file_explorer_get_selection",
            description="Get the currently selected files or folders in active Windows File Explorer.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="WINDOWS"
        ),
        fs.file_explorer_get_selection
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="file_open_with",
            description="Open a file with a specified application or trigger the native Windows 'Open with...' dialog.",
            input_schema={"path": {"type": "string"}, "app_name": {"type": "string"}},
            permission_level=PermissionLevel.LOW_RISK,
            category="WINDOWS"
        ),
        fs.file_open_with
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="file_share",
            description="Open the Windows file sharing properties dialog for a path.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.LOW_RISK,
            category="WINDOWS"
        ),
        fs.file_share
    )

    # Backward compatibility aliases
    tool_bus.register_tool(
        ToolDefinition(
            name="read_file",
            description="Read the complete contents of a file.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.read_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="write_file",
            description="Create a new file or overwrite an existing file with new content.",
            input_schema={"path": {"type": "string"}, "content": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="FILESYSTEM"
        ),
        fs.write_file
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="file_search",
            description="Search for files matching a pattern or substring within a directory.",
            input_schema={"query": {"type": "string"}, "root_dir": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.file_search
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="file_exists",
            description="Check whether a specific file or directory exists on disk.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        fs.file_exists
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="file_delete",
            description="Send a file or folder safely to the Recycle Bin.",
            input_schema={"path": {"type": "string"}},
            permission_level=PermissionLevel.SENSITIVE,
            category="FILESYSTEM"
        ),
        fs.file_delete
    )

    # Vision (On-Demand)
    from app.tools.vision import vision_find_text, vision_find_icon, vision_ask_question
    tool_bus.register_tool(
        ToolDefinition(
            name="vision_find_text",
            description="Use PaddleOCR to locate specific text on the screen and return its coordinates. Use ONLY when native tools fail.",
            input_schema={"text": {"type": "string", "description": "The text to find on screen"}},
            permission_level=PermissionLevel.READ,
            category="VISION"
        ),
        vision_find_text
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="vision_find_icon",
            description="Use OmniParser to locate a GUI element or icon by description and return its coordinates. Use ONLY when OCR and native tools fail.",
            input_schema={"description": {"type": "string", "description": "Description of the icon or UI element"}},
            permission_level=PermissionLevel.READ,
            category="VISION"
        ),
        vision_find_icon
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="vision_ask_question",
            description="Use a Visual Language Model (VLM) for visual reasoning about the current screen (e.g., 'What is preventing me from continuing?'). Use ONLY for reasoning, not for simple target finding.",
            input_schema={"question": {"type": "string", "description": "Question about the visual state of the screen"}},
            permission_level=PermissionLevel.READ,
            category="VISION"
        ),
        vision_ask_question
    )
    
    from app.tools.vision import vision_audit_environment, vision_match_template
    tool_bus.register_tool(
        ToolDefinition(
            name="vision_audit_environment",
            description="Inspect the system environment to determine which vision backends (OCR, GUI grounding, VLM) are actually available and installable.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="VISION"
        ),
        vision_audit_environment
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="vision_match_template",
            description="Find pixel coordinates of an icon/button template image on screen using ultra-fast OpenCV normalized template matching.",
            input_schema={"template_path": {"type": "string", "description": "Absolute path to template image file"}, "confidence": {"type": "number", "description": "Match threshold 0.0-1.0, default 0.8"}},
            permission_level=PermissionLevel.READ,
            category="VISION"
        ),
        lambda template_path="", confidence=0.8, **kwargs: vision_match_template(template_path, confidence)
    )

    # Native Built-in OS, Subprocess, PyAutoGUI, and Win32 Tools
    from app.tools.native_os_win32 import (
        os_get_env,
        os_set_env,
        os_get_cwd,
        os_list_drives,
        subprocess_run_sync,
        subprocess_start_background,
        pyautogui_get_screen_size,
        pyautogui_locate_on_screen,
        pyautogui_mouse_down,
        pyautogui_mouse_up,
        pyautogui_alert,
        win32_get_foreground_window,
        win32_enum_windows,
        win32_set_window_pos,
        win32_show_desktop,
        win32_lock_workstation,
        win32_get_cursor_pos
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="os_get_env",
            description="Retrieve system environment variables or inspect process environment configuration.",
            input_schema={"variable": {"type": "string"}},
            permission_level=PermissionLevel.READ,
            category="SYSTEM"
        ),
        os_get_env
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="os_set_env",
            description="Set or update an environment variable for the JARVIS process context.",
            input_schema={"variable": {"type": "string"}, "value": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="SYSTEM"
        ),
        os_set_env
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="os_get_cwd",
            description="Get the current working directory path of the system.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        os_get_cwd
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="os_list_drives",
            description="List all available Windows drives (C:, D:, etc.) with disk space statistics.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="FILESYSTEM"
        ),
        os_list_drives
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="subprocess_run_sync",
            description="Execute a shell command synchronously and capture stdout, stderr, and exit code.",
            input_schema={"command": {"type": "string"}, "cwd": {"type": "string"}, "timeout": {"type": "integer"}},
            permission_level=PermissionLevel.ACTION,
            category="TERMINAL"
        ),
        subprocess_run_sync
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="subprocess_start_background",
            description="Spawn a non-blocking background daemon process via subprocess.Popen.",
            input_schema={"command": {"type": "string"}, "cwd": {"type": "string"}},
            permission_level=PermissionLevel.ACTION,
            category="TERMINAL"
        ),
        subprocess_start_background
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="pyautogui_get_screen_size",
            description="Get the primary monitor screen resolution (width, height) using PyAutoGUI.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="INPUT"
        ),
        pyautogui_get_screen_size
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="pyautogui_locate_on_screen",
            description="Locate an image template or icon on the physical screen and return its center coordinates.",
            input_schema={"image_path": {"type": "string"}, "confidence": {"type": "number"}},
            permission_level=PermissionLevel.READ,
            category="VISION"
        ),
        pyautogui_locate_on_screen
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="pyautogui_mouse_down",
            description="Press and hold the mouse button at the current or specified screen coordinates.",
            input_schema={"button": {"type": "string", "enum": ["left", "right", "middle"]}, "x": {"type": "integer"}, "y": {"type": "integer"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        pyautogui_mouse_down
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="pyautogui_mouse_up",
            description="Release a held mouse button at current or specified screen coordinates.",
            input_schema={"button": {"type": "string", "enum": ["left", "right", "middle"]}, "x": {"type": "integer"}, "y": {"type": "integer"}},
            permission_level=PermissionLevel.ACTION,
            category="INPUT"
        ),
        pyautogui_mouse_up
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="pyautogui_alert",
            description="Display a native desktop alert modal popup dialog using PyAutoGUI.",
            input_schema={"text": {"type": "string"}, "title": {"type": "string"}},
            permission_level=PermissionLevel.LOW_RISK,
            category="WINDOWS"
        ),
        pyautogui_alert
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="win32_get_foreground_window",
            description="Get the active foreground window HWND, title, and bounding rectangle via native Win32 User32.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="WINDOWS"
        ),
        win32_get_foreground_window
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="win32_enum_windows",
            description="Enumerate all visible top-level windows with HWNDs and titles using Win32 EnumWindows.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="WINDOWS"
        ),
        win32_enum_windows
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="win32_set_window_pos",
            description="Move and resize a target window by HWND or exact title using Win32 SetWindowPos.",
            input_schema={"hwnd": {"type": "integer"}, "title": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}, "width": {"type": "integer"}, "height": {"type": "integer"}},
            permission_level=PermissionLevel.ACTION,
            category="WINDOWS"
        ),
        win32_set_window_pos
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="win32_show_desktop",
            description="Minimize all open windows to reveal the Windows desktop (Win+D).",
            input_schema={},
            permission_level=PermissionLevel.LOW_RISK,
            category="WINDOWS"
        ),
        win32_show_desktop
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="win32_lock_workstation",
            description="Lock the Windows PC workstation using native Win32 LockWorkStation.",
            input_schema={},
            permission_level=PermissionLevel.SENSITIVE,
            category="SYSTEM"
        ),
        win32_lock_workstation
    )
    tool_bus.register_tool(
        ToolDefinition(
            name="win32_get_cursor_pos",
            description="Get the exact physical hardware cursor position directly from Win32 User32 GetCursorPos.",
            input_schema={},
            permission_level=PermissionLevel.READ,
            category="INPUT"
        ),
        win32_get_cursor_pos
    )

def get_tool_schemas():
    schemas = []
    for tool_name, tool_def in tool_bus.tools.items():
        schemas.append({
            "name": tool_def.name,
            "description": tool_def.description,
            "parameters": tool_def.input_schema
        })
    return json.dumps(schemas, indent=2)


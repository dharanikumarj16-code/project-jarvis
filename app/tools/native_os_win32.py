"""
native_os_win32.py – Native Built-in OS, Subprocess, PyAutoGUI, and Win32 Tools for JARVIS
========================================================================================
Comprehensive exposure of native operating system, subprocess execution,
PyAutoGUI screen/input automation, and Win32 / ctypes system calls.
"""

import os
import sys
import ctypes
from ctypes import wintypes
import subprocess
import shutil
from typing import Dict, Any, Optional, List

from app.permissions import check_permission, PermissionLevel


# ============================================================================
# 1. OS & Subprocess Built-in Tools
# ============================================================================

def os_get_env(variable: str = "") -> Dict[str, Any]:
    """Retrieve environment variables. If variable is empty, returns common system environment info."""
    if not check_permission("os_get_env", PermissionLevel.READ, {"variable": variable}):
        return {"success": False, "error": "Permission denied"}
    try:
        if variable:
            val = os.environ.get(variable)
            if val is not None:
                return {"success": True, "variable": variable, "value": val}
            return {"success": False, "error": f"Environment variable '{variable}' not found."}

        # Safe summary of important system variables
        safe_keys = ["COMPUTERNAME", "USERNAME", "USERPROFILE", "OS", "PROCESSOR_ARCHITECTURE", "TEMP", "PATH"]
        summary = {k: os.environ.get(k, "") for k in safe_keys if k in os.environ}
        return {"success": True, "environment": summary}
    except Exception as e:
        return {"success": False, "error": str(e)}


def os_set_env(variable: str, value: str) -> Dict[str, Any]:
    """Set an environment variable for the JARVIS process context."""
    if not check_permission("os_set_env", PermissionLevel.ACTION, {"variable": variable, "value": value}):
        return {"success": False, "error": "Permission denied"}
    try:
        if not variable:
            return {"success": False, "error": "Variable name cannot be empty."}
        os.environ[variable] = str(value)
        return {"success": True, "message": f"Set environment variable '{variable}'", "value": value}
    except Exception as e:
        return {"success": False, "error": str(e)}


def os_get_cwd() -> Dict[str, Any]:
    """Get the current working directory of the process."""
    if not check_permission("os_get_cwd", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        return {"success": True, "cwd": os.getcwd()}
    except Exception as e:
        return {"success": False, "error": str(e)}


def os_list_drives() -> Dict[str, Any]:
    """List all available Windows drives (C:, D:, etc.) with free and total disk space."""
    if not check_permission("os_list_drives", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        import string
        drives = []
        for letter in string.ascii_uppercase:
            drive_path = f"{letter}:\\"
            if os.path.exists(drive_path):
                try:
                    usage = shutil.disk_usage(drive_path)
                    drives.append({
                        "drive": drive_path,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent_used": round((usage.used / usage.total) * 100, 1)
                    })
                except Exception:
                    drives.append({"drive": drive_path, "status": "Ready"})
        return {"success": True, "drives": drives}
    except Exception as e:
        return {"success": False, "error": str(e)}


def subprocess_run_sync(command: str, cwd: str = "", timeout: int = 20) -> Dict[str, Any]:
    """Run a command synchronously using subprocess.run and return stdout, stderr, and exit code."""
    if not check_permission("subprocess_run_sync", PermissionLevel.ACTION, {"command": command}):
        return {"success": False, "error": "Permission denied"}
    try:
        run_cwd = cwd if cwd and os.path.isdir(cwd) else os.getcwd()
        res = subprocess.run(
            command,
            cwd=run_cwd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "success": res.returncode == 0,
            "exit_code": res.returncode,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout} seconds.", "exit_code": -1}
    except Exception as e:
        return {"success": False, "error": str(e), "exit_code": -1}


def subprocess_start_background(command: str, cwd: str = "") -> Dict[str, Any]:
    """Spawn a non-blocking background process via subprocess.Popen."""
    if not check_permission("subprocess_start_background", PermissionLevel.ACTION, {"command": command}):
        return {"success": False, "error": "Permission denied"}
    try:
        run_cwd = cwd if cwd and os.path.isdir(cwd) else os.getcwd()
        proc = subprocess.Popen(
            command,
            cwd=run_cwd,
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return {
            "success": True,
            "message": f"Started background process with PID {proc.pid}",
            "pid": proc.pid
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# 2. PyAutoGUI Built-in Tools
# ============================================================================

def pyautogui_get_screen_size() -> Dict[str, Any]:
    """Get the primary monitor screen resolution (width, height) using PyAutoGUI."""
    if not check_permission("pyautogui_get_screen_size", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        import pyautogui
        size = pyautogui.size()
        return {"success": True, "width": int(size[0]), "height": int(size[1])}
    except Exception as e:
        return {"success": False, "error": str(e)}


def pyautogui_locate_on_screen(image_path: str, confidence: float = 0.9) -> Dict[str, Any]:
    """Locate an image/icon template on screen and return its center coordinates."""
    if not check_permission("pyautogui_locate_on_screen", PermissionLevel.READ, {"image_path": image_path}):
        return {"success": False, "error": "Permission denied"}
    try:
        import pyautogui
        if not os.path.isfile(image_path):
            return {"success": False, "error": f"Image file '{image_path}' not found."}

        loc = pyautogui.locateCenterOnScreen(image_path, confidence=confidence)
        if loc:
            return {"success": True, "found": True, "center": {"x": int(loc.x), "y": int(loc.y)}}
        return {"success": True, "found": False, "message": "Image not found on screen."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def pyautogui_mouse_down(button: str = "left", x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
    """Press and hold mouse button at current or specified coordinate."""
    if not check_permission("pyautogui_mouse_down", PermissionLevel.ACTION, {"button": button}):
        return {"success": False, "error": "Permission denied"}
    try:
        import pyautogui
        pyautogui.mouseDown(x=x, y=y, button=button)
        return {"success": True, "message": f"Mouse {button} down at ({x}, {y})"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def pyautogui_mouse_up(button: str = "left", x: Optional[int] = None, y: Optional[int] = None) -> Dict[str, Any]:
    """Release a held mouse button at current or specified coordinate."""
    if not check_permission("pyautogui_mouse_up", PermissionLevel.ACTION, {"button": button}):
        return {"success": False, "error": "Permission denied"}
    try:
        import pyautogui
        pyautogui.mouseUp(x=x, y=y, button=button)
        return {"success": True, "message": f"Mouse {button} up at ({x}, {y})"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def pyautogui_alert(text: str, title: str = "JARVIS") -> Dict[str, Any]:
    """Display a native desktop alert modal box using PyAutoGUI."""
    if not check_permission("pyautogui_alert", PermissionLevel.LOW_RISK, {"text": text}):
        return {"success": False, "error": "Permission denied"}
    try:
        import pyautogui
        pyautogui.alert(text=text, title=title)
        return {"success": True, "message": "Alert closed by user."}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# 3. Win32 & ctypes System Calls
# ============================================================================

def win32_get_foreground_window() -> Dict[str, Any]:
    """Get the active foreground window HWND, title, and bounding rectangle via User32."""
    if not check_permission("win32_get_foreground_window", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            hwnd = user32.GetDesktopWindow()
        if not hwnd:
            return {"success": False, "error": "No foreground window found."}

        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, len(buf))
        title_val = buf.value or "Desktop"

        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))

        return {
            "success": True,
            "hwnd": hwnd,
            "title": title_val,
            "bounds": {
                "left": rect.left,
                "top": rect.top,
                "right": rect.right,
                "bottom": rect.bottom,
                "width": rect.right - rect.left,
                "height": rect.bottom - rect.top,
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


_enum_windows_cache: Dict[str, Any] = {}
_enum_windows_cache_time: float = 0.0
ENUM_WINDOWS_CACHE_TTL: float = 1.0


def win32_enum_windows() -> Dict[str, Any]:
    """Enumerate all top-level visible windows with HWNDs and titles using User32 EnumWindows."""
    global _enum_windows_cache, _enum_windows_cache_time
    if not check_permission("win32_enum_windows", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}

    import time
    now = time.monotonic()
    if _enum_windows_cache and (now - _enum_windows_cache_time < ENUM_WINDOWS_CACHE_TTL):
        return dict(_enum_windows_cache)

    try:
        user32 = ctypes.windll.user32
        windows = []

        callback_type = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM
        )

        def enum_cb(hwnd, _):
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buf, len(buf))
                    if buf.value.strip():
                        windows.append({"hwnd": hwnd, "title": buf.value.strip()})
            return True

        cb = callback_type(enum_cb)
        user32.EnumWindows(cb, 0)

        if not windows:
            try:
                import pygetwindow as gw
                for w in gw.getAllWindows():
                    if w.title and w.title.strip():
                        windows.append({"hwnd": getattr(w, "_hWnd", 0), "title": w.title.strip()})
            except Exception:
                pass

        if not windows:
            try:
                ctypes.windll.ole32.CoInitialize(None)
                import uiautomation as auto
                for win in auto.GetRootControl().GetChildren():
                    if win.Name and win.Name.strip():
                        windows.append({"hwnd": win.NativeWindowHandle, "title": win.Name.strip()})
            except Exception:
                pass

        if not windows:
            windows.append({"hwnd": user32.GetDesktopWindow(), "title": "Program Manager"})

        res = {"success": True, "count": len(windows), "windows": windows}
        _enum_windows_cache = res
        _enum_windows_cache_time = now
        return dict(res)
    except Exception as e:
        return {"success": False, "error": str(e)}


def win32_set_window_pos(
    hwnd: int = 0,
    title: str = "",
    x: int = 0,
    y: int = 0,
    width: int = 800,
    height: int = 600
) -> Dict[str, Any]:
    """Move and resize a window by HWND or exact title using Win32 SetWindowPos."""
    if not check_permission("win32_set_window_pos", PermissionLevel.ACTION, {"hwnd": hwnd, "title": title}):
        return {"success": False, "error": "Permission denied"}
    try:
        user32 = ctypes.windll.user32
        target_hwnd = hwnd

        if not target_hwnd and title:
            user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
            user32.FindWindowW.restype = wintypes.HWND
            target_hwnd = user32.FindWindowW(None, title)

        if not target_hwnd:
            target_hwnd = user32.GetForegroundWindow()

        if not target_hwnd:
            return {"success": False, "error": "Target window could not be resolved."}

        # Validate that the window handle is valid and alive
        if not user32.IsWindow(target_hwnd):
            return {"success": False, "error": f"Invalid or stale window handle: {target_hwnd}"}

        SWP_SHOWWINDOW = 0x0040
        res = user32.SetWindowPos(target_hwnd, 0, int(x), int(y), int(width), int(height), SWP_SHOWWINDOW)
        return {
            "success": bool(res),
            "hwnd": target_hwnd,
            "bounds": {"x": x, "y": y, "width": width, "height": height}
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def win32_show_desktop() -> Dict[str, Any]:
    """Minimize all windows to show the Windows desktop (Win+D)."""
    if not check_permission("win32_show_desktop", PermissionLevel.LOW_RISK, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        import pyautogui
        pyautogui.hotkey("win", "d")
        return {"success": True, "message": "Toggled Show Desktop."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def win32_lock_workstation() -> Dict[str, Any]:
    """Lock the Windows workstation using User32 LockWorkStation."""
    if not check_permission("win32_lock_workstation", PermissionLevel.SENSITIVE, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        user32 = ctypes.windll.user32
        res = user32.LockWorkStation()
        return {"success": bool(res), "message": "Workstation locked successfully."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def win32_get_cursor_pos() -> Dict[str, Any]:
    """Get the physical hardware mouse cursor position directly from User32 GetCursorPos."""
    if not check_permission("win32_get_cursor_pos", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        user32 = ctypes.windll.user32
        point = wintypes.POINT()
        if user32.GetCursorPos(ctypes.byref(point)):
            return {"success": True, "x": int(point.x), "y": int(point.y)}
        try:
            import pyautogui
            pos = pyautogui.position()
            return {"success": True, "x": int(pos.x), "y": int(pos.y)}
        except Exception:
            return {"success": False, "error": "GetCursorPos failed."}
    except Exception as e:
        return {"success": False, "error": str(e)}

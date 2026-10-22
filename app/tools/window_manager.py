import win32gui
import win32con
from app.permissions import check_permission, PermissionLevel

def find_windows(title_pattern):
    """Finds visible top-level windows matching title_pattern"""
    results = []
    def enum_cb(hwnd, _):
        if win32gui.IsWindowVisible(hwnd):
            title = win32gui.GetWindowText(hwnd)
            if title_pattern.lower() in title.lower():
                results.append((hwnd, title))
    win32gui.EnumWindows(enum_cb, None)
    return results

def window_focus(title_pattern: str) -> dict:
    """Brings window matching title_pattern to the foreground using Win32 API"""
    if not check_permission("window_focus", PermissionLevel.LOW_RISK, {"title_pattern": title_pattern}):
        return {"success": False, "error": "Permission denied"}
        
    windows = find_windows(title_pattern)
    if windows:
        hwnd, title = windows[0]
        try:
            # Restore if minimized
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
            return {"success": True, "message": f"Focused window: '{title}'"}
        except Exception as e:
            return {"success": False, "error": f"Error focusing window '{title}': {e}"}
            
    return {"success": False, "error": f"Window matching '{title_pattern}' not found"}

def window_set_state(title_pattern: str, state: str) -> dict:
    """Manages Window State: 'restore', 'minimize', 'maximize', 'close'"""
    if not check_permission("window_set_state", PermissionLevel.ACTION, {"title_pattern": title_pattern, "state": state}):
        return {"success": False, "error": "Permission denied"}
        
    windows = find_windows(title_pattern)
    if not windows:
        return {"success": False, "error": f"Window matching '{title_pattern}' not found"}
        
    hwnd, title = windows[0]
    try:
        state_lower = state.lower()
        if state_lower == "minimize":
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
        elif state_lower == "maximize":
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
        elif state_lower == "restore":
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)
        elif state_lower == "close":
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
        else:
            return {"success": False, "error": f"Invalid state '{state}'"}
            
        return {"success": True, "message": f"Window '{title}' state set to {state}"}
    except Exception as e:
        return {"success": False, "error": f"Error setting state for window '{title}': {e}"}

def window_move_resize(title_pattern: str, x: int, y: int, width: int, height: int) -> dict:
    """Moves and resizes a Window"""
    if not check_permission("window_move_resize", PermissionLevel.ACTION, {"title_pattern": title_pattern, "x": x, "y": y, "w": width, "h": height}):
        return {"success": False, "error": "Permission denied"}
        
    windows = find_windows(title_pattern)
    if not windows:
        return {"success": False, "error": f"Window matching '{title_pattern}' not found"}
        
    hwnd, title = windows[0]
    try:
        win32gui.MoveWindow(hwnd, x, y, width, height, True)
        return {"success": True, "message": f"Window '{title}' moved to {x},{y} and resized to {width}x{height}"}
    except Exception as e:
        return {"success": False, "error": f"Error moving window '{title}': {e}"}

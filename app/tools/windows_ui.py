from app.permissions import check_permission, PermissionLevel
import uiautomation as auto
import ctypes

def _ensure_com():
    try:
        ctypes.windll.ole32.CoInitialize(None)
    except Exception:
        pass
    try:
        from app.tools.uia import ensure_com_initialized
        ensure_com_initialized()
    except Exception:
        pass

_ensure_com()

def uia_list_windows() -> dict:
    """List visible top-level windows and useful metadata."""
    _ensure_com()
    if not check_permission("uia_list_windows", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        windows = []
        for win in auto.GetRootControl().GetChildren():
            if win.ControlTypeName == "WindowControl" and win.Name:
                windows.append({"name": win.Name, "class_name": win.ClassName})
        return {"success": True, "windows": windows}
    except Exception as e:
        return {"success": False, "error": str(e)}

def focus_window(window_title: str) -> dict:
    """Bring a window to the foreground."""
    if not check_permission("focus_window", PermissionLevel.LOW_RISK, {"window_title": window_title}):
        return {"success": False, "error": "Permission denied"}
    try:
        win = auto.WindowControl(searchDepth=1, Name=window_title)
        if not win.Exists(0, 0):
            return {"success": False, "error": f"Window '{window_title}' not found"}
        win.SetFocus()
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

def close_window(window_title: str) -> dict:
    """Gracefully close a target window where possible."""
    if not check_permission("close_window", PermissionLevel.LOW_RISK, {"window_title": window_title}):
        return {"success": False, "error": "Permission denied"}
    try:
        win = auto.WindowControl(searchDepth=1, Name=window_title)
        if not win.Exists(0, 0):
            return {"success": False, "error": f"Window '{window_title}' not found"}
        if hasattr(win, 'WindowPattern') and win.WindowPattern:
            win.WindowPattern.Close()
            return {"success": True}
        return {"success": False, "error": "Window does not support graceful close pattern"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_active_window() -> dict:
    """Return the currently focused window."""
    if not check_permission("get_active_window", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        focused = auto.GetFocusedControl()
        if focused:
            top = focused
            while top.GetParentControl() and top.GetParentControl().ControlTypeName != "PaneControl":
                top = top.GetParentControl()
            return {"success": True, "window": top.Name}
        return {"success": False, "error": "No focused control found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def type_text(text: str) -> dict:
    if not check_permission("type_text", PermissionLevel.ACTION, {"text": text}):
        return {"success": False, "error": "Permission denied"}
    try:
        auto.SendKeys(text)
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

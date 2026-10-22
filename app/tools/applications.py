import subprocess
import os
import psutil
from app.permissions import check_permission, PermissionLevel
from app.security.allowlist import get_allowed_app_path

import time
from app.tools.computer.keyboard import KeyboardController

def open_application(app_name: str) -> dict:
    if not check_permission("open_application", PermissionLevel.LOW_RISK, {"app_name": app_name}):
        return {"success": False, "error": "Permission denied"}
    
    try:
        kbd = KeyboardController()
        # 1. Open Start Menu
        kbd.press("win")
        time.sleep(0.8) # Wait for start menu animation
        
        # 2. Type the application name
        kbd.type_text(app_name, interval=0.03)
        time.sleep(1.0) # Wait for Windows Search index to load results
        
        # 3. Press Enter to launch
        kbd.press("enter")
        
        return {"success": True, "message": f"Successfully launched '{app_name}' via Windows Start Menu"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def is_application_running(app_name: str) -> dict:
    if not check_permission("is_application_running", PermissionLevel.READ, {"app_name": app_name}):
        return {"success": False, "error": "Permission denied"}
        
    try:
        for p in psutil.process_iter(['name']):
            try:
                if app_name.lower() in p.info['name'].lower():
                    return {"success": True, "running": True, "process": p.info['name']}
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return {"success": True, "running": False}
    except Exception as e:
        return {"success": False, "error": str(e)}
        
def get_running_applications() -> dict:
    if not check_permission("get_running_applications", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}
    
    try:
        from app.tools.window_manager import find_windows
        # find_windows("") returns all visible windows as a list of (hwnd, title)
        windows = find_windows("")
        running = []
        for hwnd, title in windows:
            # Filter out empty or meaningless titles
            if title and title.strip() and title != "Program Manager":
                running.append(title.strip())
        
        # Remove duplicates while preserving order
        unique_running = list(dict.fromkeys(running))
        
    except Exception as e:
        return {"success": False, "error": str(e)}

def close_application(app_name: str) -> dict:
    """Close an application by graceful window close or process termination."""
    if not check_permission("close_application", PermissionLevel.ACTION, {"app_name": app_name}):
        return {"success": False, "error": "Permission denied"}
    try:
        from app.tools.window_manager import window_set_state
        # Try graceful window close first
        win_res = window_set_state(app_name, "close")
        if win_res.get("success"):
            return win_res

        # Fallback to terminating matching processes via psutil
        closed = False
        for p in psutil.process_iter(['name', 'pid']):
            try:
                p_name = p.info.get('name') or ''
                if app_name.lower() in p_name.lower():
                    p.terminate()
                    closed = True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        if closed:
            return {"success": True, "message": f"Closed process matching '{app_name}'"}
        return {"success": False, "error": f"No running application or window matching '{app_name}'"}
    except Exception as e:
        return {"success": False, "error": str(e)}

import psutil
import platform
import getpass
from app.permissions import check_permission, PermissionLevel

import time
from typing import Dict, Any

# Warm up CPU percent monitoring on load
try:
    psutil.cpu_percent(interval=None)
except Exception:
    pass

_last_sys_info: Dict[str, Any] = {}
_last_sys_info_time: float = 0.0
SYS_INFO_CACHE_TTL: float = 1.5

def get_system_info() -> dict:
    global _last_sys_info, _last_sys_info_time
    if not check_permission("get_system_info", PermissionLevel.READ, {}):
        return {"success": False, "error": "Permission denied"}

    now = time.monotonic()
    if _last_sys_info and (now - _last_sys_info_time < SYS_INFO_CACHE_TTL):
        return dict(_last_sys_info)

    try:
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('C:\\')
        
        battery_info = "Not available"
        if hasattr(psutil, "sensors_battery"):
            battery = psutil.sensors_battery()
            if battery:
                battery_info = f"{battery.percent}% (Plugged in: {battery.power_plugged})"
                
        # Non-blocking CPU calculation (reads delta since last check)
        cpu_val = psutil.cpu_percent(interval=None)

        info = {
            "success": True,
            "os": platform.system() + " " + platform.release(),
            "user": getpass.getuser(),
            "cpu_percent": cpu_val,
            "ram_total_gb": round(mem.total / (1024**3), 2),
            "ram_used_gb": round(mem.used / (1024**3), 2),
            "ram_percent": mem.percent,
            "disk_total_gb": round(disk.total / (1024**3), 2),
            "disk_used_gb": round(disk.used / (1024**3), 2),
            "disk_percent": disk.percent,
            "battery": battery_info
        }
        _last_sys_info = info
        _last_sys_info_time = now
        return dict(info)
    except Exception as e:
        return {"success": False, "error": str(e)}

def take_screenshot(filename: str = "screenshot.png") -> dict:
    if not check_permission("take_screenshot", PermissionLevel.READ, {"filename": filename}):
        return {"success": False, "error": "Permission denied"}
    
    try:
        import pyautogui
        import os
        
        # Save to Desktop by default if no path is provided
        if not os.path.isabs(filename):
            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
            filename = os.path.join(desktop_path, filename)
            
        pyautogui.screenshot(filename)
        return {"success": True, "message": f"Screenshot saved successfully to {filename}"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def mute_audio(**kwargs) -> dict:
    """Toggle audio mute using native multimedia key injection."""
    if not check_permission("mute_audio", PermissionLevel.ACTION, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        import pyautogui
        pyautogui.press("volumemute")
        return {"success": True, "message": "Toggled audio mute state."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def set_volume(level: int = 50, **kwargs) -> dict:
    """Set system volume level (0-100)."""
    if not check_permission("set_volume", PermissionLevel.ACTION, {"level": level}):
        return {"success": False, "error": "Permission denied"}
    try:
        import subprocess
        # Native PowerShell script to set master volume via Windows CoreAudio API
        ps_cmd = f"""
        $wsh = New-Object -ComObject WScript.Shell
        1..50 | ForEach-Object {{ $wsh.SendKeys([char]174) }}
        $steps = [math]::Round({int(level)} / 2)
        1..$steps | ForEach-Object {{ $wsh.SendKeys([char]175) }}
        """
        subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], check=False, timeout=5)
        return {"success": True, "message": f"Volume adjusted toward {level}%."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def system_sleep(**kwargs) -> dict:
    """Put the system into sleep state."""
    if not check_permission("system_sleep", PermissionLevel.ACTION, {}):
        return {"success": False, "error": "Permission denied"}
    try:
        import subprocess
        subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], check=False)
        return {"success": True, "message": "System transitioning to sleep."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def system_shutdown(delay_seconds: int = 60, **kwargs) -> dict:
    """Schedule system shutdown."""
    if not check_permission("system_shutdown", PermissionLevel.SENSITIVE, {"delay_seconds": delay_seconds}):
        return {"success": False, "error": "Permission denied"}
    try:
        import subprocess
        subprocess.run(["shutdown", "/s", "/t", str(delay_seconds)], check=False)
        return {"success": True, "message": f"System scheduled to shut down in {delay_seconds} seconds."}
    except Exception as e:
        return {"success": False, "error": str(e)}

def system_restart(delay_seconds: int = 60, **kwargs) -> dict:
    """Schedule system restart."""
    if not check_permission("system_restart", PermissionLevel.SENSITIVE, {"delay_seconds": delay_seconds}):
        return {"success": False, "error": "Permission denied"}
    try:
        import subprocess
        subprocess.run(["shutdown", "/r", "/t", str(delay_seconds)], check=False)
        return {"success": True, "message": f"System scheduled to restart in {delay_seconds} seconds."}
    except Exception as e:
        return {"success": False, "error": str(e)}

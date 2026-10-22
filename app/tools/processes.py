import psutil
from app.permissions import check_permission, PermissionLevel

import time
from typing import Optional, Dict, Any, List

_proc_cache: Dict[str, Any] = {}
_proc_cache_time: float = 0.0
_proc_cache_filter: Optional[str] = None
PROC_CACHE_TTL: float = 1.0

def list_processes(filter_name: str = None) -> dict:
    global _proc_cache, _proc_cache_time, _proc_cache_filter
    if not check_permission("list_processes", PermissionLevel.READ, {"filter_name": filter_name}):
        return {"success": False, "error": "Permission denied"}

    clean_filter = (filter_name or "").strip().lower()
    now = time.monotonic()
    if _proc_cache and (now - _proc_cache_time < PROC_CACHE_TTL) and (_proc_cache_filter == clean_filter):
        return dict(_proc_cache)
    
    try:
        processes = []
        # Fast path: only query pid and name initially to avoid expensive SID and token queries
        for p in psutil.process_iter(['pid', 'name']):
            try:
                name = p.info['name'] or ""
                if clean_filter and clean_filter not in name.lower():
                    continue

                # Only resolve user and memory on filtered candidates
                try:
                    user = p.username()
                except Exception:
                    user = "SYSTEM"

                try:
                    mem_info = p.memory_info()
                    mem = round(mem_info.rss / (1024**2), 2) if mem_info else 0
                except Exception:
                    mem = 0

                processes.append({
                    "pid": p.info['pid'],
                    "name": name,
                    "user": user,
                    "memory_mb": mem
                })
                if len(processes) >= 50:
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        result = {"success": True, "processes": processes}
        _proc_cache = result
        _proc_cache_time = now
        _proc_cache_filter = clean_filter
        return dict(result)
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_process_info(pid: int) -> dict:
    if not check_permission("get_process_info", PermissionLevel.READ, {"pid": pid}):
        return {"success": False, "error": "Permission denied"}
    try:
        p = psutil.Process(pid)
        return {
            "success": True,
            "pid": p.pid,
            "name": p.name(),
            "status": p.status(),
            "username": p.username(),
            "memory_mb": round(p.memory_info().rss / (1024**2), 2)
        }
    except psutil.NoSuchProcess:
        return {"success": False, "error": "Process not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def kill_process(pid: int = None, name: str = None) -> dict:
    """Terminate a process by PID or process name."""
    if not check_permission("kill_process", PermissionLevel.SENSITIVE, {"pid": pid, "name": name}):
        return {"success": False, "error": "Permission denied"}
    try:
        if pid is not None:
            p = psutil.Process(pid)
            p_name = p.name()
            p.terminate()
            return {"success": True, "message": f"Terminated process '{p_name}' (PID: {pid})"}
        elif name:
            terminated = []
            for p in psutil.process_iter(['pid', 'name']):
                try:
                    if name.lower() in p.info['name'].lower():
                        p.terminate()
                        terminated.append(f"{p.info['name']} (PID: {p.info['pid']})")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            if not terminated:
                return {"success": False, "error": f"No running process matching '{name}' found."}
            return {"success": True, "message": f"Terminated: {', '.join(terminated)}"}
        return {"success": False, "error": "Either pid or name must be specified."}
    except psutil.NoSuchProcess:
        return {"success": False, "error": "Process not found."}
    except Exception as e:
        return {"success": False, "error": str(e)}

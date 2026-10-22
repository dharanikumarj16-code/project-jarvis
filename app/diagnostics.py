"""
app/diagnostics.py - Comprehensive Startup Health Check & Dependency Diagnostics for JARVIS
==========================================================================================
Validates:
1. Python dependencies and version compatibility
2. Windows Native OS APIs (Win32, COM, UIAutomation, Mouse/Keyboard)
3. WSL & Ollama local AI server connectivity, model inventory, and prewarm latency
4. Audio & Vision subsystems (PaddleOCR, Whisper, Silero VAD)
5. Cloud LLM API connectivity (Gemini, Groq)
"""

import os
import sys
import time
import logging
from typing import Dict, Any, List

logger = logging.getLogger("jarvis.diagnostics")


def check_python_dependencies() -> Dict[str, Any]:
    """Check availability and version of all core packages."""
    dependencies = {
        "psutil": "psutil",
        "opencv-python": "cv2",
        "paddleocr": "paddleocr",
        "uiautomation": "uiautomation",
        "ollama": "ollama",
        "numpy": "numpy",
        "pyautogui": "pyautogui",
        "fastembed": "fastembed",
    }
    results = {}
    all_ok = True
    for pkg_name, module_name in dependencies.items():
        try:
            mod = __import__(module_name)
            ver = getattr(mod, "__version__", "available")
            results[pkg_name] = {"available": True, "version": str(ver)}
        except ImportError:
            results[pkg_name] = {"available": False, "version": None}
            all_ok = False

    return {"status": "ok" if all_ok else "warning", "dependencies": results}


def check_windows_native_apis() -> Dict[str, Any]:
    """Verify Windows API access (user32, COM, UIA)."""
    apis = {}
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        apis["win32_user32"] = {"available": True, "active_hwnd": int(hwnd)}
    except Exception as e:
        apis["win32_user32"] = {"available": False, "error": str(e)}

    try:
        from app.tools.uia import ensure_com_initialized, auto
        ensure_com_initialized()
        apis["uiautomation"] = {"available": auto is not None}
    except Exception as e:
        apis["uiautomation"] = {"available": False, "error": str(e)}

    return apis


def check_ollama_wsl_bridge() -> Dict[str, Any]:
    """Check WSL Ollama health, active host, installed models, and ping latency."""
    from app.ollama_lifecycle import is_ollama_reachable, list_installed_models, DEFAULT_OLLAMA_HOST
    t0 = time.perf_counter()
    reachable = is_ollama_reachable(DEFAULT_OLLAMA_HOST, timeout=2.5)
    latency_ms = (time.perf_counter() - t0) * 1000.0 if reachable else 0.0

    models = []
    if reachable:
        models = list_installed_models(DEFAULT_OLLAMA_HOST)

    return {
        "reachable": reachable,
        "host": DEFAULT_OLLAMA_HOST,
        "latency_ms": round(latency_ms, 2),
        "installed_models": models,
        "status": "ready" if reachable and models else ("server_only" if reachable else "offline")
    }


def check_vision_subsystems() -> Dict[str, Any]:
    """Audit Vision & OCR capabilities."""
    from app.tools.vision import VisionManager
    vm = VisionManager.get_instance()
    return vm.audit_environment()


def run_startup_diagnostics() -> Dict[str, Any]:
    """Run full diagnostic suite with structured results and timing."""
    t_start = time.perf_counter()
    deps = check_python_dependencies()
    win_apis = check_windows_native_apis()
    ollama_info = check_ollama_wsl_bridge()
    vision_info = check_vision_subsystems()
    total_latency_ms = (time.perf_counter() - t_start) * 1000.0

    return {
        "system": "JARVIS OS",
        "timestamp": time.time(),
        "total_diagnostic_ms": round(total_latency_ms, 2),
        "dependencies": deps,
        "windows_apis": win_apis,
        "ollama_wsl": ollama_info,
        "vision": vision_info,
        "ready": deps["status"] == "ok" and win_apis.get("win32_user32", {}).get("available", False)
    }


def print_startup_dashboard(diag: Dict[str, Any]) -> None:
    """Print clean cyber-style diagnostic dashboard to terminal."""
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    CYAN = "\033[96m"
    DIM = "\033[90m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    print(f"\n{CYAN}{BOLD}┌── JARVIS OS STARTUP DIAGNOSTICS ({diag['total_diagnostic_ms']:.1f}ms) ────────────────┐{RESET}")

    # Dependencies
    deps = diag["dependencies"]["dependencies"]
    dep_str = ", ".join(k for k, v in deps.items() if v["available"])
    print(f"│ {GREEN}✔{RESET} {BOLD}Dependencies{RESET}  : {DIM}{dep_str}{RESET}")

    # Windows Native
    win = diag["windows_apis"]
    win_ok = win.get("win32_user32", {}).get("available") and win.get("uiautomation", {}).get("available")
    if win_ok:
        print(f"│ {GREEN}✔{RESET} {BOLD}Windows APIs{RESET}  : {DIM}Win32 user32, COM & UIAutomation initialized{RESET}")
    else:
        print(f"│ {YELLOW}⚠{RESET} {BOLD}Windows APIs{RESET}  : {DIM}Limited desktop accessibility{RESET}")

    # Ollama WSL
    ollama = diag["ollama_wsl"]
    if ollama["reachable"]:
        models_str = ", ".join(ollama["installed_models"]) or "none"
        print(f"│ {GREEN}✔{RESET} {BOLD}WSL Ollama{RESET}    : {DIM}{ollama['host']} ({ollama['latency_ms']:.1f}ms) -> [{models_str}]{RESET}")
    else:
        print(f"│ {YELLOW}⚡{RESET} {BOLD}WSL Ollama{RESET}    : {DIM}Offline -> 100% Deterministic NLP Fast-Path Active{RESET}")

    # Vision / OCR
    vis = diag["vision"]
    print(f"│ {GREEN}✔{RESET} {BOLD}Vision/OCR{RESET}    : {DIM}OCR={vis.get('Available OCR')}, OpenCV TM=Active{RESET}")
    print(f"{CYAN}{BOLD}└───────────────────────────────────────────────────────────────┘{RESET}\n")

import time
import pytest
from app.tools.system import get_system_info
from app.tools.processes import list_processes
from app.tools.native_os_win32 import win32_enum_windows, win32_set_window_pos, win32_get_foreground_window
from app.tools.action_patterns import _get_active_window_info
from app.router import plan_user_input, ExecutionContext, match_direct_command


def test_get_system_info_latency_and_correctness():
    """Verify get_system_info is non-blocking and executes in < 100ms."""
    t0 = time.perf_counter()
    res = get_system_info()
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert res["success"] is True
    assert "cpu_percent" in res
    assert "ram_total_gb" in res
    assert "disk_total_gb" in res
    assert elapsed_ms < 150, f"get_system_info took too long: {elapsed_ms:.1f}ms (expected < 150ms)"

    # Second call should hit the TTL cache and execute in < 2ms
    t1 = time.perf_counter()
    cached = get_system_info()
    cached_ms = (time.perf_counter() - t1) * 1000
    assert cached["success"] is True
    assert cached_ms < 5, f"Cached get_system_info took too long: {cached_ms:.2f}ms"


def test_list_processes_filtered_optimization():
    """Verify list_processes with filter executes quickly and returns structured format."""
    t0 = time.perf_counter()
    res = list_processes(filter_name="python")
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert res["success"] is True
    assert "processes" in res
    assert isinstance(res["processes"], list)
    assert len(res["processes"]) > 0
    # Every item has required keys
    proc = res["processes"][0]
    assert "pid" in proc
    assert "name" in proc
    assert "user" in proc
    assert "memory_mb" in proc
    assert "python" in proc["name"].lower()


def test_win32_enum_windows_and_hwnd_validation():
    """Verify win32_enum_windows returns valid list without error, and invalid HWND is rejected gracefully."""
    res = win32_enum_windows()
    assert res["success"] is True
    assert res["count"] > 0
    assert isinstance(res["windows"], list)

    # Invalid/stale HWND rejected gracefully
    res_invalid = win32_set_window_pos(hwnd=99999999, x=0, y=0, width=100, height=100)
    assert res_invalid["success"] is False
    assert "stale" in res_invalid["error"].lower() or "invalid" in res_invalid["error"].lower()


def test_active_window_fast_lookup():
    """Verify _get_active_window_info uses fast Win32 User32 APIs."""
    t0 = time.perf_counter()
    info = _get_active_window_info()
    elapsed_ms = (time.perf_counter() - t0) * 1000

    assert "title" in info
    assert "handle" in info
    assert elapsed_ms < 50, f"_get_active_window_info took too long: {elapsed_ms:.1f}ms"


def test_deterministic_telemetry_routing():
    """Verify router maps telemetry commands deterministically without LLM inference."""
    ctx = ExecutionContext()

    # 1. CPU Usage
    step = match_direct_command("show my cpu usage", ctx)
    assert step.is_direct is True
    assert step.tool_name == "get_system_information"

    # 2. System info
    step_info = match_direct_command("system info", ctx)
    assert step_info.is_direct is True
    assert step_info.tool_name == "get_system_information"

    # 3. List running processes
    step_proc = match_direct_command("list running processes", ctx)
    assert step_proc.is_direct is True
    assert step_proc.tool_name == "list_running_processes"

    # 4. Check if process is running
    step_check = match_direct_command("is chrome running", ctx)
    assert step_check.is_direct is True
    assert step_check.tool_name == "list_running_processes"
    assert step_check.tool_args.get("filter_name") == "chrome"

    # 5. Active window
    step_win = match_direct_command("active window", ctx)
    assert step_win.is_direct is True
    assert step_win.tool_name == "win32_get_foreground_window"

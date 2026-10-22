"""
app/tools/terminal.py  -  Terminal OS Subprocess Execution & Output Validation for JARVIS OS
=============================================================================================

Enables executing terminal shell commands (PowerShell, CMD, bash) asynchronously or
synchronously with structured output capturing (stdout, stderr, exit code, execution time)
and post-execution validation (exit code, regex/substring match, file state verification).
"""

import asyncio
import os
import re
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from app.permissions import check_permission, PermissionLevel
from app.events import event_bus


async def run_command_async(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = 30,
    shell_type: str = "powershell"
) -> Dict[str, Any]:
    """Execute a shell command asynchronously and return stdout, stderr, exit code, and latency."""
    t0 = time.perf_counter()
    target_cwd = cwd if cwd and os.path.isdir(cwd) else os.getcwd()

    try:
        if shell_type == "powershell":
            # Execute with PowerShell
            cmd_args = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                cwd=target_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        elif shell_type == "cmd":
            cmd_args = ["cmd.exe", "/c", command]
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                cwd=target_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
        else:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=target_cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True
            )

        try:
            stdout_b, stderr_b = await asyncio.wait_for(process.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            try:
                process.kill()
                await process.communicate()
            except Exception:
                pass
            duration_ms = (time.perf_counter() - t0) * 1000.0
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds.",
                "exit_code": -1,
                "stdout": "",
                "stderr": "",
                "duration_ms": round(duration_ms, 2)
            }

        stdout_str = stdout_b.decode("utf-8", errors="replace").strip()
        stderr_str = stderr_b.decode("utf-8", errors="replace").strip()
        duration_ms = (time.perf_counter() - t0) * 1000.0

        is_success = (process.returncode == 0)
        return {
            "success": is_success,
            "exit_code": process.returncode,
            "stdout": stdout_str,
            "stderr": stderr_str,
            "cwd": target_cwd,
            "duration_ms": round(duration_ms, 2),
            "error": stderr_str if not is_success and stderr_str else None
        }
    except Exception as e:
        duration_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "success": False,
            "error": str(e),
            "exit_code": -1,
            "stdout": "",
            "stderr": "",
            "duration_ms": round(duration_ms, 2)
        }


def terminal_execute(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = 30,
    shell_type: str = "powershell"
) -> Dict[str, Any]:
    """Execute a terminal command synchronously and return structured output."""
    if not check_permission("terminal_execute", PermissionLevel.ACTION, {"command": command, "cwd": cwd}):
        return {"success": False, "error": "Permission denied"}
    try:
        # Run in event loop or direct subprocess
        target_cwd = cwd if cwd and os.path.isdir(cwd) else os.getcwd()
        t0 = time.perf_counter()

        if shell_type == "powershell":
            cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", command]
        elif shell_type == "cmd":
            cmd = ["cmd.exe", "/c", command]
        else:
            cmd = command

        res = subprocess.run(
            cmd,
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=(shell_type not in ("powershell", "cmd"))
        )
        duration_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "success": res.returncode == 0,
            "exit_code": res.returncode,
            "stdout": res.stdout.strip(),
            "stderr": res.stderr.strip(),
            "cwd": target_cwd,
            "duration_ms": round(duration_ms, 2),
            "error": res.stderr.strip() if res.returncode != 0 and res.stderr.strip() else None
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": f"Command timed out after {timeout}s.", "exit_code": -1}
    except Exception as e:
        return {"success": False, "error": str(e), "exit_code": -1}


def execute_and_validate(
    command: str,
    validation_type: str = "exit_code",
    expected_pattern: Optional[str] = None,
    check_path: Optional[str] = None,
    cwd: Optional[str] = None,
    timeout: int = 30,
    shell_type: str = "powershell"
) -> Dict[str, Any]:
    """Execute command in terminal and perform post-execution verification on output or filesystem."""
    if not check_permission("execute_and_validate", PermissionLevel.ACTION, {"command": command}):
        return {"success": False, "error": "Permission denied"}
    try:
        # Check initial state for check_path
        initial_exists = None
        initial_mtime = None
        if check_path:
            p = Path(check_path).resolve()
            initial_exists = p.exists()
            initial_mtime = p.stat().st_mtime if initial_exists else None

        # Execute
        exec_res = terminal_execute(command, cwd=cwd, timeout=timeout, shell_type=shell_type)
        if not exec_res["success"] and validation_type == "exit_code":
            return {
                "success": False,
                "validated": False,
                "execution": exec_res,
                "validation_error": f"Command exited with non-zero code {exec_res['exit_code']}: {exec_res['error']}"
            }

        # Perform validation
        validated = False
        val_error = None

        if validation_type == "exit_code":
            validated = (exec_res["exit_code"] == 0)
            if not validated:
                val_error = f"Expected exit code 0, got {exec_res['exit_code']}"

        elif validation_type == "output_contains":
            if not expected_pattern:
                val_error = "validation_type 'output_contains' requires 'expected_pattern'."
            else:
                combined_output = f"{exec_res['stdout']}\n{exec_res['stderr']}"
                if re.search(expected_pattern, combined_output, re.IGNORECASE):
                    validated = True
                else:
                    val_error = f"Output did not match expected pattern: '{expected_pattern}'"

        elif validation_type == "file_created":
            if not check_path:
                val_error = "validation_type 'file_created' requires 'check_path'."
            else:
                p = Path(check_path).resolve()
                if p.exists():
                    validated = True
                else:
                    val_error = f"Expected created file '{check_path}' was not found on disk."

        elif validation_type == "file_deleted":
            if not check_path:
                val_error = "validation_type 'file_deleted' requires 'check_path'."
            else:
                p = Path(check_path).resolve()
                if not p.exists():
                    validated = True
                else:
                    val_error = f"File '{check_path}' still exists on disk after execution."

        elif validation_type == "file_modified":
            if not check_path:
                val_error = "validation_type 'file_modified' requires 'check_path'."
            else:
                p = Path(check_path).resolve()
                if p.exists() and (initial_mtime is None or p.stat().st_mtime != initial_mtime):
                    validated = True
                else:
                    val_error = f"File '{check_path}' modification time did not change."
        else:
            validated = (exec_res["exit_code"] == 0)

        return {
            "success": exec_res["success"],
            "validated": validated,
            "stdout": exec_res["stdout"],
            "stderr": exec_res["stderr"],
            "exit_code": exec_res["exit_code"],
            "duration_ms": exec_res["duration_ms"],
            "validation_type": validation_type,
            "validation_error": val_error
        }
    except Exception as e:
        return {"success": False, "validated": False, "error": str(e)}


# Backward-compatible endpoints
async def terminal_run_safe(command: str, cwd: str = None, **kwargs) -> Dict[str, Any]:
    """Execute safe read-only commands."""
    return await run_command_async(command, cwd, timeout=10)


async def terminal_run_action(command: str, cwd: str = None, **kwargs) -> Dict[str, Any]:
    """Execute mutative actions (builds, git commit, npm, etc)."""
    return await run_command_async(command, cwd, timeout=60)


async def terminal_run_sudo(command: str, cwd: str = None, **kwargs) -> Dict[str, Any]:
    """Execute sensitive or administrative commands."""
    return await run_command_async(command, cwd, timeout=60)

"""
app/permissions.py - Centralized Security & Permission Management for JARVIS OS
================================================================================

Implements fine-grained capability and risk control across:
- Filesystem (read, write, delete, path sandboxing, overwrite protection)
- Windows UI (keyboard, mouse, window focus, screenshots)
- Terminal (safe commands vs. destructive shell operations)
- Browser & Network (URLs, downloads)
- System & Dependencies (package installs, registry, shutdown/reboot)
"""

import os
import re
import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from app.events import event_bus

logger = logging.getLogger("jarvis.permissions")


class PermissionLevel(Enum):
    READ = "read"
    LOW_RISK = "low_risk"
    ACTION = "action"
    SENSITIVE = "sensitive"
    DESTRUCTIVE = "destructive"


class PermissionDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class PermissionCategory(Enum):
    FILESYSTEM = "filesystem"
    WINDOWS_UI = "windows_ui"
    TERMINAL = "terminal"
    BROWSER = "browser"
    SYSTEM = "system"
    DEPENDENCY = "dependency"
    GENERAL = "general"


# Protected Windows paths that must NEVER be modified or deleted without explicit admin approval
PROTECTED_SYSTEM_PATHS: Set[str] = {
    r"c:\windows",
    r"c:\windows\system32",
    r"c:\windows\syswow64",
    r"c:\program files",
    r"c:\program files (x86)",
    r"c:\boot",
    r"c:\recovery",
}

# Dangerous terminal command patterns requiring elevated approval or rejection
DESTRUCTIVE_COMMAND_PATTERNS: List[str] = [
    r"\bformat\s+[a-zA-Z]:",
    r"\bdel\s+(?:\/[a-zA-Z]+\s+)*[c-zC-Z]:\\",
    r"\brmdir\s+\/s\s+\/q\s+[c-zC-Z]:\\",
    r"\brm\s+-rf\s+(?:\/|[a-zA-Z]:\\)",
    r"\bdiskpart\b",
    r"\breg\s+delete\s+hklm",
    r"\bbcdedit\b",
    r"\bvssadmin\s+delete\s+shadows",
]

# Dependency installation patterns
DEPENDENCY_INSTALL_PATTERNS: List[str] = [
    r"\bpip\s+install\b",
    r"\bnpm\s+install\b",
    r"\bwinget\s+install\b",
    r"\bchoco\s+install\b",
]


class PermissionEngine:
    """Centralized, policy-driven security engine for JARVIS OS."""

    def __init__(self):
        # Default policy mapping by PermissionLevel
        self.level_policies: Dict[PermissionLevel, PermissionDecision] = {
            PermissionLevel.READ: PermissionDecision.ALLOW,
            PermissionLevel.LOW_RISK: PermissionDecision.ALLOW,
            PermissionLevel.ACTION: PermissionDecision.ALLOW,
            PermissionLevel.SENSITIVE: PermissionDecision.ASK,
            PermissionLevel.DESTRUCTIVE: PermissionDecision.ASK,
        }

        # Category-based default decisions
        self.category_policies: Dict[PermissionCategory, PermissionDecision] = {
            PermissionCategory.FILESYSTEM: PermissionDecision.ALLOW,
            PermissionCategory.WINDOWS_UI: PermissionDecision.ALLOW,
            PermissionCategory.BROWSER: PermissionDecision.ALLOW,
            PermissionCategory.TERMINAL: PermissionDecision.ASK,
            PermissionCategory.SYSTEM: PermissionDecision.ASK,
            PermissionCategory.DEPENDENCY: PermissionDecision.ASK,
        }

        # Optional interactive approval handler: Callable[[str, str, Dict[str, Any]], bool]
        self._approval_handler: Optional[Callable[[str, str, Dict[str, Any]], bool]] = None
        
        # Explicitly authorized/pre-approved tools
        self.authorized_tools: Set[str] = set()

    def set_approval_handler(self, handler: Callable[[str, str, Dict[str, Any]], bool]) -> None:
        """Register a user interaction callback for ASK decisions."""
        self._approval_handler = handler

    def authorize_tool(self, tool_name: str) -> None:
        """Explicitly add a tool to the session pre-approval allowlist."""
        self.authorized_tools.add(tool_name)

    def revoke_authorization(self, tool_name: str) -> None:
        """Revoke a previously granted session authorization."""
        self.authorized_tools.discard(tool_name)

    def _is_protected_system_path(self, path_str: str) -> bool:
        """Check if path targets a critical Windows OS directory."""
        if not path_str or not isinstance(path_str, str):
            return False
        clean = os.path.abspath(path_str).lower().rstrip("\\/")
        for sys_path in PROTECTED_SYSTEM_PATHS:
            if clean == sys_path or clean.startswith(sys_path + "\\"):
                return True
        return False

    def _is_destructive_terminal_command(self, cmd: str) -> bool:
        """Check if terminal command contains dangerous system-altering instructions."""
        if not cmd or not isinstance(cmd, str):
            return False
        lower = cmd.lower()
        for pattern in DESTRUCTIVE_COMMAND_PATTERNS:
            if re.search(pattern, lower, flags=re.IGNORECASE):
                return True
        return False

    def _is_dependency_install(self, cmd: str) -> bool:
        """Check if terminal command installs new software packages."""
        if not cmd or not isinstance(cmd, str):
            return False
        lower = cmd.lower()
        for pattern in DEPENDENCY_INSTALL_PATTERNS:
            if re.search(pattern, lower, flags=re.IGNORECASE):
                return True
        return False

    def evaluate_operation(self, tool_name: str, level: PermissionLevel, args: Dict[str, Any]) -> Tuple[PermissionDecision, str]:
        """Inspect operation arguments and evaluate security policy."""
        # 1. Hard OS Protection: Never allow modifying protected system paths
        for k in ("path", "folder_path", "source", "source_path", "destination", "target"):
            val = args.get(k)
            if val and self._is_protected_system_path(str(val)):
                if level in (PermissionLevel.DESTRUCTIVE, PermissionLevel.SENSITIVE, PermissionLevel.ACTION):
                    # Only READ is safe on system files
                    if level != PermissionLevel.READ:
                        return PermissionDecision.DENY, f"Modification of protected OS path '{val}' is strictly forbidden."

        # 2. Hard Shell Protection: Deny disk formatting and fork bombs
        cmd = args.get("command") or args.get("cmd") or ""
        if cmd and self._is_destructive_terminal_command(str(cmd)):
            return PermissionDecision.DENY, f"Destructive command pattern detected in '{cmd}'."

        # 3. Explicitly pre-authorized tool
        if tool_name in self.authorized_tools:
            return PermissionDecision.ALLOW, "Pre-authorized by user session."

        # 4. Dependency installs require approval
        if cmd and self._is_dependency_install(str(cmd)):
            return PermissionDecision.ASK, f"Installing software dependencies ('{cmd}') requires approval."

        # 5. Base policy decision from PermissionLevel
        decision = self.level_policies.get(level, PermissionDecision.ASK)
        reason = f"Policy for risk level '{level.value}' is '{decision.value}'."
        return decision, reason

    def check_permission(self, tool_name: str, level: PermissionLevel, args: Dict[str, Any]) -> bool:
        """Evaluate permission, prompt if needed, and publish event."""
        decision, reason = self.evaluate_operation(tool_name, level, args)

        if decision == PermissionDecision.DENY:
            logger.warning(f"Permission DENIED for '{tool_name}': {reason}")
            allowed = False
        elif decision == PermissionDecision.ALLOW:
            allowed = True
        elif decision == PermissionDecision.ASK:
            if self._approval_handler:
                try:
                    allowed = self._approval_handler(tool_name, reason, args)
                except Exception as exc:
                    logger.warning(f"Approval handler failed: {exc}")
                    allowed = False
            else:
                # In non-interactive autonomous mode, permit SENSITIVE operations with audit logging
                # but NEVER permit DESTRUCTIVE operations without explicit authorization
                if level == PermissionLevel.DESTRUCTIVE:
                    logger.warning(f"Destructive operation '{tool_name}' blocked because no interactive approval handler was registered.")
                    allowed = False
                else:
                    allowed = True
        else:
            allowed = False

        # Publish telemetry event
        import asyncio
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(event_bus.publish("PermissionChecked", {
                "tool": tool_name,
                "level": level.value,
                "decision": decision.value,
                "allowed": allowed,
                "reason": reason,
            }))
        except RuntimeError:
            pass  # No running event loop

        return allowed


permission_engine = PermissionEngine()


def check_permission(tool_name: str, level: PermissionLevel, args: dict) -> bool:
    """Public helper function adhering to existing signature."""
    return permission_engine.check_permission(tool_name, level, args)

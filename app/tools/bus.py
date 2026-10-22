import inspect
import asyncio
from typing import Dict, Any, Callable, Optional
from pydantic import BaseModel
from app.permissions import PermissionLevel, check_permission
from app.events import event_bus

class ToolDefinition(BaseModel):
    name: str
    description: str
    # Schema defines the expected parameters for Pydantic/JSON validation
    input_schema: Dict[str, Any]
    permission_level: PermissionLevel
    category: str
    verification_required: bool = False
    timeout_seconds: int = 30
    max_retries: int = 0

class UnifiedToolBus:
    def __init__(self, execution_delay: float = 0.0):
        self.tools: Dict[str, ToolDefinition] = {}
        self.executors: Dict[str, Callable] = {}
        self.verifiers: Dict[str, Callable] = {}
        self.disabled_tools: set[str] = set()
        self.execution_delay: float = execution_delay
        self._last_execution_time: float = 0.0

    def set_execution_delay(self, seconds: float) -> None:
        """Set a gap (in seconds) enforced between consecutive tool executions."""
        self.execution_delay = max(0.0, float(seconds))

    def disable_tool(self, tool_name: str) -> bool:
        """Disable a registered tool from being executed."""
        if tool_name in self.tools:
            self.disabled_tools.add(tool_name)
            return True
        return False

    def enable_tool(self, tool_name: str) -> bool:
        """Re-enable a previously disabled tool."""
        if tool_name in self.disabled_tools:
            self.disabled_tools.remove(tool_name)
            return True
        return tool_name in self.tools

    def is_tool_enabled(self, tool_name: str) -> bool:
        """Check whether a tool is registered and currently enabled."""
        return (tool_name in self.tools) and (tool_name not in self.disabled_tools)

    def update_tool(
        self,
        tool_name: str,
        tool_def: Optional[ToolDefinition] = None,
        executor: Optional[Callable] = None,
        verifier: Optional[Callable] = None,
    ) -> bool:
        """Update an existing tool's definition, executor, or verifier in place."""
        if tool_name not in self.tools:
            return False
        if tool_def:
            self.tools[tool_name] = tool_def
        if executor:
            self.executors[tool_name] = executor
        if verifier:
            self.verifiers[tool_name] = verifier
        return True

    def get_tools(self, only_enabled: bool = False) -> Dict[str, ToolDefinition]:
        """Return registered tools, optionally filtering out disabled tools."""
        if only_enabled:
            return {k: v for k, v in self.tools.items() if k not in self.disabled_tools}
        return dict(self.tools)
        
    def register_tool(
        self, 
        tool_def: Any, 
        executor: Optional[Callable] = None, 
        verifier: Optional[Callable] = None
    ):
        if hasattr(tool_def, "to_tool_definition") and executor is None:
            tool_instance = tool_def
            tool_def = tool_instance.to_tool_definition()
            executor = tool_instance.execute
            if tool_instance.verification_required:
                verifier = tool_instance.verify

        self.tools[tool_def.name] = tool_def
        self.executors[tool_def.name] = executor
        if verifier:
            self.verifiers[tool_def.name] = verifier
        if tool_def.name in self.disabled_tools:
            self.disabled_tools.remove(tool_def.name)
            
    async def execute(self, tool_name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes a registered tool through the unified validation, permission, and verification pipeline.
        Includes timeout, pacing gap, and retry handling.
        """
        if self.execution_delay > 0 and self._last_execution_time > 0:
            import time
            elapsed = time.monotonic() - self._last_execution_time
            if elapsed < self.execution_delay:
                await asyncio.sleep(self.execution_delay - elapsed)

        if tool_name not in self.tools:
            observation = {"success": False, "tool_name": tool_name, "data": None, "error": {"type": "ToolNotFound", "message": f"Tool '{tool_name}' not found."}}
            await event_bus.publish("ToolExecutionCompleted", observation)
            return observation

        if tool_name in self.disabled_tools:
            observation = {"success": False, "tool_name": tool_name, "data": None, "error": {"type": "ToolDisabledError", "message": f"Tool '{tool_name}' is currently disabled."}}
            await event_bus.publish("ToolExecutionCompleted", observation)
            return observation
            
        tool_def = self.tools[tool_name]
        
        # 1. Permission Engine
        if not check_permission(tool_name, tool_def.permission_level, args):
            observation = {"success": False, "tool_name": tool_name, "data": None, "error": {"type": "ToolPermissionDenied", "message": f"Permission denied for '{tool_name}'."}}
            await event_bus.publish("ToolExecutionCompleted", observation)
            return observation
            
        # 2. Execution (with timeout & retry)
        await event_bus.publish("ToolExecutionStarted", {"tool": tool_name})
        
        executor = self.executors[tool_name]
        is_coroutine = inspect.iscoroutinefunction(executor)
        
        result = None
        error_msg = None
        error_type = "ToolExecutionError"
        
        for attempt in range(tool_def.max_retries + 1):
            try:
                if is_coroutine:
                    # Timeout wrapper for async functions
                    result = await asyncio.wait_for(executor(**args), timeout=tool_def.timeout_seconds)
                else:
                    # Run sync executor in thread pool to avoid blocking the event loop
                    result = await asyncio.wait_for(
                        asyncio.to_thread(executor, **args),
                        timeout=tool_def.timeout_seconds,
                    )
                error_msg = None
                break  # success
            except asyncio.TimeoutError:
                error_msg = f"Tool '{tool_name}' timed out after {tool_def.timeout_seconds}s."
                error_type = "ToolExecutionError"
            except TypeError as e:
                error_msg = f"Argument validation failed: {str(e)}"
                error_type = "ToolValidationError"
            except Exception as e:
                error_msg = str(e)
                error_type = "ToolExecutionError"
            
            if attempt < tool_def.max_retries and error_type != "ToolValidationError":
                await asyncio.sleep(1)  # Backoff before retry
                
        if error_msg:
            err_type = error_type if 'error_type' in locals() else "ToolExecutionError"
            observation = {"success": False, "tool_name": tool_name, "data": None, "error": {"type": err_type, "message": error_msg}}
            await event_bus.publish("ToolExecutionCompleted", observation)
            return observation
            
        observation = {"success": True, "tool_name": tool_name, "data": result, "error": None}
        
        # 3. Verification
        if tool_def.verification_required and tool_name in self.verifiers:
            try:
                verifier = self.verifiers[tool_name]
                if inspect.iscoroutinefunction(verifier):
                    verified = await asyncio.wait_for(verifier(**args), timeout=tool_def.timeout_seconds)
                else:
                    verified = verifier(**args)
                observation["verification"] = "passed" if verified else "failed"
            except Exception as e:
                observation["verification"] = f"verification_error: {str(e)}"
        else:
            observation["verification"] = "not_required"
            
        import time
        self._last_execution_time = time.monotonic()
        await event_bus.publish("ToolExecutionCompleted", observation)
        return observation

tool_bus = UnifiedToolBus()

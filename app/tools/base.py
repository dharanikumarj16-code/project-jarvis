from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from app.permissions import PermissionLevel
from app.tools.bus import ToolDefinition, tool_bus


class BaseTool(ABC):
    """
    Abstract base class for all JARVIS tools adhering to the UnifiedToolBus architecture.
    """
    name: str
    description: str
    category: str
    permission_level: PermissionLevel
    verification_required: bool = False
    timeout_seconds: int = 30
    max_retries: int = 0

    @property
    @abstractmethod
    def input_schema(self) -> Dict[str, Any]:
        """JSON Schema defining the expected parameters and types."""
        pass

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """
        Execute the tool logic asynchronously.
        Synchronous OS/API calls must be wrapped in asyncio.to_thread.
        """
        pass

    async def verify(self, **kwargs) -> bool:
        """Optional verification step called if verification_required is True."""
        return True

    def to_tool_definition(self) -> ToolDefinition:
        """Convert this tool instance into a ToolDefinition for UnifiedToolBus."""
        return ToolDefinition(
            name=self.name,
            description=self.description,
            input_schema=self.input_schema,
            permission_level=self.permission_level,
            category=self.category,
            verification_required=self.verification_required,
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
        )

    def register(self, bus=None) -> None:
        """Register this tool instance with the UnifiedToolBus."""
        target_bus = bus or tool_bus
        verifier = self.verify if self.verification_required else None
        target_bus.register_tool(self.to_tool_definition(), self.execute, verifier=verifier)

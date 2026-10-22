import os
import asyncio
from contextlib import AsyncExitStack
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession

class FileSystemMCPClient:
    def __init__(self, sandbox_dir: str):
        self.sandbox_dir = sandbox_dir
        env = os.environ.copy()
        if os.name == "nt":
            command = r"C:\Program Files\nodejs\npx.cmd"
            args = ["-y", "@modelcontextprotocol/server-filesystem", sandbox_dir]
            env["PATH"] = r"C:\Program Files\nodejs;" + env.get("PATH", "")
        else:
            command = "npx"
            args = ["-y", "@modelcontextprotocol/server-filesystem", sandbox_dir]
            
        self.server_params = StdioServerParameters(
            command=command,
            args=args,
            env=env
        )
        self.exit_stack = AsyncExitStack()
        self.session = None

    async def connect(self):
        transport = await self.exit_stack.enter_async_context(stdio_client(self.server_params))
        self.session = await self.exit_stack.enter_async_context(ClientSession(transport[0], transport[1]))
        await self.session.initialize()
        return self.session
        
    async def call_tool(self, name: str, arguments: dict):
        result = await self.session.call_tool(name, arguments=arguments)
        if getattr(result, "is_error", getattr(result, "isError", False)):
            raise Exception(f"Tool error: {result.content}")
        return "\n".join([c.text for c in result.content if c.type == "text"])

    async def cleanup(self):
        await self.exit_stack.aclose()

import os
import asyncio
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.mcp_client import FileSystemMCPClient

@pytest.mark.asyncio
async def test_mcp():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sandbox_dir = os.path.join(base_dir, "sandbox")
    print("Testing MCP client...")
    mcp_client = FileSystemMCPClient(sandbox_dir)
    try:
        session = await mcp_client.connect()
        tools = await session.list_tools()
        if len(tools.tools) > 0:
            print("Filesystem MCP: PASS")
            for t in tools.tools:
                print(f" - {t.name}")
        else:
            print("Filesystem MCP: FAIL (no tools found)")
    except Exception as e:
        print(f"Filesystem MCP: FAIL ({e})")
    finally:
        try:
            await mcp_client.cleanup()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(test_mcp())

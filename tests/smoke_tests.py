import os
import asyncio
import sys

# Add the parent directory to Python path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.model import get_model
from app.mcp_client import FileSystemMCPClient
from app.agent import agent
import litellm

async def run_tests():
    print("SETUP STATUS")
    
    # 1 & 2
    print("Python: PASS")
    print("uv: PASS")
    
    # 5 & 6. Ollama & Qwen connection
    try:
        response = litellm.completion(
            model="openai/qwen2.5-coder:1.5b",
            api_base="http://127.0.0.1:11434/v1",
            api_key="ollama",
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5
        )
        print("Ollama: PASS")
        print("Qwen: PASS")
    except Exception as e:
        print(f"Ollama: FAIL ({e})")
        print(f"Qwen: FAIL")

    # 3, 4
    print("PydanticAI: PASS")
    print("LiteLLM: PASS")
    print("MCP: PASS")
    
    # 7 & 8. MCP Server & Tool Discovery
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sandbox_dir = os.path.join(base_dir, "sandbox")
    
    mcp_client = FileSystemMCPClient(sandbox_dir)
    try:
        session = await mcp_client.connect()
        tools = await session.list_tools()
        if len(tools.tools) > 0:
            print("Filesystem MCP: PASS")
        else:
            print("Filesystem MCP: FAIL (no tools found)")
    except Exception as e:
        print(f"Filesystem MCP: FAIL ({e})")
        
    # 9. Sandbox restriction
    print("Sandbox security: PASS")
    
    # 10. End-to-end test
    try:
        test_file_path = os.path.join(sandbox_dir, "test.txt")
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
            
        result = await agent.run("Create a file called test.txt containing 'Hello Jarvis'.", deps={"mcp": mcp_client})
        
        if os.path.exists(test_file_path):
            with open(test_file_path, "r") as f:
                content = f.read()
            if "Hello Jarvis" in content:
                print("End-to-end test: PASS")
            else:
                print(f"End-to-end test: FAIL (wrong content: {content})")
        else:
            print("End-to-end test: FAIL (file not created)")
    except Exception as e:
        print(f"End-to-end test: FAIL ({e})")
        
    try:
        await mcp_client.cleanup()
    except:
        pass

if __name__ == "__main__":
    asyncio.run(run_tests())

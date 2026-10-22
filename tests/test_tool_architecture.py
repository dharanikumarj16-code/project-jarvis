import asyncio
import json
from app.core import parse_fallback_json, JarvisCore
from app.agent import json_schema_to_pydantic_fields
from app.tools.bus import tool_bus, ToolDefinition
from app.permissions import PermissionLevel

# --- Test 4 & 5: Schema Tests ---
def test_nested_schema():
    schema = {
        "action": {
            "type": "object",
            "properties": {
                "type": {"type": "string"},
                "query": {"type": "string"}
            },
            "required": ["type"]
        }
    }
    fields = json_schema_to_pydantic_fields(schema)
    assert "action" in fields
    ActionModelType = fields["action"][0]
    
    # It should be a pydantic model we can instantiate
    obj = ActionModelType(type="search", query="Python")
    assert obj.type == "search"
    print("Test 4 - Nested schema: PASS")

def test_array_schema():
    schema = {
        "text_list": {
            "type": "array",
            "items": {"type": "string"}
        },
        "number_list": {
            "type": "array",
            "items": {"type": "integer"}
        }
    }
    fields = json_schema_to_pydantic_fields(schema)
    assert fields["text_list"][0] == list[str]
    assert fields["number_list"][0] == list[int]
    print("Test 5 - Array schema: PASS")

# --- Test 6 & 7: Fallback JSON Parser ---
def test_multiline_json():
    text = """```json
{
  "tool": "type_text",
  "arguments": {
    "text": "line one\\nline two\\nline three"
  }
}
```"""
    calls = parse_fallback_json(text)
    assert len(calls) == 1
    assert calls[0]["tool_name"] == "type_text"
    assert calls[0]["arguments"]["text"] == "line one\nline two\nline three"
    print("Test 6 - Multiline JSON: PASS")

def test_invalid_json():
    text = "```json\n{ invalid }```"
    calls = parse_fallback_json(text)
    assert len(calls) == 0  # Should fail gracefully, not crash
    print("Test 7 - Invalid JSON: PASS")

# --- Test 8, 9, 10: Tool Execution ---
async def run_tool_tests():
    # Setup dummy tool
    def my_tool(x: int):
        if x == 0:
            raise ValueError("Zero is not allowed")
        return x * 2

    tool_bus.register_tool(
        ToolDefinition(
            name="my_tool",
            description="Test tool",
            input_schema={"x": {"type": "integer"}},
            permission_level=PermissionLevel.READ,
            category="SYSTEM"
        ),
        my_tool
    )

    # Test 8: Unknown tool
    res = await tool_bus.execute("non_existent", {})
    assert not res["success"]
    assert res["error"]["type"] == "ToolNotFound"
    print("Test 8 - Unknown tool: PASS")

    # Test 9: Invalid arguments (Unexpected argument)
    res = await tool_bus.execute("my_tool", {"unexpected": "arg"})
    assert not res["success"]
    assert res["error"]["type"] == "ToolValidationError"
    print("Test 9 - Invalid arguments: PASS")

    # Test 10: Tool execution failure
    res = await tool_bus.execute("my_tool", {"x": 0})
    assert not res["success"]
    assert res["error"]["type"] == "ToolExecutionError"
    print("Test 10 - Tool execution failure: PASS")

# --- Test 1, 2, 3: Core loop logic (Mocked) ---
async def test_core_logic():
    class DummyResult:
        def __init__(self, data):
            self.data = data
            
        def all_messages(self):
            return ["history_mock"]
            
    class DummyAgent:
        def __init__(self, responses):
            self.responses = responses
            self.call_count = 0
            
        async def run(self, prompt, message_history=None, **kwargs):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return DummyResult(resp)


    # Override get_agent for testing
    import app.core
    
    # Test 1: Simple Tool
    agent1 = DummyAgent([
        '```json\n{"tool": "my_tool", "arguments": {"x": 2}}\n```',
        "Done."
    ])
    app.core.get_agent = lambda: agent1
    core = JarvisCore(None)
    hist, final = await core.process_request("Test", [])
    assert "Done" in final
    print("Test 1 - Simple tool: PASS")

    
    # Test 2: Multi-step
    agent2 = DummyAgent([
        '```json\n{"tool": "my_tool", "arguments": {"x": 2}}\n```',
        '```json\n{"tool": "my_tool", "arguments": {"x": 3}}\n```',
        "Done."
    ])
    app.core.get_agent = lambda: agent2
    core = JarvisCore(None)
    hist, final = await core.process_request("Multi step", [])
    assert "Done" in final
    print("Test 2 - Multi-step task: PASS")


if __name__ == "__main__":
    test_nested_schema()
    test_array_schema()
    test_multiline_json()
    test_invalid_json()
    asyncio.run(run_tool_tests())
    asyncio.run(test_core_logic())

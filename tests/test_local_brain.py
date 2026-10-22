"""
tests/test_local_brain.py - Unit & Integration Tests for FunctionGemmaLocalBrain
=============================================================================

Validates:
1. Successful Ollama connectivity.
2. Model availability detection.
3. Tool-schema conversion and caching.
4. Valid tool-call parsing.
5. Invalid tool names handling.
6. Missing required arguments validation.
7. Incorrect argument types validation & coercion.
8. Ollama connection failure handling.
9. Model timeout handling.
10. Model responses without tool calls.
11. Tool execution failure reporting.
12. Maximum execution limits & anti-loop detection.
13. Existing simple-command fast-path preservation.
14. Complex-agent routing fallback preservation.
15. Real local model smoke test (when Ollama is accessible).
"""

import asyncio
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from app.local_brain import FunctionGemmaLocalBrain
from app.tools.bus import ToolDefinition, tool_bus
from app.permissions import PermissionLevel
from app.core import JarvisCore


@pytest.fixture(autouse=True)
def setup_test_tools():
    """Register sample tools for testing."""
    tool_bus.register_tool(
        ToolDefinition(
            name="test_scanner",
            description="A test scanner tool with required string and optional integer.",
            input_schema={
                "target": {"type": "string", "description": "Target hostname or IP"},
                "timeout": {"type": "integer", "description": "Optional timeout in seconds", "default": 5},
            },
            permission_level=PermissionLevel.READ,
            category="SYSTEM",
        ),
        lambda target, timeout=5: f"Scanned {target} (timeout={timeout})",
    )

    tool_bus.register_tool(
        ToolDefinition(
            name="test_failing_tool",
            description="A tool that always throws an exception.",
            input_schema={"flag": {"type": "boolean"}},
            permission_level=PermissionLevel.READ,
            category="SYSTEM",
        ),
        lambda flag=True: (_ for _ in ()).throw(RuntimeError("Hardware failure simulation")),
    )


# ---------------------------------------------------------------------------
# 1. Successful Ollama Connectivity
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ollama_connectivity_success():
    brain = FunctionGemmaLocalBrain(host="http://mock-ollama:11434", model_name="functiongemma:latest")
    mock_client = AsyncMock()
    mock_client.list.return_value = {
        "models": [{"model": "functiongemma:latest", "name": "functiongemma:latest"}]
    }

    with patch.object(brain, "_client", mock_client):
        health = await brain.check_health()
        assert health["available"] is True
        assert health["model"] == "functiongemma:latest"
        assert health["error"] is None


# ---------------------------------------------------------------------------
# 2. Model Availability Detection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_model_availability_missing():
    brain = FunctionGemmaLocalBrain(host="http://mock-ollama:11434", model_name="nonexistent_model")
    mock_client = AsyncMock()
    mock_client.list.return_value = {
        "models": [{"model": "llama3:latest", "name": "llama3:latest"}]
    }

    with patch.object(brain, "_client", mock_client):
        health = await brain.check_health()
        assert health["available"] is False
        assert "not found" in health["error"]


# ---------------------------------------------------------------------------
# 3. Tool-Schema Conversion & Caching
# ---------------------------------------------------------------------------
def test_tool_schema_conversion():
    brain = FunctionGemmaLocalBrain()
    tool_def = tool_bus.tools["test_scanner"]
    schema = brain.convert_tool_definition_to_schema(tool_def)

    assert schema["type"] == "function"
    fn = schema["function"]
    assert fn["name"] == "test_scanner"
    assert "target" in fn["parameters"]["properties"]
    assert fn["parameters"]["properties"]["target"]["type"] == "string"
    assert "target" in fn["parameters"]["required"]
    assert "timeout" not in fn["parameters"]["required"]

    # Verify schema caching
    brain._refresh_schema_cache()
    assert "test_scanner" in brain._schema_cache
    cached = brain._schema_cache["test_scanner"]
    assert cached == schema


# ---------------------------------------------------------------------------
# 4. Valid Tool-Call Parsing
# ---------------------------------------------------------------------------
def test_valid_tool_call_parsing():
    brain = FunctionGemmaLocalBrain()

    # From mock object
    class MockCall:
        class function:
            name = "test_scanner"
            arguments = {"target": "127.0.0.1"}

    parsed = brain.parse_tool_call(MockCall())
    assert parsed["tool_name"] == "test_scanner"
    assert parsed["arguments"] == {"target": "127.0.0.1"}

    # From dict with JSON string
    dict_call = {
        "function": {
            "name": "test_scanner",
            "arguments": '{"target": "localhost", "timeout": 10}'
        }
    }
    parsed_dict = brain.parse_tool_call(dict_call)
    assert parsed_dict["tool_name"] == "test_scanner"
    assert parsed_dict["arguments"] == {"target": "localhost", "timeout": 10}


# ---------------------------------------------------------------------------
# 5. Invalid Tool Names
# ---------------------------------------------------------------------------
def test_invalid_tool_names():
    brain = FunctionGemmaLocalBrain()
    is_valid, err, _ = brain.validate_tool_call("unknown_hallucinated_tool", {"x": 1})
    assert is_valid is False
    assert "not registered" in err


# ---------------------------------------------------------------------------
# 6. Missing Required Arguments
# ---------------------------------------------------------------------------
def test_missing_required_arguments():
    brain = FunctionGemmaLocalBrain()
    # test_scanner requires 'target'
    is_valid, err, _ = brain.validate_tool_call("test_scanner", {"timeout": 10})
    assert is_valid is False
    assert "Missing required argument 'target'" in err


# ---------------------------------------------------------------------------
# 7. Incorrect Argument Types & Coercion
# ---------------------------------------------------------------------------
def test_argument_type_validation_and_coercion():
    brain = FunctionGemmaLocalBrain()

    # Successful coercion: string number to integer
    is_valid, err, sanitized = brain.validate_tool_call(
        "test_scanner", {"target": "192.168.1.1", "timeout": "15"}
    )
    assert is_valid is True
    assert sanitized["timeout"] == 15

    # Invalid type that cannot be coerced to integer
    is_valid, err, _ = brain.validate_tool_call(
        "test_scanner", {"target": "192.168.1.1", "timeout": "not-a-number"}
    )
    assert is_valid is False
    assert "must be an integer" in err


# ---------------------------------------------------------------------------
# 8. Ollama Connection Failure
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ollama_connection_failure():
    brain = FunctionGemmaLocalBrain(host="http://nonexistent-host:9999")
    mock_client = AsyncMock()
    mock_client.chat.side_effect = ConnectionError("Connection refused")

    with patch.object(brain, "_client", mock_client):
        res = await brain.select_tools("Scan network")
        assert res["has_tool_calls"] is False
        assert len(res["errors"]) > 0
        assert "Connection refused" in res["errors"][0]


# ---------------------------------------------------------------------------
# 9. Model Timeout
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_model_timeout_handling():
    brain = FunctionGemmaLocalBrain(timeout=0.01)
    mock_client = AsyncMock()

    async def slow_chat(*args, **kwargs):
        await asyncio.sleep(0.5)

    mock_client.chat.side_effect = slow_chat

    with patch.object(brain, "_client", mock_client):
        res = await brain.select_tools("Scan network")
        assert res["has_tool_calls"] is False
        assert any("timed out" in e.lower() for e in res["errors"])


# ---------------------------------------------------------------------------
# 10. Model Responses Without Tool Calls
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_model_response_without_tool_calls():
    brain = FunctionGemmaLocalBrain()
    mock_client = AsyncMock()

    class MockResponse:
        class message:
            content = "I cannot fulfill this request."
            tool_calls = None

    mock_client.chat.return_value = MockResponse()

    with patch.object(brain, "_client", mock_client):
        res = await brain.select_tools("Write a poem about Windows")
        assert res["has_tool_calls"] is False
        assert res["tool_calls"] == []
        assert res["text"] == "I cannot fulfill this request."


# ---------------------------------------------------------------------------
# 11. Tool Execution Failure Reporting
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_tool_execution_failure():
    brain = FunctionGemmaLocalBrain()
    mock_client = AsyncMock()

    class MockResponse:
        class message:
            content = ""
            tool_calls = [{
                "function": {
                    "name": "test_failing_tool",
                    "arguments": {"flag": True}
                }
            }]

    mock_client.chat.return_value = MockResponse()

    with patch.object(brain, "_client", mock_client):
        result = await brain.run_tool_loop("Run failing tool", max_turns=1)
        assert len(result["observations"]) == 1
        obs = result["observations"][0]
        assert obs["success"] is False
        assert obs["error"] is not None
        assert "Hardware failure simulation" in obs["error"]["message"]


# ---------------------------------------------------------------------------
# 12. Maximum Execution Limits & Anti-Loop Detection
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_execution_limits_and_anti_loop():
    brain = FunctionGemmaLocalBrain(max_turns=3, max_tool_executions=2)
    mock_client = AsyncMock()

    # Model proposes same tool call repeatedly
    class MockResponse:
        class message:
            content = ""
            tool_calls = [{
                "function": {
                    "name": "test_scanner",
                    "arguments": {"target": "10.0.0.1"}
                }
            }]

    mock_client.chat.return_value = MockResponse()

    with patch.object(brain, "_client", mock_client):
        result = await brain.run_tool_loop("Scan repeatedly", max_turns=3, max_tool_executions=2)
        # First execution succeeds; second is prevented by anti-loop protection
        assert result["executed_count"] == 1
        errors = [o.get("error", {}).get("type") for o in result["observations"] if not o.get("success")]
        assert "CircularCallDetected" in errors


# ---------------------------------------------------------------------------
# 13. Existing Simple-Command Fast-Path Remains Functional
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_simple_command_fast_path_preservation():
    core = JarvisCore(None)
    # "open notepad" is a direct fast-path command
    with patch("app.core.local_brain") as mock_local_brain:
        hist, resp = await core.process_request("open notepad", [])
        # Local brain should NOT be invoked for pure fast path
        mock_local_brain.run_tool_loop.assert_not_called()
        assert "[open_app]" in resp


# ---------------------------------------------------------------------------
# 14. Complex-Agent Routing Fallback Remains Functional
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_complex_agent_routing_fallback():
    core = JarvisCore(None)

    class DummyAgent:
        async def run(self, *args, **kwargs):
            class Res:
                data = "Complex agent executed."
                def all_messages(self):
                    return []
            return Res()

    import app.core
    app.core.get_agent = lambda: DummyAgent()

    # Local brain returns 0 tool executions
    with patch("app.core.local_brain.run_tool_loop", new=AsyncMock(return_value={"executed_count": 0, "observations": []})):
        hist, resp = await core.process_request("Analyze this complex codebase and generate an architectural summary", [])
        assert "Complex agent executed." in resp


# ---------------------------------------------------------------------------
# 15. Integration Smoke Test Against Real WSL Ollama
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_live_ollama_functiongemma_smoke():
    brain = FunctionGemmaLocalBrain()
    health = await brain.check_health()
    if not health.get("available"):
        pytest.skip("Local Ollama or FunctionGemma model not reachable.")

    # Execute a safe query: scan wifi networks or system info
    res = await brain.select_tools("What wifi networks are available right now?")
    assert res is not None
    # FunctionGemma should either return a tool call (get_wifi_networks) or safe response
    if res["has_tool_calls"]:
        call = res["tool_calls"][0]
        assert call["tool_name"] in tool_bus.tools
        assert isinstance(call["arguments"], dict)
    print(f"Live smoke test latency: {res['metrics']['total_latency_ms']}ms")


# ---------------------------------------------------------------------------
# 16. llama-cpp-python Engine Backend Selection & Health Checks
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_llama_cpp_backend_selection_and_health(tmp_path):
    # Test 1: Explicit llama_cpp with missing model file returns available=False
    missing_gguf = str(tmp_path / "nonexistent.gguf")
    brain = FunctionGemmaLocalBrain(backend="llama_cpp", gguf_path=missing_gguf)
    assert brain.get_effective_backend() == "llama_cpp"
    health = await brain.check_health()
    assert health["available"] is False
    assert health["backend"] == "llama_cpp"
    assert "not found" in health["error"]

    # Test 2: GGUF model file exists on disk
    dummy_gguf = tmp_path / "test_model.gguf"
    dummy_gguf.write_bytes(b"GGUF_MOCK_DATA")
    brain_active = FunctionGemmaLocalBrain(backend="llama_cpp", gguf_path=str(dummy_gguf))
    assert brain_active.get_effective_backend() == "llama_cpp"
    health_active = await brain_active.check_health()
    assert health_active["available"] is True
    assert health_active["backend"] == "llama_cpp"
    assert health_active["model"] == "test_model.gguf"
    assert health_active["error"] is None

    # Test 3: Auto mode detects GGUF model file if present
    brain_auto = FunctionGemmaLocalBrain(backend="auto", gguf_path=str(dummy_gguf))
    assert brain_auto.get_effective_backend() == "llama_cpp"


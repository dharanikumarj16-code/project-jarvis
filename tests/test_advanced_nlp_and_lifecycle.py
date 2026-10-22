"""
tests/test_advanced_nlp_and_lifecycle.py
========================================

Verifies:
1. Dynamic tool management: enable/disable/update on UnifiedToolBus.
2. Dynamic tool creation, isolated testing, and hot registration.
3. Centralized permission management (OS protection, terminal commands, dependency installs, custom handlers).
4. Ollama & FunctionGemma lifecycle checks, discovery, and deterministic fallback.
5. Multi-step planning with dependencies, criteria, and execution.
"""

import asyncio
import pytest
from app.permissions import PermissionEngine, PermissionLevel, PermissionDecision
from app.tools.bus import ToolDefinition, tool_bus
from app.tools.canonical_registry import get_canonical_registry, resolve_canonical_tool_name
from app.tools.dynamic_tools import propose_tool, verify_tool_isolated, save_and_register_dynamic_tool
from app.ollama_lifecycle import is_ollama_reachable, list_installed_models, initialize_local_brain_lifecycle
from app.planner import create_execution_plan, execute_plan, ExecutionPlan
from app.router import ExecutionContext


# ---------------------------------------------------------------------------
# 1. Dynamic ToolBus Enable / Disable / Update
# ---------------------------------------------------------------------------
def test_tool_bus_dynamic_enable_disable_update():
    dummy_def = ToolDefinition(
        name="test_dummy_tool",
        description="A dummy test tool",
        input_schema={"type": "object", "properties": {"msg": {"type": "string"}}},
        permission_level=PermissionLevel.LOW_RISK,
        category="test",
    )
    tool_bus.register_tool(dummy_def, executor=lambda msg="": f"Echo: {msg}")

    assert tool_bus.is_tool_enabled("test_dummy_tool") is True
    assert "test_dummy_tool" in tool_bus.get_tools(only_enabled=True)

    # Disable tool
    assert tool_bus.disable_tool("test_dummy_tool") is True
    assert tool_bus.is_tool_enabled("test_dummy_tool") is False
    assert "test_dummy_tool" not in tool_bus.get_tools(only_enabled=True)

    # Re-enable tool
    assert tool_bus.enable_tool("test_dummy_tool") is True
    assert tool_bus.is_tool_enabled("test_dummy_tool") is True

    # Update tool
    updated_def = ToolDefinition(
        name="test_dummy_tool",
        description="Updated dummy test tool",
        input_schema={"type": "object"},
        permission_level=PermissionLevel.READ,
        category="test",
    )
    assert tool_bus.update_tool("test_dummy_tool", tool_def=updated_def) is True
    assert tool_bus.tools["test_dummy_tool"].description == "Updated dummy test tool"


@pytest.mark.asyncio
async def test_disabled_tool_execution_rejection():
    dummy_def = ToolDefinition(
        name="disabled_sample_tool",
        description="Tool that will be disabled",
        input_schema={},
        permission_level=PermissionLevel.LOW_RISK,
        category="test",
    )
    tool_bus.register_tool(dummy_def, executor=lambda: "done")
    tool_bus.disable_tool("disabled_sample_tool")

    obs = await tool_bus.execute("disabled_sample_tool", {})
    assert obs["success"] is False
    assert obs["error"]["type"] == "ToolDisabledError"


# ---------------------------------------------------------------------------
# 2. Dynamic Tool Creation, Isolated Testing & Hot Registration
# ---------------------------------------------------------------------------
def test_dynamic_tool_propose_and_isolated_test():
    code = """
def sample_word_count(text=""):
    return {"count": len(text.split())}
"""
    prop = propose_tool(
        name="sample_word_count",
        description="Count words in text",
        input_schema={"text": {"type": "string"}},
        code=code,
    )
    assert prop["valid"] is True
    assert prop["tool_name"] == "sample_word_count"

    # Test in isolation
    test_res = verify_tool_isolated(
        name="sample_word_count",
        code=code,
        test_args={"text": "hello jarvis how are you"},
    )
    assert test_res["success"] is True
    assert test_res["result"] == {"count": 5}

    # Hot register
    reg = save_and_register_dynamic_tool(
        name="sample_word_count",
        description="Count words in text",
        input_schema={"text": {"type": "string"}},
        code=code,
        auto_save=False,
    )
    assert reg["registered"] is True
    assert "sample_word_count" in tool_bus.tools


# ---------------------------------------------------------------------------
# 3. Centralized Permission Management
# ---------------------------------------------------------------------------
def test_centralized_permissions_system_path_protection():
    engine = PermissionEngine()
    # Attempting to delete a file in C:\Windows
    decision, reason = engine.evaluate_operation(
        "move_to_recycle_bin",
        PermissionLevel.DESTRUCTIVE,
        {"path": r"C:\Windows\System32\cmd.exe"},
    )
    assert decision == PermissionDecision.DENY
    assert "strictly forbidden" in reason


def test_centralized_permissions_destructive_command_blocking():
    engine = PermissionEngine()
    # Attempting to format a drive
    decision, reason = engine.evaluate_operation(
        "terminal_execute",
        PermissionLevel.DESTRUCTIVE,
        {"command": "format d: /q"},
    )
    assert decision == PermissionDecision.DENY
    assert "Destructive command pattern" in reason


def test_centralized_permissions_dependency_approval_required():
    engine = PermissionEngine()
    decision, reason = engine.evaluate_operation(
        "terminal_execute",
        PermissionLevel.ACTION,
        {"command": "pip install requests"},
    )
    assert decision == PermissionDecision.ASK
    assert "requires approval" in reason


def test_centralized_permissions_custom_approval_handler():
    engine = PermissionEngine()
    # Register approval handler that approves requests mentioning 'safe'
    engine.set_approval_handler(lambda tool, reason, args: "safe" in args.get("command", ""))

    assert engine.check_permission("terminal_execute", PermissionLevel.SENSITIVE, {"command": "echo safe operation"}) is True
    assert engine.check_permission("terminal_execute", PermissionLevel.SENSITIVE, {"command": "echo dangerous operation"}) is False


# ---------------------------------------------------------------------------
# 4. Ollama & FunctionGemma Lifecycle
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ollama_lifecycle_bootstrap_and_fallback():
    # If Ollama is running on localhost, verify query works; if not, verify fallback mode is declared
    status = await initialize_local_brain_lifecycle(auto_start=False, auto_pull=False)
    assert "ollama_running" in status
    assert "active_mode" in status
    if status["ollama_running"]:
        assert status["active_mode"] in ("gemma_slm", "deterministic_fallback")
    else:
        assert status["active_mode"] == "deterministic_fallback"


# ---------------------------------------------------------------------------
# 5. Multi-Step Workflow Planning and Execution
# ---------------------------------------------------------------------------
def test_multi_step_planning_dependencies_and_criteria():
    user_req = "open file explorer && creat foler test_proj && list files"
    plan = create_execution_plan(user_req)

    assert plan.total_steps == 3
    assert plan.steps[0].command == "open file explorer"
    assert plan.steps[0].tool_name == "file_explorer_open"
    assert plan.steps[0].dependencies == []

    assert plan.steps[1].command == "creat foler test_proj"
    assert plan.steps[1].tool_name == "create_directory"
    assert plan.steps[1].dependencies == [1]
    assert "filesystem_exists" in plan.steps[1].validation_criteria

    assert plan.steps[2].command == "list files"
    assert plan.steps[2].tool_name == "list_directory"
    assert plan.steps[2].dependencies == [2]


@pytest.mark.asyncio
async def test_multi_step_execution_and_failure_handling():
    plan = ExecutionPlan(
        goal="Test multi-step execution",
        steps=[],
    )
    # Register simple mock tools
    tool_bus.register_tool(
        ToolDefinition(name="step_a_tool", description="", input_schema={}, permission_level=PermissionLevel.LOW_RISK, category="test"),
        executor=lambda: {"done": True},
    )
    tool_bus.register_tool(
        ToolDefinition(name="step_b_tool", description="", input_schema={}, permission_level=PermissionLevel.LOW_RISK, category="test"),
        executor=lambda: {"done": True},
    )

    from app.planner import PlanStep
    plan.steps.append(PlanStep(step_id=1, command="step a", tool_name="step_a_tool", dependencies=[]))
    plan.steps.append(PlanStep(step_id=2, command="step b", tool_name="step_b_tool", dependencies=[1]))

    ctx = ExecutionContext()
    completed_plan = await execute_plan(plan, ctx, step_delay=0.0)

    assert completed_plan.completed is True
    assert completed_plan.success is True
    assert completed_plan.completed_count == 2

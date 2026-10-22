"""
tests/test_architecture_separation.py - Verification of 5-Path Architecture
===========================================================================

Validates the explicit architectural separation required:
1. Fast path: Regex -> BGE/MiniLM intent matching -> native tools.
2. Planning path: SmolLM2-135M -> structured task plan.
3. Tool path: FunctionGemma -> tool call -> UnifiedToolBus.
4. Control path: State tracking -> result verification -> bounded retry or replanning.
5. Fallback: Model unavailable / invalid output -> deterministic fallback / clarification.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock

from app.router import ExecutionContext, plan_user_input, match_direct_command
from app.planner import (
    PlanStep,
    ExecutionPlan,
    plan_task_with_reasoning,
    execute_plan,
    verify_step_result,
    decompose_goal_with_smollm2,
)
from app.tools.bus import tool_bus
from app.local_brain import FunctionGemmaLocalBrain


# ==============================================================================
# 1. FAST PATH: Regex -> BGE/MiniLM intent matching -> native tools
# ==============================================================================

def test_fast_path_regex_to_native_tools():
    """Verify simple computer instructions match directly without any LLM."""
    ctx = ExecutionContext()
    cmd = "open chrome && maximize it && mute volume"
    steps = plan_user_input(cmd, ctx)
    assert len(steps) == 3
    assert all(s.is_direct for s in steps)
    assert steps[0].tool_name == "open_app"
    assert steps[1].tool_name == "maximize_window"
    assert steps[2].tool_name == "mute_audio"


def test_fast_path_semantic_intent_matching():
    """Verify BGE/MiniLM intent matching resolves paraphrased commands."""
    ctx = ExecutionContext()
    step = match_direct_command("launch the web browser", ctx)
    assert step.tool_name == "open_app"


# ==============================================================================
# 2. PLANNING PATH: SmolLM2-135M -> structured task plan
# ==============================================================================

def test_planning_path_smollm2_decomposition():
    """Verify SmolLM2-135M decomposes complex user goals into discrete plan steps."""
    import json
    mock_response = json.dumps({
        "message": {"content": json.dumps(["open notepad", "type quarterly report", "save file"])}
    }).encode("utf-8")
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = mock_response
        mock_url.return_value.__enter__.return_value = mock_resp

        steps = decompose_goal_with_smollm2("write quarterly report in notepad and save")
        assert len(steps) == 3
        assert steps[0] == "open notepad"
        assert steps[1] == "type quarterly report"
        assert steps[2] == "save file"


def test_planning_path_produces_structured_plan():
    """Verify structured plan contains dependencies and validation criteria."""
    with patch("app.planner.decompose_goal_with_smollm2", return_value=["open notepad", "maximize it"]):
        plan = plan_task_with_reasoning("setup notepad")
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 2
        assert plan.steps[0].dependencies == []
        assert plan.steps[1].dependencies == [1]
        assert plan.steps[0].tool_name == "open_app"


# ==============================================================================
# 3. TOOL PATH: FunctionGemma -> tool call -> UnifiedToolBus
# ==============================================================================

@pytest.mark.asyncio
async def test_tool_path_functiongemma_execution():
    """Verify FunctionGemma translates user intent into validated tool bus calls."""
    brain = FunctionGemmaLocalBrain(tool_delay=0.0)

    mock_selection = {
        "has_tool_calls": True,
        "tool_calls": [{"tool_name": "set_volume", "arguments": {"level": 50}}],
        "text": "",
        "errors": None,
        "metrics": {"ollama_latency_ms": 12.0, "total_latency_ms": 12.0},
    }

    with patch.object(brain, "select_tools", return_value=mock_selection), \
         patch.object(tool_bus, "execute", return_value={"success": True, "data": "Volume set to 50"}) as mock_exec:
        res = await brain.run_tool_loop("set volume to 50%", max_turns=1)
        assert res["executed_count"] == 1
        mock_exec.assert_called_once_with("set_volume", {"level": 50})


# ==============================================================================
# 4. CONTROL PATH: State tracking -> Result verification -> Bounded retry
# ==============================================================================

def test_control_path_result_verification_success():
    step = PlanStep(step_id=1, command="open notepad", tool_name="open_app", validation_criteria="success == True")
    obs = {"success": True, "data": "Launched notepad"}
    valid, err = verify_step_result(step, obs)
    assert valid is True
    assert err is None


def test_control_path_result_verification_failure():
    step = PlanStep(step_id=1, command="open non_existent_binary", tool_name="open_app")
    obs = {"success": False, "error": {"message": "Binary not found"}}
    valid, err = verify_step_result(step, obs)
    assert valid is False
    assert "Binary not found" in err


@pytest.mark.asyncio
async def test_control_path_bounded_retry_and_state_tracking():
    """Verify bounded retry when tool execution fails, then succeeds."""
    ctx = ExecutionContext()
    step1 = PlanStep(step_id=1, command="open notepad", tool_name="open_app", tool_args={"app_name": "notepad"})
    plan = ExecutionPlan(goal="launch app", steps=[step1])

    # First attempt fails, second attempt succeeds
    call_count = 0

    async def mock_execute(name, args):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"success": False, "error": "Temporary lock"}
        return {"success": True, "data": "App opened"}

    with patch.object(tool_bus, "execute", side_effect=mock_execute):
        res_plan = await execute_plan(plan, ctx, step_delay=0.0)
        assert res_plan.success is True
        assert call_count == 2
        assert ctx.last_app_name == "notepad"


# ==============================================================================
# 5. FALLBACK PATH: Deterministic fallback / clarification on model failure
# ==============================================================================

def test_fallback_path_when_smollm2_unavailable():
    """When SmolLM2 is offline, planner seamlessly falls back to deterministic router."""
    with patch("urllib.request.urlopen", side_effect=Exception("Ollama offline")):
        plan = plan_task_with_reasoning("open chrome and mute volume")
        assert isinstance(plan, ExecutionPlan)
        assert len(plan.steps) == 2
        assert plan.steps[0].tool_name == "open_app"
        assert plan.steps[1].tool_name == "mute_audio"


def test_fallback_path_clarification_on_ambiguous_intent():
    """Ambiguous intent produces a deterministic clarification prompt."""
    ctx = ExecutionContext()
    steps = plan_user_input("close it", ctx)  # No context set
    assert any(s.routing_result and s.routing_result.needs_clarification for s in steps)

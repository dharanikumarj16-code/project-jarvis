"""
app/planner.py - Multi-Step Workflow Planner and Execution Engine for JARVIS OS
================================================================================

Implements structured multi-step planning with:
- Ordered execution steps
- Step dependency tracking (e.g. Step 2 requires Step 1 to succeed)
- Deterministic post-execution validation criteria
- Completion criteria and bounded failure handling
"""

import asyncio
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.config import config
from app.router import ExecutionContext, Step, match_direct_command, plan_user_input
from app.tools.bus import tool_bus

logger = logging.getLogger("jarvis.planner")


class PlanStep(BaseModel):
    """A single discrete step in a multi-step task plan."""
    step_id: int
    command: str
    tool_name: Optional[str] = None
    tool_args: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[int] = Field(default_factory=list)
    validation_criteria: str = "success == True"
    status: str = "pending"  # pending, running, completed, failed, skipped
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class ExecutionPlan(BaseModel):
    """A structured plan containing ordered steps, dependencies, and completion criteria."""
    goal: str
    steps: List[PlanStep] = Field(default_factory=list)
    completed: bool = False
    success: bool = False
    summary: str = ""
    created_at: float = Field(default_factory=time.time)

    @property
    def total_steps(self) -> int:
        return len(self.steps)

    @property
    def completed_count(self) -> int:
        return sum(1 for s in self.steps if s.status == "completed")


def _infer_validation_criteria(tool_name: Optional[str], args: Dict[str, Any]) -> str:
    """Assign appropriate completion/validation criteria based on tool operation."""
    if not tool_name:
        return "success == True"
    if tool_name in ("create_directory", "create_file"):
        path = args.get("path", "")
        return f"filesystem_exists({path})" if path else "success == True"
    if tool_name == "move_to_recycle_bin":
        path = args.get("path", "")
        return f"not filesystem_exists({path})" if path else "success == True"
    if tool_name in ("move_file", "move_directory"):
        dst = args.get("destination", "")
        return f"filesystem_exists({dst})" if dst else "success == True"
    if tool_name == "open_app":
        app_name = args.get("app_name", "")
        return f"process_running({app_name})" if app_name else "success == True"
    return "success == True"


def create_execution_plan(user_input: str, ctx: Optional[ExecutionContext] = None) -> ExecutionPlan:
    """Parse complex instructions into an ExecutionPlan with ordered steps and dependencies."""
    if ctx is None:
        ctx = ExecutionContext()

    raw_steps: List[Step] = plan_user_input(user_input, ctx)
    plan = ExecutionPlan(goal=user_input)

    for idx, raw in enumerate(raw_steps, start=1):
        # Step depends on immediately preceding step in sequential tasks
        deps = [idx - 1] if idx > 1 else []
        criteria = _infer_validation_criteria(raw.tool_name, raw.tool_args)

        plan_step = PlanStep(
            step_id=idx,
            command=raw.command,
            tool_name=raw.tool_name,
            tool_args=raw.tool_args,
            dependencies=deps,
            validation_criteria=criteria,
            status="pending",
        )
        plan.steps.append(plan_step)

    return plan


async def execute_plan(
    plan: ExecutionPlan,
    ctx: ExecutionContext,
    step_delay: float = 0.5,
) -> ExecutionPlan:
    """Execute plan steps sequentially, respecting dependencies and halting on critical errors."""
    logger.info(f"Executing plan for goal: '{plan.goal}' ({len(plan.steps)} steps)")
    completed_steps: Dict[int, PlanStep] = {}

    for step in plan.steps:
        # Check prerequisites
        unmet_deps = [dep for dep in step.dependencies if dep not in completed_steps or completed_steps[dep].status != "completed"]
        if unmet_deps:
            step.status = "skipped"
            step.error = f"Prerequisite step(s) {unmet_deps} did not complete successfully."
            logger.warning(f"Skipping Step {step.step_id} ('{step.command}'): unmet dependencies {unmet_deps}")
            continue

        if not step.tool_name:
            step.status = "failed"
            step.error = "No registered tool identified for step."
            continue

        step.status = "running"
        t0 = time.perf_counter()
        retries_left = getattr(config, "max_retries", 2)
        step_success = False

        while retries_left >= 0 and not step_success:
            try:
                if step_delay > 0 and step.step_id > 1:
                    await asyncio.sleep(step_delay)

                obs = await tool_bus.execute(step.tool_name, step.tool_args)
                step.duration_ms = (time.perf_counter() - t0) * 1000.0

                is_valid, verify_err = verify_step_result(step, obs)
                if is_valid:
                    step.status = "completed"
                    step.result = obs.get("data")
                    completed_steps[step.step_id] = step
                    step_success = True
                    # State tracking in context
                    if step.tool_name in ("open_app", "file_explorer_open", "list_directory"):
                        ctx.update(step.tool_name, step.tool_args)
                else:
                    retries_left -= 1
                    if retries_left >= 0:
                        logger.warning(f"Step {step.step_id} failed verification ({verify_err}). Retrying ({retries_left} left)...")
                        await asyncio.sleep(0.5)
                    else:
                        step.status = "failed"
                        step.error = verify_err or "Verification failed"
                        logger.error(f"Step {step.step_id} failed after retries: {step.error}")

            except Exception as exc:
                retries_left -= 1
                if retries_left < 0:
                    step.duration_ms = (time.perf_counter() - t0) * 1000.0
                    step.status = "failed"
                    step.error = str(exc)
                    logger.error(f"Step {step.step_id} execution error: {exc}")

    plan.completed = True
    plan.success = all(s.status == "completed" for s in plan.steps)
    plan.summary = f"Completed {plan.completed_count}/{plan.total_steps} steps."
    return plan


def verify_step_result(step: PlanStep, obs: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Control Path: Result verification against deterministic criteria."""
    if not obs.get("success", False):
        err = obs.get("error")
        msg = err.get("message") if isinstance(err, dict) else str(err)
        return False, msg or "Tool execution failed"

    criteria = step.validation_criteria or "success == True"
    if "filesystem_exists" in criteria:
        import os
        path = step.tool_args.get("path") or step.tool_args.get("destination")
        if path and not os.path.exists(path):
            return False, f"Post-condition failed: expected path '{path}' does not exist on disk"

    return True, None


def decompose_goal_with_smollm2(goal: str, host: Optional[str] = None) -> List[str]:
    """Planning Path: Use SmolLM2-135M to decompose complex goals into discrete steps."""
    import urllib.request
    import json

    host = host or getattr(config, "ollama_host", "http://127.0.0.1:11434")
    model = getattr(config, "reasoning_model", "smollm2:135m")
    url = f"{host.rstrip('/')}/api/chat"

    prompt = (
        f"You are a computer task planner. Break down the following request into a simple JSON array of discrete, "
        f"single-action computer instructions (e.g. [\"open notepad\", \"type hello world\"]):\n"
        f"Request: \"{goal}\"\n"
        f"Return ONLY the JSON array of strings."
    )

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json",
    }).encode("utf-8")

    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=4.0) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                content = data.get("message", {}).get("content", "").strip()
                parsed = json.loads(content)
                if isinstance(parsed, list) and all(isinstance(x, str) for x in parsed):
                    return parsed
                if isinstance(parsed, dict) and "steps" in parsed and isinstance(parsed["steps"], list):
                    return [str(x) for x in parsed["steps"]]
    except Exception as exc:
        logger.debug(f"SmolLM2-135M planning fallback: {exc}")

    return []


def plan_task_with_reasoning(goal: str, ctx: Optional[ExecutionContext] = None) -> ExecutionPlan:
    """Planning Path: Decompose via SmolLM2-135M or fallback to deterministic regex router."""
    if ctx is None:
        ctx = ExecutionContext()

    # 1. Try SmolLM2-135M planning decomposition
    sub_steps = decompose_goal_with_smollm2(goal)
    if sub_steps and len(sub_steps) > 1:
        plan = ExecutionPlan(goal=goal)
        for idx, cmd in enumerate(sub_steps, start=1):
            matched = match_direct_command(cmd, ctx)
            deps = [idx - 1] if idx > 1 else []
            criteria = _infer_validation_criteria(matched.tool_name, matched.tool_args)
            step = PlanStep(
                step_id=idx,
                command=cmd,
                tool_name=matched.tool_name,
                tool_args=matched.tool_args,
                dependencies=deps,
                validation_criteria=criteria,
                status="pending",
            )
            plan.steps.append(step)
        return plan

    # 2. Deterministic Fallback: regex parser & direct mapping
    return create_execution_plan(goal, ctx)


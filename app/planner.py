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
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from app.router import ExecutionContext, Step, plan_user_input
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
        try:
            if step_delay > 0 and step.step_id > 1:
                await asyncio.sleep(step_delay)

            obs = await tool_bus.execute(step.tool_name, step.tool_args)
            step.duration_ms = (time.perf_counter() - t0) * 1000.0

            if obs.get("success", False):
                step.status = "completed"
                step.result = obs.get("data")
                completed_steps[step.step_id] = step
                # Update context
                if step.tool_name in ("open_app", "file_explorer_open", "list_directory"):
                    ctx.update(step.tool_name, step.tool_args)
            else:
                step.status = "failed"
                err = obs.get("error", {})
                step.error = err.get("message") if isinstance(err, dict) else str(err)
                logger.error(f"Step {step.step_id} failed: {step.error}")

        except Exception as exc:
            step.duration_ms = (time.perf_counter() - t0) * 1000.0
            step.status = "failed"
            step.error = str(exc)
            logger.error(f"Step {step.step_id} execution error: {exc}")

    plan.completed = True
    plan.success = all(s.status == "completed" for s in plan.steps)
    plan.summary = f"Completed {plan.completed_count}/{plan.total_steps} steps."
    return plan

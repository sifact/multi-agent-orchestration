"""Runs a validated plan sequentially through the existing route table."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, replace
from typing import Literal

from ..agents.common import AgentContext, AgentReply
from ..routing.router import ROUTES
from .config import CoordinatorSettings
from .plan import Plan, PlanStep
from .text import clean_model_text

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StepExecution:
    """Outcome and timing for one planned agent call or dependency skip."""

    step: PlanStep
    status: Literal["completed", "failed", "skipped"]
    reply: AgentReply | None
    seconds: float
    error: str | None = None


def dispatch_plan(
    plan: Plan,
    context: AgentContext,
    settings: CoordinatorSettings | None = None,
) -> list[StepExecution]:
    """Run each step in order and skip descendants of steps that did not complete."""
    settings = settings or CoordinatorSettings()
    completed: dict[str, StepExecution] = {}
    executions: list[StepExecution] = []
    for step in plan.steps:
        dependencies = [completed.get(dependency) for dependency in step.depends_on]
        failed_dependencies = [
            execution for execution in dependencies
            if execution is None or execution.status != "completed"
        ]
        if failed_dependencies:
            names = ", ".join(
                execution.step.id if execution is not None else "unknown"
                for execution in failed_dependencies
            )
            execution = StepExecution(
                step, "skipped", None, 0.0,
                f"Skipped because dependency step(s) did not complete: {names}.",
            )
            executions.append(execution)
            completed[step.id] = execution
            continue

        sub_question = _with_findings(step, dependencies, settings.findings_char_limit)
        started = time.perf_counter()
        try:
            reply = ROUTES[step.agent](sub_question, context)
            reply = replace(reply, answer=clean_model_text(reply.answer))
        except Exception as error:
            logger.exception("Coordinator agent step %s (%s) raised an error.",
                             step.id, step.agent)
            execution = StepExecution(
                step, "failed", None, time.perf_counter() - started, str(error)
            )
        else:
            status: Literal["completed", "failed"] = (
                "failed" if reply.error is not None else "completed"
            )
            execution = StepExecution(step, status, reply, time.perf_counter() - started,
                                      reply.error)
        executions.append(execution)
        completed[step.id] = execution
    return executions


def _with_findings(
    step: PlanStep,
    dependencies: list[StepExecution | None],
    char_limit: int,
) -> str:
    """Append only dependency answers, bounded separately from the step's own question."""
    if not dependencies:
        return step.question
    findings = "\n\n".join(
        f"[{execution.step.agent}] {execution.reply.answer}"
        for execution in dependencies
        if execution is not None and execution.reply is not None
    )
    return f"{step.question}\n\nFindings so far:\n{findings[:char_limit]}"

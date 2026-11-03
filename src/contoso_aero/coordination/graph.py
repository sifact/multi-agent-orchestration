"""LangGraph workflow for planning, sequential dispatch and optional synthesis."""

from __future__ import annotations

import time
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from ..agents.common import AgentContext, AgentReply
from ..routing.graph import PipelineResult
from ..routing.router import REFUSAL
from .config import CoordinatorSettings
from .dispatch import StepExecution, dispatch_plan
from .planner import PlannerResult, plan_question
from .synthesize import SynthesisResult, synthesize


class CoordinatorState(TypedDict):
    """Values that flow through the three sequential coordinator stages."""

    question: str
    context: AgentContext
    settings: CoordinatorSettings
    planning: PlannerResult | None
    plan_seconds: float
    executions: list[StepExecution]
    step_seconds: dict[str, float]
    synthesis: SynthesisResult | None
    synthesis_seconds: float
    answer: str
    refused: bool
    error: str | None


def ask_coordinated(
    question: str,
    context: AgentContext,
    settings: CoordinatorSettings | None = None,
) -> PipelineResult:
    """Answer one question through one plan, sequential agent steps and optional synthesis."""
    settings = settings or CoordinatorSettings()
    started = time.perf_counter()
    final = _build_graph().invoke(CoordinatorState(
        question=question,
        context=context,
        settings=settings,
        planning=None,
        plan_seconds=0.0,
        executions=[],
        step_seconds={},
        synthesis=None,
        synthesis_seconds=0.0,
        answer="",
        refused=False,
        error=None,
    ))
    planning = final["planning"]
    plan = planning.plan if planning is not None else None
    executions = final["executions"]
    called = list(dict.fromkeys(
        execution.step.agent for execution in executions if execution.status != "skipped"
    ))
    agent = _aggregate_reply(
        final["answer"], planning, executions, final["synthesis"]
    )
    if final["refused"]:
        label = "unsupported"
    elif final["error"] is not None:
        label = "error"
    elif len(called) == 1:
        label = called[0]
    else:
        label = "coordinator"
    agent_seconds = sum(final["step_seconds"].values()) + final["synthesis_seconds"]
    return PipelineResult(
        question=question,
        label=label,
        answer=final["answer"],
        refused=final["refused"],
        intent=None,
        agent=agent,
        intent_seconds=final["plan_seconds"],
        agent_seconds=agent_seconds,
        total_seconds=time.perf_counter() - started,
        error=final["error"],
        agents_called=called,
        plan=plan,
        plan_seconds=final["plan_seconds"],
        step_seconds=final["step_seconds"],
        synthesis_seconds=final["synthesis_seconds"],
        coordination_steps=executions,
    )


def _build_graph():
    def plan_node(state: CoordinatorState) -> dict[str, object]:
        started = time.perf_counter()
        planning = plan_question(state["question"], state["context"].model, state["settings"])
        error = planning.error
        return {
            "planning": planning,
            "plan_seconds": time.perf_counter() - started,
            "error": error,
            "refused": planning.plan is not None and planning.plan.status == "unsupported",
        }

    def after_plan(state: CoordinatorState) -> Literal["dispatch", "refuse", "__end__"]:
        planning = state["planning"]
        if planning is None or planning.error is not None or planning.plan is None:
            return END
        return "refuse" if planning.plan.status == "unsupported" else "dispatch"

    def dispatch_node(state: CoordinatorState) -> dict[str, object]:
        plan = state["planning"].plan
        if plan is None:
            return {"error": "Coordinator received no validated plan."}
        executions = dispatch_plan(plan, state["context"], state["settings"])
        return {
            "executions": executions,
            "step_seconds": {execution.step.id: execution.seconds for execution in executions},
        }

    def after_dispatch(state: CoordinatorState) -> Literal["single", "synthesize"]:
        plan = state["planning"].plan
        return "synthesize" if plan is not None and len(plan.steps) > 1 else "single"

    def single_node(state: CoordinatorState) -> dict[str, object]:
        if not state["executions"]:
            return {"error": "Coordinator plan contained no agent step."}
        execution = state["executions"][0]
        if execution.status != "completed" or execution.reply is None:
            return {
                "error": f"Step {execution.step.id} ({execution.step.agent}) failed: "
                f"{execution.error or 'no answer was returned.'}"
            }
        return {"answer": execution.reply.answer}

    def synthesis_node(state: CoordinatorState) -> dict[str, object]:
        planning = state["planning"]
        if planning is None or planning.plan is None:
            return {"error": "Coordinator received no validated plan for synthesis."}
        started = time.perf_counter()
        result = synthesize(
            state["question"], planning.plan, state["executions"], state["context"].model
        )
        failed = [
            f"{execution.step.id} ({execution.step.agent})"
            for execution in state["executions"] if execution.status != "completed"
        ]
        error = result.error
        if failed:
            failed_summary = "Some requested parts were not completed: " + ", ".join(failed) + "."
            error = f"{error} {failed_summary}".strip() if error else failed_summary
        return {
            "synthesis": result,
            "synthesis_seconds": time.perf_counter() - started,
            "answer": result.answer,
            "error": error,
        }

    def refuse_node(_: CoordinatorState) -> dict[str, object]:
        return {"answer": REFUSAL, "refused": True}

    graph = StateGraph(CoordinatorState)
    graph.add_node("plan", plan_node)
    graph.add_node("dispatch", dispatch_node)
    graph.add_node("single", single_node)
    graph.add_node("synthesize", synthesis_node)
    graph.add_node("refuse", refuse_node)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges("plan", after_plan, ["dispatch", "refuse", END])
    graph.add_conditional_edges("dispatch", after_dispatch, ["single", "synthesize"])
    graph.add_edge("single", END)
    graph.add_edge("synthesize", END)
    graph.add_edge("refuse", END)
    return graph.compile()


def _aggregate_reply(
    answer: str,
    planning: PlannerResult | None,
    executions: list[StepExecution],
    synthesis: SynthesisResult | None,
) -> AgentReply:
    """Combine planner, step and synthesis costs while preserving tool evidence in order."""
    replies = [execution.reply for execution in executions if execution.reply is not None]
    return AgentReply(
        agent="coordinator",
        answer=answer,
        input_tokens=(planning.input_tokens if planning else 0)
        + sum(reply.input_tokens for reply in replies)
        + (synthesis.input_tokens if synthesis else 0),
        output_tokens=(planning.output_tokens if planning else 0)
        + sum(reply.output_tokens for reply in replies)
        + (synthesis.output_tokens if synthesis else 0),
        model_seconds=(planning.model_seconds if planning else 0.0)
        + sum(reply.model_seconds for reply in replies)
        + (synthesis.model_seconds if synthesis else 0.0),
        retry_wait_seconds=(planning.retry_wait_seconds if planning else 0.0)
        + sum(reply.retry_wait_seconds for reply in replies)
        + (synthesis.retry_wait_seconds if synthesis else 0.0),
        model_calls=(planning.model_calls if planning else 0)
        + sum(reply.model_calls for reply in replies)
        + (synthesis.model_calls if synthesis else 0),
        tool_calls=sum(reply.tool_calls for reply in replies),
        context=[
            f"[{reply.agent}] {item}" for reply in replies for item in reply.context
        ],
        trace=[trace for reply in replies for trace in reply.trace],
    )

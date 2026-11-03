"""The request pipeline as a LangGraph graph: detect intent, route, then one agent or a refusal.

Each node is timed with a wall clock so the report can show per-stage latency. The graph has
no node that calls a second agent: the router limitation is intentional.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal, TypedDict

from langgraph.graph import END, START, StateGraph

from ..agents.common import AgentContext, AgentReply
from ..llm import ModelError
from .intent import IntentResult, detect_intent
from .router import REFUSAL, route

if TYPE_CHECKING:
    from ..coordination.dispatch import StepExecution
    from ..coordination.plan import Plan


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Outcome of one question: the answer, who produced it, and per-stage cost."""

    question: str
    label: str
    answer: str
    refused: bool
    intent: IntentResult | None
    agent: AgentReply | None
    intent_seconds: float
    agent_seconds: float
    total_seconds: float
    error: str | None = None
    agents_called: list[str] = field(default_factory=list)
    plan: Plan | None = None
    plan_seconds: float = 0.0
    step_seconds: dict[str, float] = field(default_factory=dict)
    synthesis_seconds: float = 0.0
    coordination_steps: list[StepExecution] = field(default_factory=list)


class PipelineState(TypedDict):
    question: str
    intent: IntentResult | None
    reply: AgentReply | None
    answer: str
    error: str | None
    intent_seconds: float
    agent_seconds: float


def ask(question: str, context: AgentContext) -> PipelineResult:
    """Answer one question through intent detection, the router, and at most one agent."""
    started = time.perf_counter()
    final = _build_graph(context).invoke(PipelineState(
        question=question, intent=None, reply=None, answer="", error=None,
        intent_seconds=0.0, agent_seconds=0.0))
    intent, reply = final["intent"], final["reply"]
    return PipelineResult(
        question=question, label=intent.label if intent else "error", answer=final["answer"],
        refused=reply is None and final["error"] is None, intent=intent, agent=reply,
        intent_seconds=final["intent_seconds"], agent_seconds=final["agent_seconds"],
        total_seconds=time.perf_counter() - started, error=final["error"],
        agents_called=[reply.agent] if reply else [])


def _build_graph(context: AgentContext):
    def detect_node(state: PipelineState) -> dict[str, object]:
        started = time.perf_counter()
        try:
            intent = detect_intent(state["question"], context.model)
        except ModelError as error:
            return {"error": str(error), "intent_seconds": time.perf_counter() - started}
        return {"intent": intent, "intent_seconds": time.perf_counter() - started}

    def agent_node(state: PipelineState) -> dict[str, object]:
        handler = route(state["intent"].label)  # type: ignore[union-attr]
        started = time.perf_counter()
        reply = handler(state["question"], context)  # type: ignore[misc]
        return {"reply": reply, "answer": reply.answer, "error": reply.error,
                "agent_seconds": time.perf_counter() - started}

    def refuse_node(state: PipelineState) -> dict[str, object]:
        return {"answer": REFUSAL}

    def after_detect(state: PipelineState) -> Literal["agent", "refuse", "__end__"]:
        if state["error"] is not None:
            return END
        return "agent" if route(state["intent"].label) else "refuse"  # type: ignore[union-attr]

    graph = StateGraph(PipelineState)
    graph.add_node("detect_intent", detect_node)
    graph.add_node("agent", agent_node)
    graph.add_node("refuse", refuse_node)
    graph.add_edge(START, "detect_intent")
    graph.add_conditional_edges("detect_intent", after_detect, ["agent", "refuse", END])
    graph.add_edge("agent", END)
    graph.add_edge("refuse", END)
    return graph.compile()

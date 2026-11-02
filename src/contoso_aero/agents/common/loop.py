"""The tool-calling loop every agent module runs, in plain Python.

Flow: model -> (tools -> model)* -> answer. A step limit sends the model to a final no-tools
answer, so a confused model cannot loop forever. The loop deliberately uses no agent
framework: project 2 wraps `handle()` in a service, and the agents must move without one.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field

from ...llm import ModelError, ToolCall
from .types import AgentContext, AgentReply, Tool, ToolStep

FINAL_NUDGE = "Tool budget used. Answer now using only the results you already have."


@dataclass(slots=True)
class _Cost:
    """Running totals for one agent run, reported per stage by the evaluation."""

    input_tokens: int = 0
    output_tokens: int = 0
    model_seconds: float = 0.0
    retry_wait_seconds: float = 0.0
    model_calls: int = 0
    tool_calls: int = 0
    context: list[str] = field(default_factory=list)
    trace: list[ToolStep] = field(default_factory=list)


def run_agent(agent: str, system_prompt: str, question: str, tools: Sequence[Tool],
              context: AgentContext) -> AgentReply:
    """Run one agent to completion and return its answer with its cost data."""
    by_name = {tool.name: tool for tool in tools}
    specs = [tool.spec() for tool in tools]
    messages: list[dict[str, object]] = [{"role": "system", "content": system_prompt},
                                         {"role": "user", "content": question}]
    cost = _Cost()
    try:
        answer, pending = _call_model(context, messages, specs, cost)
        steps = 0
        while pending and steps < context.max_steps:
            _run_tools(by_name, pending, messages, cost)
            steps += 1
            answer, pending = _call_model(context, messages, specs, cost)
        if pending:
            messages.append({"role": "user", "content": FINAL_NUDGE})
            answer, _ = _call_model(context, messages, (), cost)
    except ModelError as error:
        return _reply(agent, "", cost, str(error))
    return _reply(agent, answer, cost, None)


def _call_model(context: AgentContext, messages: list[dict[str, object]],
                specs: Sequence[dict[str, object]], cost: _Cost) -> tuple[str, list[ToolCall]]:
    """One model call; appends the assistant message and returns its text and tool calls."""
    response = context.model.complete(messages, specs)
    message: dict[str, object] = {"role": "assistant", "content": response.content}
    if response.tool_calls:
        message["tool_calls"] = [
            {"id": call.call_id, "type": "function",
             "function": {"name": call.name, "arguments": json.dumps(call.arguments)}}
            for call in response.tool_calls]
    messages.append(message)
    cost.input_tokens += response.input_tokens
    cost.output_tokens += response.output_tokens
    cost.model_seconds += response.model_seconds
    cost.retry_wait_seconds += response.retry_wait_seconds
    cost.model_calls += 1
    return response.content or "", list(response.tool_calls) if specs else []


def _run_tools(by_name: dict[str, Tool], pending: list[ToolCall],
               messages: list[dict[str, object]], cost: _Cost) -> None:
    """Run every requested tool; an unknown tool becomes an error message for the model."""
    for call in pending:
        tool = by_name.get(call.name)
        output = f"Error: unknown tool '{call.name}'." if tool is None else tool.run(call.arguments)
        messages.append({"role": "tool", "tool_call_id": call.call_id, "content": output})
        cost.context.append(f"{call.name}: {output}")
        cost.trace.append(ToolStep(call.name, call.arguments, output))
    cost.tool_calls += len(pending)


def _reply(agent: str, answer: str, cost: _Cost, error: str | None) -> AgentReply:
    return AgentReply(
        agent=agent, answer=answer, input_tokens=cost.input_tokens,
        output_tokens=cost.output_tokens, model_seconds=cost.model_seconds,
        retry_wait_seconds=cost.retry_wait_seconds, model_calls=cost.model_calls,
        tool_calls=cost.tool_calls, context=cost.context, trace=cost.trace,
        error=error)

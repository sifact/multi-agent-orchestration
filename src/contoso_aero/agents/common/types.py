"""Shared agent contract: the context an agent receives and the reply it returns."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ...llm import ModelClient


@dataclass(frozen=True, slots=True)
class AgentContext:
    """Everything an agent module needs, passed in so a module never reaches for globals.

    Keeping this a plain value is what lets project 2 wrap `handle()` in a service later:
    the service only has to build the same context.
    """

    model: ModelClient
    database_path: Path
    knowledge_dir: Path
    max_steps: int = 6


@dataclass(frozen=True, slots=True)
class ToolStep:
    """One tool call as the model made it, kept so a person can audit what an agent ran."""

    tool: str
    arguments: dict[str, object]
    output: str


@dataclass(frozen=True, slots=True)
class AgentReply:
    """An agent's answer plus the cost data the evaluation reports per stage."""

    agent: str
    answer: str
    input_tokens: int = 0
    output_tokens: int = 0
    model_seconds: float = 0.0
    retry_wait_seconds: float = 0.0
    model_calls: int = 0
    tool_calls: int = 0
    context: list[str] = field(default_factory=list)
    trace: list[ToolStep] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True, slots=True)
class Tool:
    """A function the model may call; `run` returns text so every tool result is loggable."""

    name: str
    description: str
    parameters: dict[str, object]
    run: Callable[[dict[str, object]], str]

    def spec(self) -> dict[str, object]:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description,
                             "parameters": self.parameters}}

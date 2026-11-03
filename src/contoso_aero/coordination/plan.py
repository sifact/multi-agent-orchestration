"""Typed plan data and strict validation for coordinator output."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from ..routing.router import ROUTES
from .config import CoordinatorSettings
from .text import clean_model_text


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One self-contained question assigned to a single existing agent."""

    id: str
    agent: str
    question: str
    depends_on: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Plan:
    """A supported ordered plan or an explicit unsupported decision."""

    status: Literal["plan", "unsupported"]
    steps: tuple[PlanStep, ...]


def parse_plan(raw: str, settings: CoordinatorSettings | None = None) -> Plan:
    """Parse and validate JSON from the planner before any agent can be called."""
    settings = settings or CoordinatorSettings()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError("Planner response must be one JSON object.") from error
    if not isinstance(payload, dict) or set(payload) != {"status", "steps"}:
        raise ValueError("Planner response must contain only status and steps.")
    status, raw_steps = payload["status"], payload["steps"]
    if status == "unsupported":
        if raw_steps != []:
            raise ValueError("Unsupported plans must contain no steps.")
        return Plan(status="unsupported", steps=())
    if status != "plan" or not isinstance(raw_steps, list):
        raise ValueError("Planner status must be plan or unsupported.")
    if not 1 <= len(raw_steps) <= settings.max_steps:
        raise ValueError(f"Plans must contain between 1 and {settings.max_steps} steps.")

    known_agents = set(ROUTES)
    steps: list[PlanStep] = []
    seen_ids: set[str] = set()
    for raw_step in raw_steps:
        if not isinstance(raw_step, dict) or set(raw_step) != {
            "id", "agent", "question", "depends_on"
        }:
            raise ValueError("Each step must contain only id, agent, question and depends_on.")
        step_id, agent, question, dependencies = (
            raw_step["id"], raw_step["agent"], raw_step["question"], raw_step["depends_on"]
        )
        if not isinstance(step_id, str) or not step_id.strip() or step_id in seen_ids:
            raise ValueError("Step ids must be non-empty and unique.")
        if not isinstance(agent, str) or agent not in known_agents:
            raise ValueError("Each step must name a known agent.")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("Each step needs a self-contained question.")
        if not isinstance(dependencies, list) or not all(
            isinstance(dependency, str) for dependency in dependencies
        ):
            raise ValueError("depends_on must be a list of earlier step ids.")
        if len(set(dependencies)) != len(dependencies):
            raise ValueError("A step cannot depend on the same step twice.")
        if any(dependency not in seen_ids for dependency in dependencies):
            raise ValueError("Each dependency must name an earlier step.")
        steps.append(PlanStep(step_id, agent, clean_model_text(question).strip(),
                             tuple(dependencies)))
        seen_ids.add(step_id)
    return Plan(status="plan", steps=tuple(steps))

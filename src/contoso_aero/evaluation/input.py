"""Build sanitized JSONL rows and project-owned run records for evaluation."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from ..routing import PipelineResult
from .questions import Question

MAX_CONTEXT_CHARS = 12_000


@dataclass(frozen=True, slots=True)
class EvaluationRow:
    """One harness row containing application output, expected values, and telemetry."""

    id: str
    category: str
    question: str
    response: str
    chosen_agent: str
    predicted_agent: str
    predicted_agents: list[str]
    refused: bool
    context: str
    expected_agents: list[str]
    expected_facts: list[str]
    expected_numbers: list[dict[str, float]]
    expected_behavior: str
    agent_telemetry: dict[str, object]
    judge_applicability: dict[str, str]
    judge_telemetry: dict[str, object]
    seed: int
    temperature: float


def build_row(question: Question, result: PipelineResult, seed: int) -> EvaluationRow:
    """Convert one pipeline result into the stable evaluator input contract."""
    agent = result.agent
    context = "\n".join(agent.context if agent else "")[:MAX_CONTEXT_CHARS]
    return EvaluationRow(
        id=question.id,
        category=question.category,
        question=question.question,
        response=result.answer,
        chosen_agent=result.label,
        predicted_agent=result.label,
        predicted_agents=list(result.agents_called),
        refused=result.refused,
        context=context,
        expected_agents=question.expected_agents,
        expected_facts=question.expected_facts,
        expected_numbers=question.expected_numbers,
        expected_behavior=question.expected_behavior,
        agent_telemetry={
            "intent_seconds": result.intent_seconds,
            "agent_seconds": result.agent_seconds,
            "total_seconds": result.total_seconds,
            "retry_wait_seconds": _retry_wait(result),
            "intent_tokens": result.intent.input_tokens if result.intent else 0,
            "intent_output_tokens": result.intent.output_tokens if result.intent else 0,
            "agent_input_tokens": agent.input_tokens if agent else 0,
            "agent_output_tokens": agent.output_tokens if agent else 0,
            "tool_calls": agent.tool_calls if agent else 0,
            "model_calls": (1 if result.intent else 0) + (agent.model_calls if agent else 0),
            "error": result.error or (agent.error if agent else None),
        },
        judge_applicability={
            "groundedness": "not_applicable" if result.refused else "applicable",
            "relevance": "applicable",
            "intent_resolution": "applicable",
        },
        judge_telemetry={
            "latency_seconds": None,
            "input_tokens": None,
            "output_tokens": None,
            "retry_wait_seconds": None,
            "retries": None,
            "status": "sdk_unavailable",
        },
        seed=seed,
        temperature=0.0,
    )


def write_rows(rows: list[EvaluationRow], path: Path) -> None:
    """Write evaluator input rows without credentials or raw SDK internals."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(asdict(row), ensure_ascii=False) + "\n")


def project_record(
    rows: list[EvaluationRow],
    sdk_result: dict[str, Any],
    versions: dict[str, str],
    cases: list[dict[str, object]] | None = None,
    run_id: str = "",
    created_at: str = "",
    question_file: str = "",
) -> dict[str, object]:
    """Allowlist the stable project envelope around the SDK result."""
    judge_rows = sdk_result.get("rows", [])
    return {
        "run_id": run_id,
        "created_at": created_at,
        "question_file": question_file,
        "versions": versions,
        "cases": cases if cases is not None else [asdict(row) for row in rows],
        "metrics": sdk_result.get("metrics", {}),
        "judge_metrics": _applicable_judge_metrics(judge_rows),
        "judge_rows": judge_rows,
        "studio_url": sdk_result.get("studio_url"),
        "judge_telemetry": {
            "status": "unavailable",
            "reason": "Azure AI Evaluation does not expose supported per-judge token, retry, or latency interception.",
        },
    }


def _applicable_judge_metrics(rows: object) -> dict[str, float]:
    """Aggregate numeric judge outputs after excluding refusal rows from groundedness."""
    values: dict[str, list[float]] = {}
    if not isinstance(rows, list):
        return {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        expected = row.get("inputs.expected_behavior")
        for key, value in row.items():
            if not isinstance(key, str) or not key.startswith("outputs."):
                continue
            evaluator = key.split(".", 2)[1]
            if evaluator == "groundedness" and expected == "refuse":
                continue
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                values.setdefault(key.removeprefix("outputs."), []).append(float(value))
    return {key: mean(items) for key, items in values.items()}


def _retry_wait(result: PipelineResult) -> float:
    return (
        (result.intent.retry_wait_seconds if result.intent else 0.0)
        + (result.agent.retry_wait_seconds if result.agent else 0.0)
    )

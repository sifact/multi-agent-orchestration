"""Azure AI Evaluation SDK execution boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from azure.ai.evaluation import evaluate

from .target import build_exact_evaluators, evaluator_config


def run_sdk_evaluation(
    data_path: Path,
    output_path: Path,
    judges: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run exact evaluators and optional SDK judges against an existing JSONL target."""
    evaluators: dict[str, Any] = build_exact_evaluators()
    config = evaluator_config()
    if judges:
        evaluators.update(judges)
    result = evaluate(
        data=str(data_path),
        evaluators=evaluators,
        evaluator_config=config,
        output_path=str(output_path),
        fail_on_evaluator_errors=False,
    )
    if not isinstance(result, dict):
        raise TypeError("Azure AI Evaluation returned an unsupported result.")
    return result


def run_sdk_target_evaluation(
    data_path: Path,
    output_path: Path,
    target: Any,
    judges: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run the same evaluator set against a callable target and JSONL input rows."""
    evaluators: dict[str, Any] = build_exact_evaluators()
    if judges:
        evaluators.update(judges)
    result = evaluate(
        data=str(data_path),
        target=target,
        evaluators=evaluators,
        evaluator_config=evaluator_config(target_outputs=True),
        output_path=str(output_path),
        fail_on_evaluator_errors=False,
    )
    if not isinstance(result, dict):
        raise TypeError("Azure AI Evaluation returned an unsupported result.")
    return result

"""Targets and evaluator configuration for the Azure AI Evaluation SDK."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import nullcontext
from importlib.metadata import version
from threading import Lock
from typing import Any

from azure.ai.evaluation import (
    GroundednessEvaluator,
    IntentResolutionEvaluator,
    OpenAIModelConfiguration,
    RelevanceEvaluator,
)

from ..config import ModelSettings
from .evaluators import (
    correct_refusal,
    expected_facts_found,
    expected_numbers_within_tolerance,
    routing_accuracy,
)

Evaluator = Callable[..., dict[str, object]]


def build_model_configuration(settings: ModelSettings) -> OpenAIModelConfiguration:
    """Create the SDK's public OpenAI-compatible configuration without persisting its key."""
    settings.require_complete()
    return OpenAIModelConfiguration(
        type="openai",
        base_url=settings.base_url,
        api_key=settings.api_key,
        model=settings.model_name,
    )


def sdk_versions() -> dict[str, str]:
    """Return non-secret package versions recorded in a project run envelope."""
    return {
        "azure-ai-evaluation": version("azure-ai-evaluation"),
        "langgraph": version("langgraph"),
    }


def build_exact_evaluators() -> dict[str, Evaluator]:
    """Return the deterministic evaluators used as primary project metrics."""
    return {
        "routing_accuracy": routing_accuracy,
        "expected_facts_found": expected_facts_found,
        "expected_numbers": expected_numbers_within_tolerance,
        "correct_refusal": correct_refusal,
    }


class SerializedEvaluator:
    """A judge that waits for the shared model lock before each call.

    The SDK runs judge rows concurrently and offers no concurrency argument, so this is the
    only place the project can stop judges from flooding a rate-limited endpoint.
    """

    def __init__(self, judge: Callable[..., dict[str, object]], lock: Lock) -> None:
        self._judge = judge
        self._lock = lock

    def __call__(self, **kwargs: object) -> dict[str, object]:
        with self._lock:
            return self._judge(**kwargs)


def build_judge_evaluators(model_config: OpenAIModelConfiguration,
                           lock: Lock | None = None) -> dict[str, Any]:
    """Construct the three requested SDK judges, serialized behind `lock` when one is given."""
    judges: dict[str, Any] = {
        "groundedness": GroundednessEvaluator(model_config),
        "relevance": RelevanceEvaluator(model_config),
        "intent_resolution": IntentResolutionEvaluator(model_config),
    }
    if lock is None:
        return judges
    return {name: SerializedEvaluator(judge, lock) for name, judge in judges.items()}


def evaluator_config(target_outputs: bool = False) -> dict[str, dict[str, dict[str, str]]]:
    """Map SDK evaluator parameters to the JSONL data columns."""
    output = "${target." if target_outputs else "${data."
    close = "}"
    exact = {
        "predicted_agent": f"{output}predicted_agent{close}",
        "expected_agents": "${data.expected_agents}",
        "response": f"{output}response{close}",
        "expected_facts": "${data.expected_facts}",
        "expected_numbers": "${data.expected_numbers}",
        "refused": f"{output}refused{close}",
        "expected_behavior": "${data.expected_behavior}",
    }
    return {
        "routing_accuracy": {"column_mapping": {k: v for k, v in exact.items()
                                                 if k in {"predicted_agent", "expected_agents"}}},
        "expected_facts_found": {"column_mapping": {k: v for k, v in exact.items()
                                                     if k in {"response", "expected_facts"}}},
        "expected_numbers": {"column_mapping": {k: v for k, v in exact.items()
                                                  if k in {"response", "expected_numbers"}}},
        "correct_refusal": {"column_mapping": {k: v for k, v in exact.items()
                                                if k in {"refused", "expected_behavior"}}},
        "groundedness": {"column_mapping": {
            "query": "${data.question}", "response": f"{output}response{close}",
            "context": f"{output}context{close}"}},
        "relevance": {"column_mapping": {
            "query": "${data.question}", "response": f"{output}response{close}"}},
        "intent_resolution": {"column_mapping": {
            "query": "${data.question}", "response": f"{output}response{close}"}},
    }


def build_pipeline_target(
    context: Any,
    on_result: Callable[[Any], None] | None = None,
    lock: Lock | None = None,
) -> Callable[[str], dict[str, object]]:
    """Adapt the application pipeline to the SDK target callback contract."""
    from ..routing import ask

    def target(question: str) -> dict[str, object]:
        with lock if lock is not None else nullcontext():
            result = ask(question, context)
        if on_result is not None:
            on_result(result)
        return {
            "response": result.answer,
            "predicted_agent": result.label,
            "refused": result.refused,
            "context": "\n".join(result.agent.context if result.agent else ""),
        }

    return target

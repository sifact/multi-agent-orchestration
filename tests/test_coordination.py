"""Offline tests for plan parsing, planner retries and the coordination dev set."""

from __future__ import annotations

import json
from collections.abc import Sequence

import pytest

from contoso_aero.config import DataSettings
from contoso_aero.coordination import CoordinatorSettings, Plan, parse_plan, plan_question
from contoso_aero.evaluation.plan_probe import load_probe
from contoso_aero.llm import ModelResponse
from contoso_aero.routing.intent import LABELS


class PlanModel:
    """Replays planner JSON and captures each model request for offline checks."""

    def __init__(self, *responses: str) -> None:
        self.responses = list(responses)
        self.calls: list[list[dict[str, object]]] = []

    def complete(
        self,
        messages: list[dict[str, object]],
        tools: Sequence[dict[str, object]] = (),
    ) -> ModelResponse:
        self.calls.append(list(messages))
        return ModelResponse(content=self.responses.pop(0), tool_calls=[], input_tokens=7,
                             output_tokens=3, model_seconds=0.25, retry_wait_seconds=0.5)


def _step(step_id: str, agent: str, question: str, depends_on: list[str]) -> dict[str, object]:
    return {"id": step_id, "agent": agent, "question": question, "depends_on": depends_on}


def test_given_valid_chain_when_plan_parsed_then_dependencies_use_earlier_steps() -> None:
    raw = json.dumps({"status": "plan", "steps": [
        _step("first", "service", "Find the service event.", []),
        _step("second", "knowledge", "Find the relevant procedure.", ["first"]),
    ]})

    plan = parse_plan(raw)

    assert plan.steps[1].depends_on == ("first",)


def test_given_unsupported_output_when_plan_parsed_then_no_steps_are_returned() -> None:
    plan = parse_plan('{"status":"unsupported","steps":[]}')

    assert plan == Plan(status="unsupported", steps=())


@pytest.mark.parametrize("dependency", ["later", "missing"])
def test_given_forward_or_unknown_dependency_when_plan_parsed_then_it_is_rejected(
    dependency: str,
) -> None:
    raw = json.dumps({"status": "plan", "steps": [
        _step("first", "service", "Find the event.", [dependency]),
        _step("later", "knowledge", "Find the procedure.", []),
    ]})

    with pytest.raises(ValueError, match="earlier"):
        parse_plan(raw)


def test_given_too_many_steps_when_plan_parsed_then_configured_limit_is_enforced() -> None:
    raw = json.dumps({"status": "plan", "steps": [
        _step(f"s{index}", "service", "Find a service record.", []) for index in range(3)
    ]})

    with pytest.raises(ValueError, match="between 1 and 2"):
        parse_plan(raw, CoordinatorSettings(max_steps=2))


def test_given_invalid_planner_json_when_retried_then_second_plan_is_returned() -> None:
    model = PlanModel("not json", '{"status":"unsupported","steps":[]}')

    result = plan_question("What is outside scope?", model)  # type: ignore[arg-type]

    assert result.plan == Plan(status="unsupported", steps=())
    assert result.model_calls == 2 and len(model.calls) == 2
    assert result.input_tokens == 14 and result.retry_wait_seconds == 1.0


def test_given_invalid_plan_after_retry_when_planned_then_error_is_reported() -> None:
    model = PlanModel("{}", "{}")

    result = plan_question("Combine two data domains.", model)  # type: ignore[arg-type]

    assert result.plan is None and result.model_calls == 2
    assert result.error and "status and steps" in result.error


def test_given_shipped_coordinator_probe_when_loaded_then_rows_cover_pairs_chains_and_refusals() -> None:
    items = load_probe(DataSettings().coordination_probe_path)
    pair_rows = [item for item in items if len(item.expected_agents) == 2]
    triple_rows = [item for item in items if len(item.expected_agents) == 3]
    single_rows = [item for item in items if len(item.expected_agents) == 1]
    unsupported_rows = [item for item in items if not item.expected_agents]
    expected_pairs = {
        frozenset(pair)
        for pair in (
            ("telemetry", "service"), ("telemetry", "production"), ("telemetry", "quality"),
            ("telemetry", "knowledge"), ("service", "production"), ("service", "quality"),
            ("service", "knowledge"), ("production", "quality"), ("production", "knowledge"),
            ("quality", "knowledge"),
        )
    }

    assert len(items) >= 18
    assert {frozenset(item.expected_agents) for item in pair_rows} == expected_pairs
    assert len(triple_rows) >= 3 and len(single_rows) == 3 and len(unsupported_rows) == 3


def test_given_shipped_dev_set_when_compared_to_frozen_test_set_then_questions_do_not_overlap() -> None:
    settings = DataSettings()
    probe_questions = {item.question for item in load_probe(settings.coordination_probe_path)}
    frozen_questions = {
        json.loads(line)["question"] for line in settings.eval_path.read_text().splitlines()
    }

    assert not probe_questions & frozen_questions


def test_given_shared_label_descriptions_when_prompt_checked_then_every_intent_label_is_present() -> None:
    from contoso_aero.coordination.planner import build_planner_prompt

    prompt = build_planner_prompt()

    assert all(f"- {label}:" in prompt for label in LABELS)

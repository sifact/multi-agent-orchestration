"""Offline tests for plan parsing, planner retries and the coordination dev set."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from contoso_aero.agents.common import AgentContext, AgentReply, ToolStep
from contoso_aero.config import DataSettings
from contoso_aero.coordination import (
    CoordinatorSettings,
    Plan,
    ask_coordinated,
    parse_plan,
    plan_question,
)
from contoso_aero.coordination import dispatch as dispatch_module
from contoso_aero.evaluation.plan_probe import load_probe
from contoso_aero.llm import ModelResponse
from contoso_aero.routing import REFUSAL, ask
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


def test_given_planner_prompt_when_category_boundaries_checked_then_sets_are_minimal() -> None:
    from contoso_aero.coordination.planner import build_planner_prompt

    prompt = " ".join(build_planner_prompt().split())

    assert "Select the smallest set of agents" in prompt
    assert "Factory inspection results belong to quality, not service" in prompt
    assert "Include knowledge only when the question asks what document guidance says" in prompt


def _context(model: PlanModel) -> AgentContext:
    return AgentContext(model=model, database_path=Path("unused.sqlite3"),
                        knowledge_dir=Path("unused-knowledge"))


def _plan_json(*steps: dict[str, object]) -> str:
    return json.dumps({"status": "plan", "steps": list(steps)})


def test_given_single_step_plan_when_coordinated_then_agent_answer_is_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = PlanModel(_plan_json(_step("one", "telemetry", "Read the fleet status.", [])))
    reply = AgentReply(agent="telemetry", answer="Engine is active.")
    monkeypatch.setitem(dispatch_module.ROUTES, "telemetry",
                        lambda question, context: reply)

    result = ask_coordinated("What is its status?", _context(model))  # type: ignore[arg-type]

    assert result.answer == reply.answer and result.synthesis_seconds == 0.0
    assert result.agents_called == ["telemetry"] and len(model.calls) == 1


def test_given_dependent_step_when_dispatched_then_earlier_answer_is_appended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = PlanModel(_plan_json(
        _step("first", "telemetry", "Read the recent trend.", []),
        _step("second", "knowledge", "Find its procedure limit.", ["first"]),
    ), "Combined answer.")
    questions: list[str] = []

    def telemetry_handler(question: str, context: AgentContext) -> AgentReply:
        return AgentReply(agent="telemetry", answer="Recent trend is rising.")

    def knowledge_handler(question: str, context: AgentContext) -> AgentReply:
        questions.append(question)
        return AgentReply(agent="knowledge", answer="Procedure limit is 18.")

    monkeypatch.setitem(dispatch_module.ROUTES, "telemetry", telemetry_handler)
    monkeypatch.setitem(dispatch_module.ROUTES, "knowledge", knowledge_handler)

    result = ask_coordinated("Compare trend and limit.", _context(model))  # type: ignore[arg-type]

    assert "Findings so far:\n[telemetry] Recent trend is rising." in questions[0]
    assert result.answer == "Combined answer."


def test_given_failed_step_when_coordinated_then_dependents_skip_and_other_steps_synthesize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = PlanModel(_plan_json(
        _step("first", "telemetry", "Read the trend.", []),
        _step("dependent", "knowledge", "Find the applicable limit.", ["first"]),
        _step("independent", "production", "Read the build record.", []),
    ), "The build is known [production]. The trend and limit could not be determined.")
    called: list[str] = []

    def failed_handler(question: str, context: AgentContext) -> AgentReply:
        called.append("telemetry")
        return AgentReply(agent="telemetry", answer="", error="telemetry unavailable")

    def successful_handler(agent: str):
        def handle(question: str, context: AgentContext) -> AgentReply:
            called.append(agent)
            return AgentReply(agent=agent, answer="Build plant is P1.")
        return handle

    monkeypatch.setitem(dispatch_module.ROUTES, "telemetry", failed_handler)
    monkeypatch.setitem(dispatch_module.ROUTES, "knowledge", successful_handler("knowledge"))
    monkeypatch.setitem(dispatch_module.ROUTES, "production", successful_handler("production"))

    result = ask_coordinated("Compare trend, limit and build.", _context(model))  # type: ignore[arg-type]

    assert called == ["telemetry", "production"]
    assert [step.status for step in result.coordination_steps] == ["failed", "skipped", "completed"]
    assert result.answer.startswith("The build is known")
    assert "not completed" in (result.error or "")
    synthesis_input = str(model.calls[-1][-1]["content"])
    assert "telemetry unavailable" in synthesis_input
    assert "Build plant is P1." in synthesis_input


def test_given_invalid_plan_after_retry_when_coordinated_then_error_is_not_routed_to_v1() -> None:
    model = PlanModel("{}", "{}")

    result = ask_coordinated("Coordinate two domains.", _context(model))  # type: ignore[arg-type]

    assert result.error and "status and steps" in result.error
    assert result.agents_called == [] and result.plan is None
    assert len(model.calls) == 2


def test_given_unsupported_plan_when_coordinated_then_no_agent_is_called() -> None:
    model = PlanModel('{"status":"unsupported","steps":[]}')

    result = ask_coordinated("Tell me about weather.", _context(model))  # type: ignore[arg-type]

    assert result.refused and result.answer == REFUSAL
    assert result.agents_called == [] and result.plan is not None
    assert result.plan.status == "unsupported"


def test_given_multistep_plan_when_coordinated_then_cost_and_stage_times_are_aggregated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = PlanModel(_plan_json(
        _step("first", "telemetry", "Read status.", []),
        _step("second", "service", "Read service record.", []),
    ), "Combined [telemetry] and [service] results.")
    first = AgentReply(
        agent="telemetry", answer="Active.", input_tokens=2, output_tokens=3,
        model_seconds=0.2, retry_wait_seconds=0.1, model_calls=2, tool_calls=1,
        context=["query_sql: telemetry row"], trace=[ToolStep("query_sql", {"sql": "SELECT 1"}, "row")],
    )
    second = AgentReply(
        agent="service", answer="Removed.", input_tokens=5, output_tokens=6,
        model_seconds=0.4, retry_wait_seconds=0.2, model_calls=3, tool_calls=2,
        context=["query_sql: service row"],
    )
    monkeypatch.setitem(dispatch_module.ROUTES, "telemetry", lambda question, context: first)
    monkeypatch.setitem(dispatch_module.ROUTES, "service", lambda question, context: second)

    result = ask_coordinated("Combine fleet and service.", _context(model))  # type: ignore[arg-type]

    assert result.agent is not None
    assert (result.agent.input_tokens, result.agent.output_tokens) == (21, 15)
    assert (result.agent.model_calls, result.agent.tool_calls) == (7, 3)
    assert result.agent.retry_wait_seconds == pytest.approx(1.3)
    assert result.agent.context == ["[telemetry] query_sql: telemetry row",
                                    "[service] query_sql: service row"]
    assert len(result.agent.trace) == 1
    assert set(result.step_seconds) == {"first", "second"}
    assert result.plan_seconds >= 0 and result.synthesis_seconds >= 0


def test_given_v1_and_coordinator_unsupported_when_called_then_refusal_behavior_matches() -> None:
    v1 = ask("Weather?", _context(PlanModel("unsupported")))  # type: ignore[arg-type]
    v2_model = PlanModel('{"status":"unsupported","steps":[]}')

    v2 = ask_coordinated("Weather?", _context(v2_model))  # type: ignore[arg-type]

    assert (v1.refused, v1.answer, v1.agents_called) == (
        v2.refused, v2.answer, v2.agents_called
    )

"""Tests for evaluation scoring and report rendering without a model endpoint."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import pytest

from contoso_aero.agents.common import AgentReply
from contoso_aero.evaluation.evaluators import (
    _contains_number,
    correct_refusal,
    expected_facts_found,
    expected_numbers_within_tolerance,
    routing_accuracy,
)
from contoso_aero.evaluation.input import _applicable_judge_metrics
from contoso_aero.evaluation.questions import Question
from contoso_aero.evaluation.report import render_report
from contoso_aero.evaluation.runner import (
    _pair_results,
    _score,
    load_questions,
    sample_questions,
)
from contoso_aero.evaluation.stats import wilson_interval
from contoso_aero.evaluation.target import (
    SerializedEvaluator,
    build_model_configuration,
    sdk_versions,
)
from contoso_aero.routing.graph import PipelineResult
from contoso_aero.routing.intent import IntentResult


def _result(
    question: str,
    label: str,
    answer: str,
    refused: bool = False,
) -> PipelineResult:
    return PipelineResult(
        question=question,
        label=label,
        answer=answer,
        refused=refused,
        intent=IntentResult(label=label, raw=label, input_tokens=3, output_tokens=1),
        agent=None if refused else AgentReply(agent=label, answer=answer, input_tokens=7, output_tokens=2),
        intent_seconds=0.1,
        agent_seconds=0.2,
        total_seconds=0.3,
    )


def test_given_expected_fact_and_number_when_scored_then_both_must_be_present() -> None:
    question = Question(
        "Q001",
        "single",
        "What is the value?",
        ["telemetry"],
        ["CX7-10001"],
        [{"value": 1406.23, "tolerance": 0.05}],
    )

    correct = _score(question, _result(question.question, "telemetry", "CX7-10001 is 1406.25."))
    incorrect = _score(question, _result(question.question, "telemetry", "CX7-10001 is 1407.0."))

    assert correct.answer_correct and correct.routing_correct
    assert not incorrect.answer_correct
    assert incorrect.missing_numbers == [{"value": 1406.23, "tolerance": 0.05}]


def test_given_formatted_numbers_when_matched_then_common_model_formats_are_supported() -> None:
    assert _contains_number("change was −3.5", -3.5, 0.01)
    assert _contains_number("value was 1.4065e3", 1406.5, 0.01)
    assert _contains_number("ratio was .5", 0.5, 0.01)


def test_given_unicode_hyphens_and_spaces_when_facts_matched_then_ascii_facts_are_found() -> None:
    answer = "Engines CX7‑10052 and CX7‐10053 carry lot FBL–2501–117, removed."

    result = expected_facts_found(answer, ["CX7-10052", "CX7-10053", "FBL-2501-117", "117, removed"])

    assert result["passed"], result["missing_facts"]


def test_given_unicode_minus_hyphen_when_number_matched_then_negative_value_is_read() -> None:
    assert _contains_number("P30 fell by ‑1.9 psia", -1.9, 0.01)


def test_given_refusal_question_when_scored_then_refusal_is_answer_correct() -> None:
    question = Question("Q002", "unsupported", "Off topic", [], expected_behavior="refuse")

    result = _score(question, _result(question.question, "unsupported", "I cannot help.", refused=True))

    assert result.answer_correct and result.refusal_correct and result.routing_correct


def test_given_run_when_report_rendered_then_metrics_and_failures_are_present() -> None:
    run = {
        "run_id": "test",
        "created_at": "now",
        "cases": [
            {
                "id": "Q001",
                "category": "single",
                "expected_behavior": "answer",
                "predicted_agent": "telemetry",
                "routing_correct": True,
                "answer_correct": True,
                "refusal_correct": True,
                "intent_seconds": 0.1,
                "agent_seconds": 0.2,
                "total_seconds": 0.3,
                "intent_tokens": 3,
                "intent_output_tokens": 1,
                "agent_input_tokens": 7,
                "agent_output_tokens": 2,
                "retry_wait_seconds": 0.0,
                "missing_facts": [],
                "missing_numbers": [],
            },
            {
                "id": "Q002",
                "category": "multi",
                "expected_behavior": "answer",
                "predicted_agent": "telemetry",
                "routing_correct": True,
                "answer_correct": False,
                "refusal_correct": True,
                "intent_seconds": 0.1,
                "agent_seconds": 0.4,
                "total_seconds": 0.5,
                "intent_tokens": 3,
                "intent_output_tokens": 1,
                "agent_input_tokens": 7,
                "agent_output_tokens": 2,
                "retry_wait_seconds": 1.0,
                "missing_facts": ["FBL-2501-117"],
                "missing_numbers": [],
            },
        ],
    }

    report = render_report(run)

    assert "Routing accuracy" in report
    assert "Mean retry wait" in report
    assert "Q002" in report and "FBL-2501-117" in report


def test_given_sdk_run_when_report_rendered_then_judge_status_is_disclosed() -> None:
    run = {
        "cases": [
            {
                "category": "unsupported",
                "expected_behavior": "refuse",
                "routing_correct": True,
                "answer_correct": True,
                "refusal_correct": True,
                "agent_seconds": 0.0,
                "intent_seconds": 0.1,
                "total_seconds": 0.1,
                "retry_wait_seconds": 0.0,
                "intent_tokens": 1,
                "agent_input_tokens": 0,
                "intent_output_tokens": 1,
                "agent_output_tokens": 0,
                "missing_facts": [],
                "missing_numbers": [],
                "id": "Q001",
                "predicted_agent": "unsupported",
            }
        ],
        "run_id": "20261030T000000Z",
        "created_at": "2026-10-30T00:00:00+00:00",
        "question_file": "/tmp/questions.jsonl",
        "metrics": {"groundedness.groundedness": 0.5},
        "versions": {"azure-ai-evaluation": "1.18.10"},
        "judge_telemetry": {"status": "unavailable"},
    }

    report = render_report(run)

    assert "`groundedness` applicable cases: 0/1" in report
    assert "Judge telemetry: `unavailable`" in report
    assert "20261030T000000Z" in report


def test_given_judge_rows_when_refusal_is_present_then_groundedness_is_excluded() -> None:
    rows = [
        {
            "inputs.expected_behavior": "answer",
            "outputs.groundedness.groundedness": 1.0,
            "outputs.relevance.relevance": 1.0,
        },
        {
            "inputs.expected_behavior": "refuse",
            "outputs.groundedness.groundedness": 0.0,
            "outputs.relevance.relevance": 0.0,
        },
    ]

    metrics = _applicable_judge_metrics(rows)

    assert metrics["groundedness.groundedness"] == 1.0
    assert metrics["relevance.relevance"] == 0.5


def test_given_exact_evaluators_when_expected_values_match_then_all_pass() -> None:
    assert routing_accuracy("telemetry", ["telemetry"])["score"] == 1.0
    assert expected_facts_found("Engine CX7-10001 is ready.", ["CX7-10001"])["score"] == 1.0
    assert expected_numbers_within_tolerance(
        "The value is 1,406.25.", [{"value": 1406.23, "tolerance": 0.05}]
    )["score"] == 1.0
    assert correct_refusal(True, "refuse")["score"] == 1.0


def test_given_model_settings_when_configuration_built_then_secret_is_not_repr() -> None:
    from contoso_aero.config import ModelSettings

    settings = ModelSettings(
        base_url="https://example.test/v1",
        api_key="secret-value",
        model_name="model",
    )
    configuration = build_model_configuration(settings)

    assert configuration["base_url"] == settings.base_url
    assert configuration["model"] == settings.model_name
    assert configuration["api_key"] == "secret-value"
    assert set(sdk_versions()) == {"azure-ai-evaluation", "langgraph"}


def test_given_results_finish_out_of_order_when_paired_then_each_question_gets_its_own_result() -> None:
    first = Question("Q001", "single", "First?", ["telemetry"])
    second = Question("Q002", "single", "Second?", ["service"])
    finished = [_result("Second?", "service", "two"), _result("First?", "telemetry", "one")]

    paired = _pair_results([first, second], finished)

    assert [(q.id, r.answer) for q, r in paired] == [("Q001", "one"), ("Q002", "two")]


def test_given_missing_result_when_paired_then_the_question_is_named() -> None:
    question = Question("Q001", "single", "First?", ["telemetry"])

    with pytest.raises(ValueError, match="Q001"):
        _pair_results([question], [])


def test_given_duplicate_question_text_when_loaded_then_file_is_rejected(tmp_path) -> None:
    row = '{"id": "Q%s", "category": "single", "question": "Same?", "expected_agents": ["telemetry"]}'
    path = tmp_path / "questions.jsonl"
    path.write_text(row % "001" + "\n" + row % "002" + "\n")

    with pytest.raises(ValueError, match="unique"):
        load_questions(path)



def test_given_shared_lock_when_judges_run_in_threads_then_one_model_call_is_in_flight() -> None:
    lock = threading.Lock()
    active, peak = [0], [0]

    def judge(**kwargs: object) -> dict[str, object]:
        active[0] += 1
        peak[0] = max(peak[0], active[0])
        time.sleep(0.01)
        active[0] -= 1
        return {"score": 5.0, **kwargs}

    serialized = SerializedEvaluator(judge, lock)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda i: serialized(query=str(i)), range(16)))

    assert peak[0] == 1
    assert results[3] == {"score": 5.0, "query": "3"}


def _corpus() -> list[Question]:
    counts = {"single": 24, "multi": 23, "unsupported": 12}
    questions, number = [], 0
    for category, count in counts.items():
        for _ in range(count):
            number += 1
            agents = [] if category == "unsupported" else ["telemetry"]
            questions.append(Question(f"Q{number:03d}", category, f"Question {number}?", agents))
    return questions


def test_given_corpus_when_sampled_then_every_category_keeps_its_share() -> None:
    sample = sample_questions(_corpus(), 15, seed=20260612)

    categories = [question.category for question in sample]

    assert len(sample) == 15
    assert (categories.count("single"), categories.count("multi"), categories.count("unsupported")) == (6, 6, 3)


def test_given_same_seed_when_sampled_twice_then_the_same_questions_are_picked() -> None:
    first = [q.id for q in sample_questions(_corpus(), 15, seed=7)]

    assert first == [q.id for q in sample_questions(_corpus(), 15, seed=7)]
    assert first == sorted(first)


def test_given_report_without_judges_when_rendered_then_tables_stay_intact() -> None:
    question = Question("Q001", "single", "What is the value?", ["telemetry"], ["CX7-10001"])
    case = asdict(_score(question, _result(question.question, "telemetry", "CX7-10001")))

    report = render_report({"run_id": "r", "cases": [case], "judges_run": False})

    category_table = report.split("## By category")[1].split("##")[0]
    assert "| single | 1 |" in category_table
    assert "Not run in this evaluation" in report


def test_given_known_counts_when_wilson_interval_computed_then_bounds_match() -> None:
    low, high = wilson_interval(22, 24)
    assert (round(low * 100, 1), round(high * 100, 1)) == (74.2, 97.7)
    low, high = wilson_interval(0, 23)
    assert low == 0.0 and round(high * 100, 1) == 14.3


def test_given_no_cases_when_wilson_interval_computed_then_zero_interval_is_returned() -> None:
    assert wilson_interval(0, 0) == (0.0, 0.0)


def test_given_run_when_report_rendered_then_rates_carry_confidence_intervals() -> None:
    question = Question("Q001", "single", "What is the value?", ["telemetry"], ["CX7-10001"])
    case = asdict(_score(question, _result(question.question, "telemetry", "CX7-10001")))
    report = render_report({"run_id": "r", "cases": [case], "judges_run": False})
    assert "95% CI" in report
    assert "noisy" in report

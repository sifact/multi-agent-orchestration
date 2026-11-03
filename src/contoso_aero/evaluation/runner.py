"""Run the shared JSONL evaluation corpus and persist machine-readable results."""

from __future__ import annotations

import argparse
import json
import random
import tempfile
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from ..agents.common import AgentContext
from ..config import DataSettings, ModelSettings, SettingsError, load_model_settings
from ..coordination import ask_coordinated
from ..llm import ChatCompletionClient, ModelError
from ..routing import PipelineResult, ask
from .evaluators import (
    correct_refusal,
    expected_facts_found,
    expected_numbers_within_tolerance,
    routing_accuracy,
)
from .input import build_row, project_record
from .questions import Question
from .sdk import run_sdk_target_evaluation
from .target import (
    build_judge_evaluators,
    build_model_configuration,
    build_pipeline_target,
    sdk_versions,
)


@dataclass(frozen=True, slots=True)
class CaseResult:
    """Scoring for one question, including the raw answer and measured costs."""

    id: str
    category: str
    question: str
    expected_agents: list[str]
    predicted_agent: str
    predicted_agents: list[str]
    routing_correct: bool
    answer: str
    answer_correct: bool
    refusal_correct: bool
    expected_behavior: str
    expected_facts: list[str]
    missing_facts: list[str]
    expected_numbers: list[dict[str, float]]
    missing_numbers: list[dict[str, float]]
    intent_seconds: float
    agent_seconds: float
    total_seconds: float
    intent_tokens: int
    intent_output_tokens: int
    agent_input_tokens: int
    agent_output_tokens: int
    retry_wait_seconds: float
    model_calls: int
    tool_calls: int
    error: str | None


@dataclass(frozen=True, slots=True)
class EvaluationRun:
    """A complete evaluation run, suitable for JSON persistence and later comparison."""

    run_id: str
    created_at: str
    question_file: str
    cases: list[CaseResult]


def load_questions(path: Path) -> list[Question]:
    """Load and validate the existing question-set shape without changing its source."""
    questions: list[Question] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        try:
            raw = json.loads(line)
            questions.append(Question(**raw))
        except (json.JSONDecodeError, TypeError, KeyError) as error:
            raise ValueError(f"Invalid evaluation question at line {line_number}: {error}") from error
    if not questions:
        raise ValueError(f"Evaluation question file is empty: {path}")
    texts = [question.question for question in questions]
    if len(set(texts)) != len(texts):
        raise ValueError(f"Question texts must be unique so results can be paired: {path}")
    return questions


def run_evaluation(
    questions: list[Question],
    context: AgentContext,
    question_file: Path,
    pipeline: Literal["router", "coordinator"] = "router",
) -> EvaluationRun:
    """Run every question in order; one model failure is recorded, not silently skipped."""
    created = datetime.now(UTC)
    if pipeline == "router":
        run = ask
    elif pipeline == "coordinator":
        run = ask_coordinated
    else:
        raise ValueError(f"Unknown evaluation pipeline '{pipeline}'.")
    cases = [_score(question, run(question.question, context)) for question in questions]
    return EvaluationRun(
        run_id=created.strftime("%Y%m%dT%H%M%SZ"),
        created_at=created.isoformat(),
        question_file=str(question_file),
        cases=cases,
    )


def write_run(run: EvaluationRun, path: Path) -> None:
    """Write one complete result atomically so a partial run is never a valid artifact."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(asdict(run), indent=2, ensure_ascii=False) + "\n")
    temporary.replace(path)


def _score(question: Question, result: PipelineResult) -> CaseResult:
    # The same evaluator callables the SDK runs, so the two scoring paths cannot drift apart.
    facts = expected_facts_found(result.answer, question.expected_facts)
    numbers = expected_numbers_within_tolerance(result.answer, question.expected_numbers)
    missing_facts, missing_numbers = facts["missing_facts"], numbers["missing_numbers"]
    answer_correct = facts["passed"] and numbers["passed"] and result.error is None
    refusal_correct = correct_refusal(result.refused, question.expected_behavior)["passed"]
    predicted = result.label
    # A router answer is complete only when one agent is sufficient. Multi-agent
    # rows intentionally score false: that is the baseline limitation project 2
    # is meant to measure.
    if result.plan is None and not result.agents_called:
        routing_correct = routing_accuracy(predicted, question.expected_agents)["passed"]
    else:
        routing_correct = routing_accuracy(
            predicted, question.expected_agents, predicted_agents=result.agents_called
        )["passed"]
    return CaseResult(
        id=question.id,
        category=question.category,
        question=question.question,
        expected_agents=question.expected_agents,
        predicted_agent=predicted,
        predicted_agents=list(result.agents_called),
        routing_correct=routing_correct,
        answer=result.answer,
        answer_correct=answer_correct,
        refusal_correct=refusal_correct,
        expected_behavior=question.expected_behavior,
        expected_facts=question.expected_facts,
        missing_facts=missing_facts,
        expected_numbers=question.expected_numbers,
        missing_numbers=missing_numbers,
        intent_seconds=result.intent_seconds,
        agent_seconds=result.agent_seconds,
        total_seconds=result.total_seconds,
        intent_tokens=result.intent.input_tokens if result.intent else 0,
        intent_output_tokens=result.intent.output_tokens if result.intent else 0,
        agent_input_tokens=result.agent.input_tokens if result.agent else 0,
        agent_output_tokens=result.agent.output_tokens if result.agent else 0,
        retry_wait_seconds=(
            (result.intent.retry_wait_seconds if result.intent else 0.0)
            + (result.agent.retry_wait_seconds if result.agent else 0.0)
        ),
        model_calls=(1 if result.intent else 0) + (result.agent.model_calls if result.agent else 0),
        tool_calls=result.agent.tool_calls if result.agent else 0,
        error=result.error or (result.agent.error if result.agent else None),
    )


def _build_context() -> tuple[AgentContext, Path, ModelSettings]:
    data = DataSettings()
    if not data.database_path.is_file():
        raise SettingsError("Dataset missing: run `uv run python -m contoso_aero.data` first.")
    settings = load_model_settings()
    return (
        AgentContext(
            model=ChatCompletionClient(settings),
            database_path=data.database_path,
            knowledge_dir=data.knowledge_dir,
            max_steps=settings.max_agent_steps,
        ),
        data.eval_path,
        settings,
    )


def sample_questions(questions: list[Question], size: int, seed: int) -> list[Question]:
    """Pick a fixed sample that keeps each category's share, for judge runs on a token budget.

    The free endpoint allows 200,000 tokens a day, which cannot cover judges on every
    question; a seeded, category-balanced sample keeps judge scores comparable between runs.
    """
    if not 0 < size <= len(questions):
        raise ValueError(f"Sample size must be between 1 and {len(questions)}.")
    by_category: dict[str, list[Question]] = {}
    for question in questions:
        by_category.setdefault(question.category, []).append(question)
    quotas = {name: max(1, round(size * len(group) / len(questions)))
              for name, group in by_category.items()}
    while sum(quotas.values()) > size:
        quotas[max(quotas, key=quotas.get)] -= 1
    while sum(quotas.values()) < size:
        quotas[min(quotas, key=lambda name: quotas[name] / len(by_category[name]))] += 1
    rng = random.Random(seed)
    picked = [question for name in sorted(by_category)
              for question in rng.sample(by_category[name], quotas[name])]
    return sorted(picked, key=lambda question: question.id)


def _build_sdk_run(questions: list[Question], context: AgentContext, settings: ModelSettings,
                   question_file: Path, output: Path, with_judges: bool = True,
                   pipeline: Literal["router", "coordinator"] = "router") -> dict[str, object]:
    results: list[PipelineResult] = []
    with tempfile.TemporaryDirectory(prefix="contoso-aero-eval-") as directory:
        input_path = Path(directory) / "questions.jsonl"
        input_path.write_text("\n".join(json.dumps({
            "id": question.id,
            "category": question.category,
            "question": question.question,
            "expected_agents": question.expected_agents,
            "expected_facts": question.expected_facts,
            "expected_numbers": question.expected_numbers,
            "expected_behavior": question.expected_behavior,
        }) for question in questions) + "\n")
        # The SDK runs rows and evaluators concurrently; one lock keeps a single model call
        # in flight, so agent latency is not inflated by contention and judges stay under
        # the endpoint's tokens-per-minute limit instead of exhausting their 429 retries.
        model_lock = threading.Lock()
        target = build_pipeline_target(context, results.append, model_lock, pipeline)
        judges = (build_judge_evaluators(build_model_configuration(settings), model_lock)
                  if with_judges else None)
        sdk_result = run_sdk_target_evaluation(input_path, output, target, judges)
    paired = _pair_results(questions, results)
    rows = [build_row(question, result, seed=0) for question, result in paired]
    created = datetime.now(UTC)
    record = project_record(rows, sdk_result, sdk_versions(),
                            run_id=created.strftime("%Y%m%dT%H%M%SZ"),
                            created_at=created.isoformat(),
                            question_file=str(question_file.resolve()),
                            cases=[asdict(_score(question, result)) for question, result in paired])
    record["judges_run"] = with_judges
    record["pipeline"] = pipeline
    return record


def _pair_results(questions: list[Question],
                  results: list[PipelineResult]) -> list[tuple[Question, PipelineResult]]:
    """Match results to questions by text, because the SDK runs target rows concurrently.

    Results arrive in completion order, not file order, so pairing by position would score
    each answer against another question's expected facts.
    """
    by_question = {result.question: result for result in results}
    missing = [question.id for question in questions if question.question not in by_question]
    if missing:
        raise ValueError(f"No pipeline result for questions: {', '.join(missing)}")
    return [(question, by_question[question.question]) for question in questions]


def main(argv: list[str] | None = None) -> int:
    """Run the corpus; paths can be overridden for repeatable CI or local experiments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--pipeline", choices=("router", "coordinator"), default="router")
    parser.add_argument("--no-judges", action="store_true",
                        help="Exact checks only; skips the three LLM judges to save tokens.")
    parser.add_argument("--sample", type=int,
                        help="Run a fixed, category-balanced sample of this many questions.")
    args = parser.parse_args(argv)
    try:
        context, default_questions, settings = _build_context()
        question_path = args.questions or default_questions
        questions = load_questions(question_path)
        if args.sample is not None:
            questions = sample_questions(questions, args.sample, DataSettings().seed)
            output = _pipeline_output(args.output, args.pipeline)
            record = _build_sdk_run(questions, context, settings, question_path, output,
                                    with_judges=not args.no_judges, pipeline=args.pipeline)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
    except (ModelError, SettingsError, ValueError, OSError) as error:
        print(f"Evaluation failed: {error}")
        return 2
    print(f"Wrote {len(record['cases'])} cases to {output}")
    return 0


def _pipeline_output(
    requested: Path | None,
    pipeline: Literal["router", "coordinator"],
) -> Path:
    """Give coordinator runs a separate filename even when a router path is requested."""
    path = requested or Path("data/eval/runs/latest.json")
    if pipeline == "router" or path.stem.endswith("-coordinator"):
        return path
    return path.with_name(f"{path.stem}-coordinator{path.suffix}")


if __name__ == "__main__":
    raise SystemExit(main())

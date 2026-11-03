"""Probe coordinator plans on the hand-written dev set without dispatching agents."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from ..config import DataSettings, SettingsError, load_model_settings
from ..coordination import CoordinatorSettings, Plan, plan_question
from ..llm import ChatCompletionClient, ModelClient, ModelError
from ..routing.router import ROUTES

INVALID_PLAN = "invalid plan"


@dataclass(frozen=True, slots=True)
class ProbeItem:
    """One dev question and the complete set of agents its plan should select."""

    id: str
    expected_agents: tuple[str, ...]
    question: str


@dataclass(frozen=True, slots=True)
class ProbeResult:
    """All planned agent sets observed for one repeated dev question."""

    item: ProbeItem
    planned_agents: tuple[tuple[str, ...], ...]
    unusable_replies: tuple[str, ...] = ()

    @property
    def passed(self) -> bool:
        """Require every repeat to select precisely the expected agent set."""
        expected = set(self.item.expected_agents)
        return bool(self.planned_agents) and all(set(agents) == expected
                                                 for agents in self.planned_agents)


def load_probe(path: Path) -> list[ProbeItem]:
    """Load the coordination dev set and reject malformed rows or unknown agents."""
    items: list[ProbeItem] = []
    for line_number, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid coordination probe JSON at line {line_number}.") from error
        if not isinstance(row, dict) or set(row) != {"id", "expected_agents", "question"}:
            raise ValueError(f"Invalid coordination probe fields at line {line_number}.")
        row_id, expected, question = row["id"], row["expected_agents"], row["question"]
        if not isinstance(row_id, str) or not row_id.strip():
            raise ValueError(f"Invalid coordination probe id at line {line_number}.")
        if not isinstance(expected, list) or not all(isinstance(agent, str) for agent in expected):
            raise ValueError(f"Invalid expected_agents at line {line_number}.")
        if len(set(expected)) != len(expected) or not set(expected) <= set(ROUTES):
            raise ValueError(f"Unknown or duplicate expected agent at line {line_number}.")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"Invalid coordination probe question at line {line_number}.")
        items.append(ProbeItem(row_id, tuple(expected), question))
    if not items:
        raise ValueError(f"Coordination probe is empty: {path}")
    ids = [item.id for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError(f"Coordination probe ids must be unique in {path}.")
    return items


def run_probe(
    items: list[ProbeItem],
    model: ModelClient,
    repeat: int = 1,
    settings: CoordinatorSettings | None = None,
) -> list[ProbeResult]:
    """Ask the planner only, retaining the selected agent set for each repeat."""
    if repeat < 1:
        raise ValueError("repeat must be at least one.")
    results: list[ProbeResult] = []
    for item in items:
        observations: list[tuple[str, ...]] = []
        unusable: list[str] = []
        for _ in range(repeat):
            result = plan_question(item.question, model, settings)
            if result.invalid_reply is not None:
                # The model answered but not with a valid plan: that is a failure of this
                # question, so record it and keep probing instead of discarding the run.
                observations.append((INVALID_PLAN,))
                unusable.append(result.invalid_reply)
            elif result.error or result.plan is None:
                raise ModelError(result.error or f"Planner produced no plan for {item.id}.")
            else:
                observations.append(_planned_agents(result.plan))
        results.append(ProbeResult(item, tuple(observations), tuple(unusable)))
    return results


def format_results(results: list[ProbeResult]) -> str:
    """Render a concise table and the number of questions that passed."""
    lines = ["| ID | Expected agents | Planned agents per run | Result |",
             "|---|---|---|---|"]
    for result in results:
        expected = ", ".join(result.item.expected_agents) or "none"
        observed = "; ".join(", ".join(agents) or "none" for agents in result.planned_agents)
        lines.append(f"| {result.item.id} | {expected} | {observed} | "
                     f"{'pass' if result.passed else 'FAIL'} |")
    unusable = [(r.item.id, reply) for r in results for reply in r.unusable_replies]
    if unusable:
        lines.extend(["", "Unusable planner replies (no valid plan after one retry):"])
        lines.extend(f"* {item_id}: {reply[:200]!r}" for item_id, reply in unusable)
    passed = sum(result.passed for result in results)
    lines.extend(["", f"{passed}/{len(results)} passed."])
    return "\n".join(lines)


def _planned_agents(plan: Plan) -> tuple[str, ...]:
    return tuple(sorted({step.agent for step in plan.steps}))


def main(argv: list[str] | None = None, model: ModelClient | None = None) -> int:
    """Run the planner probe; return 0 for pass, 1 for mismatch, or 2 for errors."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DataSettings().coordination_probe_path)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    try:
        items = load_probe(args.file)
        client = model or ChatCompletionClient(load_model_settings())
        results = run_probe(items, client, args.repeat)
    except (OSError, ValueError, SettingsError, ModelError) as error:
        print(f"Coordinator probe failed: {error}", file=sys.stderr)
        return 2
    print(format_results(results))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

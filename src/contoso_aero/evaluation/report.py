"""Render a persisted evaluation run as a short Markdown report."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

from .stats import wilson_interval


def render_report(run: dict[str, object]) -> str:
    """Render aggregate metrics and failures without including secrets or full prompts."""
    cases = run.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("Evaluation run has no cases.")
    total = len(cases)
    routing = sum(bool(case["routing_correct"]) for case in cases)
    answer_cases = [case for case in cases if case["expected_behavior"] == "answer"]
    answers = sum(bool(case["answer_correct"]) for case in answer_cases)
    refusal_cases = [case for case in cases if case["expected_behavior"] == "refuse"]
    refusals = sum(bool(case["refusal_correct"]) for case in refusal_cases)
    lines = [
        "# Contoso Aero Engines evaluation report",
        "",
        ("Rates on fewer than 30 cases are noisy, and differences inside overlapping "
         "intervals are not evidence of a change."),
        "",
        f"- Run: `{run.get('run_id', 'unknown')}`",
        f"- Created: `{run.get('created_at', 'unknown')}`",
        f"- Questions: {total}",
        "",
        "## Overall metrics",
        "",
        "| Metric | Result |",
        "|---|---:|",
        f"| Routing accuracy | {_fmt(routing, total)} |",
        f"| Answer correctness (answer cases) | {_fmt(answers, len(answer_cases))} |",
        f"| Correct refusals | {_fmt(refusals, len(refusal_cases))} |",
        f"| Mean intent latency | {_mean(cases, 'intent_seconds'):.3f}s |",
        f"| Mean agent latency (called agents) | {_mean([case for case in cases if case['agent_seconds'] > 0], 'agent_seconds'):.3f}s |",
        f"| Mean total latency | {_mean(cases, 'total_seconds'):.3f}s |",
        f"| Mean retry wait | {_mean(cases, 'retry_wait_seconds'):.3f}s |",
        f"| Input tokens | {sum(int(case['intent_tokens']) + int(case['agent_input_tokens']) for case in cases)} |",
        f"| Output tokens | {sum(int(case['intent_output_tokens']) + int(case['agent_output_tokens']) for case in cases)} |",
        "",
        "## By category",
        "",
        "| Category | Cases | Routing (exact) | Answers | Refusals | Mean total |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for case in cases:
        groups[str(case["category"])].append(case)
    for category, group in sorted(groups.items()):
        answer_group = [case for case in group if case["expected_behavior"] == "answer"]
        refusal_group = [case for case in group if case["expected_behavior"] == "refuse"]
        lines.append(
            f"| {category} | {len(group)} | {_rate(group, 'routing_correct')} | "
            f"{_rate(answer_group, 'answer_correct')} | {_rate(refusal_group, 'refusal_correct')} | "
            f"{_mean(group, 'total_seconds'):.3f}s |"
        )
    lines.extend(_judge_section(run, cases))
    failures = [case for case in cases if not case["answer_correct"] or not case["routing_correct"]]
    lines.extend(["", "## Cases needing review", ""])
    if not failures:
        lines.append("None.")
    else:
        lines.extend(["| ID | Category | Predicted | Routing | Answer | Missing facts/numbers |",
                      "|---|---|---|---|---|---|"])
        for case in failures:
            missing = list(case["missing_facts"]) + [
                str(number["value"]) for number in case["missing_numbers"]
            ]
            lines.append(
                f"| {case['id']} | {case['category']} | {case['predicted_agent']} | "
                f"{'yes' if case['routing_correct'] else 'no'} | "
                f"{'yes' if case['answer_correct'] else 'no'} | {', '.join(missing) or 'refusal'} |"
            )
    return "\n".join(lines) + "\n"


def _judge_section(run: dict[str, object], cases: list[dict[str, object]]) -> list[str]:
    """Judge scores, kept after the exact tables and labelled as indicative only."""
    total = len(cases)
    if run.get("judges_run") is False:
        return ["", "## Indicative judge metrics", "",
                "Not run in this evaluation (`--no-judges`); exact checks only."]
    lines: list[str] = []
    sdk_metrics = run.get("judge_metrics") or run.get("metrics")
    if isinstance(sdk_metrics, dict) and sdk_metrics:
        lines.extend([
            "",
            "## Indicative judge metrics",
            "",
            "These SDK judge scores are separate from the primary exact checks.",
            "",
            "| Metric | Score |",
            "|---|---:|",
        ])
        for name, value in sorted(sdk_metrics.items()):
            if any(term in str(name) for term in ("groundedness", "relevance", "intent_resolution")):
                lines.append(f"| {name} | {_format_metric(value)} |")
        versions = run.get("versions")
        if isinstance(versions, dict):
            lines.extend(["", "## Evaluation metadata", ""])
            for name, value in sorted(versions.items()):
                lines.append(f"- `{name}`: `{value}`")
        lines.extend(["", "## Judge applicability and telemetry", ""])
        applicable = {
            "groundedness": sum(
                case.get("expected_behavior") != "refuse"
                for case in cases if isinstance(case, dict)
            ),
            "relevance": sum(1 for case in cases if isinstance(case, dict)),
            "intent_resolution": sum(1 for case in cases if isinstance(case, dict)),
        }
        for name, denominator in applicable.items():
            lines.append(f"- `{name}` applicable cases: {denominator}/{total}")
        telemetry = run.get("judge_telemetry")
        if isinstance(telemetry, dict):
            lines.append(f"- Judge telemetry: `{telemetry.get('status', 'unknown')}`")
            if telemetry.get("reason"):
                lines.append(f"- Judge telemetry reason: {telemetry['reason']}")
    return lines


def _format_metric(value: object) -> str:
    if isinstance(value, (int, float)):
        return f"{value:.3f}"
    return str(value)


def _mean(cases: list[dict[str, object]], field: str) -> float:
    return mean(float(case[field]) for case in cases) if cases else 0.0


def _fmt(successes: int, total: int) -> str:
    if not total:
        return "n/a (0/0)"
    low, high = wilson_interval(successes, total)
    return f"{successes / total:.1%} ({successes}/{total}, 95% CI {low:.1%}–{high:.1%})"


def _rate(cases: list[dict[str, object]], field: str) -> str:
    return _fmt(sum(bool(case[field]) for case in cases), len(cases))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = render_report(json.loads(args.run.read_text()))
        output = args.output or args.run.with_suffix(".md")
        output.write_text(report)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Report failed: {error}")
        return 2
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

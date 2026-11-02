"""Routing probe: check intent detection on the dev set without running any agent.

The 59-question test set is a frozen release gate, so router tuning happens here instead.
Only the intent call runs, which keeps a probe to a few thousand tokens on a rate-limited
endpoint. Each question can be asked several times, because the model is not deterministic.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from ..config import DataSettings, SettingsError, load_model_settings
from ..llm import ChatCompletionClient, ModelClient, ModelError
from ..routing import LABELS, detect_intent


@dataclass(frozen=True, slots=True)
class ProbeItem:
    id: str
    expected: str
    question: str


@dataclass(frozen=True, slots=True)
class ProbeResult:
    item: ProbeItem
    labels: list[str]
    tokens: int

    @property
    def passed(self) -> bool:
        """A router that is right only some of the time has not passed."""
        return bool(self.labels) and all(label == self.item.expected for label in self.labels)


def load_probe(path: Path) -> list[ProbeItem]:
    """Read the dev set, rejecting duplicate ids and labels the router cannot return."""
    items = [ProbeItem(**json.loads(line)) for line in path.read_text().splitlines() if line.strip()]
    ids = [item.id for item in items]
    if len(set(ids)) != len(ids):
        raise ValueError(f"Probe ids must be unique in {path}.")
    unknown = sorted({item.expected for item in items} - set(LABELS))
    if unknown:
        raise ValueError(f"Unknown expected labels in {path}: {', '.join(unknown)}.")
    return items


def run_probe(items: list[ProbeItem], model: ModelClient, repeat: int = 1) -> list[ProbeResult]:
    """Ask each question `repeat` times through intent detection only."""
    results = []
    for item in items:
        labels, tokens = [], 0
        for _ in range(repeat):
            intent = detect_intent(item.question, model)
            labels.append(intent.label)
            tokens += intent.input_tokens + intent.output_tokens
        results.append(ProbeResult(item, labels, tokens))
    return results


def format_results(results: list[ProbeResult]) -> str:
    lines = ["| ID | Expected | Labels seen | Result |", "|---|---|---|---|"]
    for r in results:
        lines.append(f"| {r.item.id} | {r.item.expected} | {', '.join(r.labels)} | "
                     f"{'pass' if r.passed else 'FAIL'} |")
    passed = sum(r.passed for r in results)
    lines.append("")
    lines.append(f"{passed}/{len(results)} passed, {sum(r.tokens for r in results)} tokens used.")
    return "\n".join(lines)


def main(argv: list[str] | None = None, model: ModelClient | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DataSettings().probe_path)
    parser.add_argument("--repeat", type=int, default=1)
    args = parser.parse_args(argv)
    if args.repeat < 1:
        parser.error("--repeat must be at least 1")
    try:
        items = load_probe(args.file)
        client = model or ChatCompletionClient(load_model_settings())
        results = run_probe(items, client, args.repeat)
    except (OSError, ValueError, SettingsError, ModelError) as error:
        print(f"Probe failed: {error}", file=sys.stderr)
        return 2
    print(format_results(results))
    return 0 if all(r.passed for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

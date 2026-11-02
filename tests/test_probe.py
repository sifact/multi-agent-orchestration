"""Offline tests for the routing probe over the dev set."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from contoso_aero.config import DataSettings
from contoso_aero.evaluation.probe import load_probe, main
from contoso_aero.llm import ModelResponse


class LabelModel:
    """Replays intent labels in order, with a fixed token cost per call."""

    def __init__(self, *labels: str) -> None:
        self.labels = list(labels)

    def complete(self, messages: list[dict[str, object]],
                 tools: Sequence[dict[str, object]] = ()) -> ModelResponse:
        return ModelResponse(content=self.labels.pop(0), tool_calls=[], input_tokens=10,
                             output_tokens=1)


def _probe_file(tmp_path: Path, *rows: tuple[str, str]) -> Path:
    path = tmp_path / "probe.jsonl"
    path.write_text("".join(json.dumps({"id": f"P{i:02d}", "expected": label, "question": q}) + "\n"
                            for i, (label, q) in enumerate(rows, 1)))
    return path


def test_given_matching_labels_when_probed_then_all_pass(tmp_path, capsys) -> None:
    path = _probe_file(tmp_path, ("telemetry", "Engine count?"), ("knowledge", "What is the limit?"))

    code = main(["--file", str(path)], model=LabelModel("telemetry", "knowledge"))

    assert code == 0
    assert "2/2 passed, 22 tokens used." in capsys.readouterr().out


def test_given_one_mismatch_when_probed_then_exit_code_is_one(tmp_path, capsys) -> None:
    path = _probe_file(tmp_path, ("telemetry", "Engine count?"), ("knowledge", "What is the limit?"))

    code = main(["--file", str(path)], model=LabelModel("telemetry", "service"))

    assert code == 1
    assert "| P02 | knowledge | service | FAIL |" in capsys.readouterr().out


def test_given_flaky_label_when_repeated_then_question_fails(tmp_path, capsys) -> None:
    path = _probe_file(tmp_path, ("quality", "Which inspections failed?"))

    code = main(["--file", str(path), "--repeat", "2"], model=LabelModel("quality", "service"))

    assert code == 1
    assert "quality, service | FAIL" in capsys.readouterr().out


def test_given_unknown_expected_label_when_loaded_then_file_is_rejected(tmp_path) -> None:
    path = _probe_file(tmp_path, ("weather", "Is it raining?"))

    with pytest.raises(ValueError, match="weather"):
        load_probe(path)


def test_given_duplicate_ids_when_loaded_then_file_is_rejected(tmp_path) -> None:
    path = tmp_path / "probe.jsonl"
    row = json.dumps({"id": "P01", "expected": "telemetry", "question": "Q?"}) + "\n"
    path.write_text(row * 2)

    with pytest.raises(ValueError, match="unique"):
        load_probe(path)


def test_given_shipped_dev_set_when_loaded_then_it_is_valid_and_separate_from_test_set() -> None:
    settings = DataSettings()
    probe = {item.question for item in load_probe(settings.probe_path)}
    test_set = {json.loads(line)["question"] for line in settings.eval_path.read_text().splitlines()}

    assert len(probe) == 19
    assert not probe & test_set

"""Fault-mode inference on small hand-built runs, so it is tested without the NASA files."""

from __future__ import annotations

import random

from contoso_aero.data.cmapss import SENSORS, Cycle, EngineRun, infer_fault_mode


def _run(split: str, p30: list[float]) -> EngineRun:
    cycles = tuple(Cycle(i + 1, (0.0, 0.0, 100.0), {name: (p30[i] if name == "P30" else 1.0)
                                                    for name, _, _ in SENSORS}) for i in range(len(p30)))
    return EngineRun(split, 1, cycles, None)


def test_given_falling_p30_when_train_run_inferred_then_mode_is_hpc() -> None:
    assert infer_fault_mode(_run("train", [555.0 - 0.02 * i for i in range(200)])) == "hpc"


def test_given_rising_p30_when_train_run_inferred_then_mode_is_fan() -> None:
    assert infer_fault_mode(_run("train", [555.0 + 0.05 * i for i in range(200)])) == "fan"


def test_given_flat_noisy_p30_when_test_run_inferred_then_mode_is_unknown() -> None:
    rng = random.Random(1)
    assert infer_fault_mode(_run("test", [555.0 + rng.gauss(0, 0.5) for _ in range(60)])) == "unknown"


def test_given_clear_rising_trend_when_test_run_inferred_then_mode_is_fan() -> None:
    rng = random.Random(2)
    assert infer_fault_mode(_run("test", [555.0 + 0.05 * i + rng.gauss(0, 0.3) for i in range(120)])) == "fan"

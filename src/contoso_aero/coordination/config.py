"""Coordinator limits kept together so the workflow has one tuning surface."""

from __future__ import annotations

from dataclasses import dataclass

MAX_SUPPORTED_STEPS = 3


@dataclass(frozen=True, slots=True)
class CoordinatorSettings:
    """Bounds for planning and dispatch so every run stays predictable."""

    max_steps: int = MAX_SUPPORTED_STEPS
    findings_char_limit: int = 4_000
    invalid_plan_retries: int = 1

    def __post_init__(self) -> None:
        if not 1 <= self.max_steps <= MAX_SUPPORTED_STEPS:
            raise ValueError(f"max_steps must be between 1 and {MAX_SUPPORTED_STEPS}.")
        if self.findings_char_limit < 1:
            raise ValueError("findings_char_limit must be positive.")
        if self.invalid_plan_retries < 0:
            raise ValueError("invalid_plan_retries cannot be negative.")

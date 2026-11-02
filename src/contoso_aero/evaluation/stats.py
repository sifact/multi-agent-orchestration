"""Small statistics helpers for evaluation reports."""

from __future__ import annotations

from math import sqrt


def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    """Return the Wilson score interval for a proportion, or (0.0, 0.0) when total is 0."""
    if total <= 0:
        return (0.0, 0.0)
    p = successes / total
    z2 = z * z
    denominator = 1 + z2 / total
    centre = (p + z2 / (2 * total)) / denominator
    margin = z * sqrt(p * (1 - p) / total + z2 / (4 * total * total)) / denominator
    return (max(0.0, centre - margin), min(1.0, centre + margin))

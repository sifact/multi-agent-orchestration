"""Deterministic evaluation callables registered with Azure AI Evaluation."""

from __future__ import annotations

import re
from collections.abc import Sequence


def routing_accuracy(
    predicted_agent: str,
    expected_agents: Sequence[str],
    predicted_agents: Sequence[str] | None = None,
    **kwargs: object,
) -> dict[str, object]:
    """Score a complete agent set when supplied, otherwise preserve the v1 route rule."""
    expected = list(expected_agents)
    if predicted_agents is not None:
        correct = set(predicted_agents) == set(expected)
    else:
        correct = (predicted_agent == expected[0] if len(expected) == 1
                   else not expected and predicted_agent == "unsupported")
    return {"score": float(correct), "passed": correct}


def expected_facts_found(
    response: str, expected_facts: Sequence[str], **kwargs: object
) -> dict[str, object]:
    """Score whether every expected fact occurs in the normalized answer."""
    answer = _normalize(response)
    missing = [fact for fact in expected_facts if _normalize(fact) not in answer]
    return {"score": float(not missing), "passed": not missing, "missing_facts": missing}


def expected_numbers_within_tolerance(
    response: str, expected_numbers: Sequence[dict[str, float]], **kwargs: object
) -> dict[str, object]:
    """Score whether every expected numeric value is present within its tolerance."""
    missing = [
        number for number in expected_numbers
        if not _contains_number(response, number["value"], number["tolerance"])
    ]
    return {"score": float(not missing), "passed": not missing, "missing_numbers": missing}


def correct_refusal(
    refused: bool, expected_behavior: str, **kwargs: object
) -> dict[str, object]:
    """Score refusal behavior independently from answer correctness."""
    expected_refusal = expected_behavior == "refuse"
    correct = bool(refused) == expected_refusal
    return {"score": float(correct), "passed": correct}


# Models often write serials and signs with typographic hyphens, dashes, minus signs and
# non-breaking spaces; expected facts are plain ASCII, so both sides are folded first.
_TYPOGRAPHY = str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
                             "\u2014": "-", "\u2212": "-", "\u00a0": " ", "\u202f": " "})


def _contains_number(answer: str, expected: float, tolerance: float) -> bool:
    normalized = answer.translate(_TYPOGRAPHY)
    pattern = r"[\-+]?(?:(?:\d[\d,]*)(?:\.\d*)?|\.\d+)(?:[eE][\-+]?\d+)?"
    values = re.findall(pattern, normalized)
    return any(abs(float(value.replace(",", "")) - expected) <= tolerance for value in values)


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.translate(_TYPOGRAPHY)).strip().casefold()

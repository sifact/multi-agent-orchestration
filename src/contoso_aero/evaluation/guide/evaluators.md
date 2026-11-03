# evaluators.py

Deterministic evaluator functions for routing, facts, numbers, and refusals.

* Compares a supplied agent set with the expected set; without it, preserves the v1 route rule.
* Requires every expected fact in the response after folding case, spacing and typographic hyphens.
* Matches numeric values using each question's explicit tolerance.
* Scores refusal behavior separately from answer content.
* Returns SDK-compatible score dictionaries without reading evaluation files.

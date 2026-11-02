# evaluators.py

Deterministic evaluator functions for routing, facts, numbers, and refusals.

* Compares the selected route with the expected one-agent or refusal route.
* Requires every expected fact in the response after folding case, spacing and typographic hyphens.
* Matches numeric values using each question's explicit tolerance.
* Scores refusal behavior separately from answer content.
* Returns SDK-compatible score dictionaries without reading evaluation files.

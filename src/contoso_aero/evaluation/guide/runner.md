# runner.py

Runs the shared JSONL corpus and scores each question with measured model costs.

* Pairs each result with its question by text, because SDK rows finish out of order.
* Scores each case with the same evaluator functions the SDK path registers.
* Can skip judges or run a seeded, category-balanced sample to fit a daily token budget.
* Writes an atomic JSON artifact so interrupted runs are not mistaken for results.
* Records errors as failed cases instead of silently dropping them.

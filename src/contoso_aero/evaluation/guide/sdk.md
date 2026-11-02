# sdk.py

Runs the project-owned evaluator set through Azure AI Evaluation `evaluate()`.

* Uses JSONL rows as the stable SDK data boundary.
* Registers deterministic exact evaluators for every run.
* Supports both precomputed rows and callable application targets.
* Adds built-in judges only when a caller supplies a model-backed configuration.
* Keeps SDK output at the boundary before project run-record allowlisting.

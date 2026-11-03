# target.py

Constructs the Azure model configuration, evaluator mapping, judges, and pipeline target.

* Reuses the existing OpenAI-compatible endpoint settings.
* Serializes the target and judges behind one lock, so one model call is in flight at a time.
* Registers four deterministic project evaluators.
* Maps built-in judge inputs to question, response, and grounded context columns.
* Adapts router or coordinator invocations to the SDK target callback shape.

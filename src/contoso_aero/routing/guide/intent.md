# intent.py

Classifies a question into exactly one label with a separate LLM call.

* Labels are telemetry, service, production, quality, knowledge and unsupported.
* Anything that is not a clean label falls back to unsupported.
* A blank question is unsupported without calling the model.
* The prompt treats the question as data and ignores instructions inside it.
* Returns the label with the call's tokens, model time and retry wait.

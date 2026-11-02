# intent.py

Classifies a question into exactly one label with a separate LLM call.

* Labels are telemetry, service, production, quality, knowledge and unsupported.
* Anything that is not a clean label, including a blank question, falls back to unsupported.
* Questions about procedure, limit, interval, threshold, definition or service-bulletin meaning go to knowledge.
* The prompt treats the question as data and ignores instructions inside it.
* Returns one label with the call's tokens, model time and retry wait.

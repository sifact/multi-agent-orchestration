# input.py

Builds bounded evaluation rows and allowlisted project run-record envelopes.

* Keeps expected values and application outputs in one stable row contract.
* Includes bounded tool-result context for groundedness judging.
* Keeps application telemetry separate from judge telemetry.
* Records unavailable SDK judge telemetry explicitly rather than reusing agent metrics.
* Writes JSONL rows without credentials or raw SDK internals.

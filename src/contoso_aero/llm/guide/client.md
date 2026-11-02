# client.py

Sends chat-completions requests and reports model time, retry wait and tokens separately.

* Adapts nl-to-sql's client: standard-library HTTP with an injectable transport and sleep.
* Retries HTTP 429 using Retry-After, fails fast when the wait exceeds its cap, and records waits apart.
* Retries a host-rejected malformed tool call a few times before failing.
* Parses only the supported response shape and raises ModelError for anything else.
* Never echoes the API key; errors carry a status code or a fixed message only.

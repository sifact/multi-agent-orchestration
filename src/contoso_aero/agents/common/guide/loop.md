# loop.py

Runs the model and tool loop for an agent in plain Python, with no agent framework.

* Calls the model, runs any requested tools, and repeats until the model answers in text.
* A step limit forces a final answer without tools so a loop cannot run forever.
* Token counts, model time and retry wait accumulate on one running cost record.
* A ModelError ends the run and is reported on the reply instead of being raised.
* Records each tool call's arguments and output; unknown tools return an error, not a crash.

# probe.py

Checks intent detection against the routing dev set without running any agent.

* Reads `data/eval/routing_probe.jsonl`, rejecting duplicate ids and labels the router cannot return.
* Calls only `detect_intent`, so a probe costs a few thousand tokens instead of a full evaluation.
* Asks each question `--repeat` times; it passes only if every label matches, so flaky routing fails.
* Prints a table of labels seen per question with the total tokens used.
* Exits 0 when all pass, 1 when any question fails, and 2 when the file or endpoint is unusable.

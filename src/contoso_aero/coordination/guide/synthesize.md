# synthesize.py

Merges multiple step answers while preserving provenance and missing-information notices.

* Makes one synthesis model call for a multi-step plan.
* Supplies successful answers with the name of the agent that produced each one.
* Sends failed or skipped parts as missing work, not as evidence.
* Requires factual statements to cite their source agent.
* Returns model cost and errors without hiding failed synthesis.

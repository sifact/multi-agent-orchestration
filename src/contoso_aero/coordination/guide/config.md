# config.py

Keeps the coordinator's tunable limits in one immutable settings object.

* Caps supported plans at three ordered steps.
* Sets how many characters of earlier findings a dependent step can receive.
* Sets the number of retries allowed after invalid planner output.
* Rejects settings that would violate coordinator bounds.
* Uses frozen dataclass values so one run cannot change limits midway.

# dispatch.py

Runs plan steps sequentially through the existing `ROUTES` table.

* Calls each step through its existing `handle(question, context)` entry point.
* Appends only successful dependency answers as bounded findings.
* Skips a step when any dependency failed or was skipped.
* Records each step's reply, status, error and elapsed seconds.
* Logs unexpected handler exceptions and preserves them as failed steps.

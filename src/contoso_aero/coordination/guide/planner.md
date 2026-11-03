# planner.py

Makes one planning call and retries only invalid plan output within configured bounds.

* Reuses the v1 agent-category descriptions instead of duplicating them.
* Requests either an unsupported result or an ordered plan of one to three steps.
* Retries schema or validation failures without falling back to the router.
* Returns model tokens, time, retry wait and call count with the plan.
* Reports model or plan errors so callers can stop before agent dispatch.

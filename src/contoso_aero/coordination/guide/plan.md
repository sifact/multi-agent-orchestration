# plan.py

Parses and validates the planner's JSON before it can dispatch any agent.

* Defines immutable `Plan` and `PlanStep` records.
* Supports an explicit unsupported result with no steps.
* Restricts steps to known route names and the configured maximum.
* Requires unique ids and non-empty self-contained sub-questions.
* Allows dependencies only on earlier steps, preventing cycles and forward references.

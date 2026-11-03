# graph.py

Wires planning, sequential dispatch and optional synthesis into the v2 request pipeline.

* Plans every request once and returns a fixed refusal for unsupported plans.
* Stops with an error when planning fails instead of falling back to v1.
* Returns one-step answers unchanged and synthesizes plans with multiple steps.
* Exposes agent calls, plan, individual stage times and step details on the result.
* Aggregates model and tool costs so evaluation and groundedness retain their evidence.

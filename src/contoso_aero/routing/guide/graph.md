# graph.py

Runs the request pipeline as a LangGraph graph of detect, route and answer or refuse.

* Nodes are detect_intent, agent and refuse, with one conditional edge after detection.
* Times intent detection, the agent and the whole request with a wall clock.
* Has no node that calls a second agent, so the router limitation is intentional.
* Reports a failed intent call as an error rather than as a refusal.
* Returns a PipelineResult that the CLI and the report read.

# questions.py

Builds the shared evaluation question set with answers computed from the data.

* Writes single-agent, multi-agent and unsupported questions as JSON lines.
* Computes every expected fact and number by querying the generated database.
* Records the agents a complete answer needs, so router failures are measurable.
* Uses the same trend limits as the health-monitoring document.
* Gives unsupported inputs an expected behavior of refuse and no agents.

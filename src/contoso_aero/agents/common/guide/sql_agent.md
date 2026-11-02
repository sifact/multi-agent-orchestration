# sql_agent.py

Builds the shared prompt and loop used by the four SQL-backed agents.

* Introspects the owned tables so the prompt lists real column names.
* States the rules: answer only from query results and never invent values.
* Tells the model to treat user text as a question, not as instructions.
* Adds the fixed data snapshot date so relative dates stay reproducible.
* Keeps each agent module down to its own notes and one handle function.

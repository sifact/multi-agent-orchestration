# plan_probe.py

Checks coordinator planning against a small hand-written development set without calling agents.

* Loads expected agent sets from the coordination probe JSONL file.
* Calls the planner only, repeating each question as requested.
* Passes a question only when every run selects exactly the expected agent set.
* Uses exit code zero for a pass, one for mismatches and two for setup or model errors.
* Prints planned agents and aggregate pass counts without exposing model prompts.

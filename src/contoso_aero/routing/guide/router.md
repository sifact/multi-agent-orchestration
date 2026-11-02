# router.py

Maps each intent label to one agent module's handle function.

* Is a plain dict lookup table with no scoring or fallback logic.
* Imports each agent only through its package, never reaching inside it.
* Returns None for unsupported so the pipeline refuses safely.
* Holds the fixed refusal text returned without calling any agent.
* Never merges answers: one question reaches at most one agent.

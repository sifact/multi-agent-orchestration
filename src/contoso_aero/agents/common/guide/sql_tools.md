# sql_tools.py

Gives an agent a read-only SQL tool confined to the tables it owns.

* Opens SQLite in read-only mode and authorizes reads only on the owned tables.
* Allows a single SELECT; writes, other tables and stacked statements fail.
* Caps rows and cell length so large results cannot flood the model.
* Stops queries that run past a few seconds with a progress handler.
* Returns SQL errors as text so the model can correct its query.

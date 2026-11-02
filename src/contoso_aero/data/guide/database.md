# database.py

Writes the generated tables to SQLite and mirrors them as CSV.

* Rebuilds the database in a temporary file, then swaps it in.
* Chooses each column type from its first non-null value.
* Uses the first column as primary key, and esn plus cycle for telemetry.
* Indexes esn on every table that references engines.
* Declares which agent owns which tables, the boundary project 2 depends on.

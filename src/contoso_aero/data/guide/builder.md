# builder.py

Runs every generation step in a fixed order and writes the outputs.

* Threads one seeded random generator through every step for identical rebuilds.
* Loads C-MAPSS, infers fault modes and assigns stories before building the fleet.
* Builds production, quality and service records from the fleet.
* Writes the database, the CSV copies and the knowledge documents.
* Stores hidden answers in ground_truth, a table no agent owns.

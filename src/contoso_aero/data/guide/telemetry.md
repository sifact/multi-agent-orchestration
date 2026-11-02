# telemetry.py

Builds the condition-report table from the real C-MAPSS readings.

* Writes one row per engine per cycle, keyed by Contoso serial and cycle number.
* Adds the report date from the engine's timeline.
* Keeps the three operating settings and the 16 sensors that vary.
* Never alters a reading, because this is the dataset's only real data.
* Orders rows by serial and cycle so the table is stable across builds.

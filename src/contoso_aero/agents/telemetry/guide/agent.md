# agent.py

Answers questions about fleet engines and their C-MAPSS sensor readings.

* Owns the operators, aircraft, engines and engine_telemetry tables.
* Adds a sensor glossary built from the real C-MAPSS column definitions.
* Explains that the latest reading is the highest cycle per engine serial.
* Exposes one public function, handle(question, context).
* Cannot see builds, quality or service records and says so.

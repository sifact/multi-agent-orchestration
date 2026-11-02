# agent.py

Answers questions about where, when and from which lots an engine was built.

* Owns the engine_builds, module_builds and supplier_lots tables; maps plant ids to names from the reference records.
* Finds engines built with a lot by filtering module_builds on lot_id.
* Distinguishes consumed lots from quarantined lots by supplier_lots.status.
* Exposes one public function, handle(question, context).
* Cannot see inspections, deviations or in-service data and says so.

# agent.py

Answers questions about inspections, nonconformance reports, deviations and quarantines.

* Owns the inspections, ncrs, deviations and lot_quarantines tables.
* Reads a lot as quarantined only while its quarantine status is open.
* Links deviations to lots through lot_id when the departure concerned a lot.
* Exposes one public function, handle(question, context).
* Cannot see which engines used a lot or any in-service data and says so.

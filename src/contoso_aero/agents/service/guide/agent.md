# agent.py

Answers questions about removals, shop visits, difficulty reports and borescope findings.

* Owns the removals, shop_visits, difficulty_reports and borescope_inspections tables.
* Describes difficulty reports as shaped on the public FAA service difficulty form.
* Treats unscheduled=1 as an unplanned removal.
* Exposes one public function, handle(question, context).
* Cannot see builds or quality records and says so.

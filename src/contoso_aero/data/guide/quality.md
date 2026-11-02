# quality.py

Creates inspections, nonconformance reports, deviations and lot quarantines.

* Inspects every module build on one characteristic, with a small random failure rate.
* Raises a rework NCR and a passing re-inspection for every failed inspection.
* Adds the story NCR for the torque wrench, naming how many HPC modules it affects.
* Adds the story deviation and records story-lot coating readings as accepted under it.
* Quarantines the story lot and marks it quarantined in the supplier lot table.

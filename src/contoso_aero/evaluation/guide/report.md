# report.py

Renders persisted evaluation results as aggregate Markdown metrics and review cases.

* Reports routing accuracy, answer correctness and correct refusals, each with a 95% Wilson interval.
* Breaks metrics down by single, multi and unsupported categories.
* Shows intent, agent, total and retry-wait latency separately.
* Puts judge scores after the exact tables, or says when a run skipped judges.
* Lists cases whose routing or answer score needs human review.

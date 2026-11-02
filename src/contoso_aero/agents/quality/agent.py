"""Quality agent: inspections, nonconformance reports, deviations and lot quarantines."""

from __future__ import annotations

from ...data import TABLE_OWNERS
from ..common import AgentContext, AgentReply, answer_with_sql

NAME = "quality"
TABLES = TABLE_OWNERS[NAME]

NOTES = """\
Facts about the data:
- inspections: measured characteristics per module with a pass/fail result.
- ncrs: nonconformance reports (description, root_cause, disposition, affected_from/affected_to).
- deviations: approved departures from specification, valid between approved_date and valid_to,
  linked to a supplier lot_id when the departure concerned a lot. status is 'open' or 'closed'.
- lot_quarantines: a lot is under quarantine while status is 'open'; 'released' once cleared.
- You cannot see which engines were built with a lot, nor any in-service data. If asked, say that
  belongs to another domain."""


def handle(question: str, context: AgentContext) -> AgentReply:
    """Answer a question about factory quality using only the quality tables."""
    return answer_with_sql(NAME, "quality", TABLES, NOTES, question, context)

"""Service and maintenance agent: removals, shop visits, difficulty reports, borescope findings."""

from __future__ import annotations

from ...data import TABLE_OWNERS
from ..common import AgentContext, AgentReply, answer_with_sql

NAME = "service"
TABLES = TABLE_OWNERS[NAME]

NOTES = """\
Facts about the data:
- removals: one row per engine removed from an aircraft; unscheduled=1 means unplanned.
- shop_visits: the repair visit after a removal, with findings and parts_replaced.
- difficulty_reports: Service Difficulty Reports shaped on the public FAA form 8070-1
  (part_name, part_number, part_condition, nature_of_condition, problem_description).
- borescope_inspections: periodic internal inspections with a finding and an action.
- Engine serials (esn) look like CX7-10114; operators are identified by short codes (NWA, FAB, ...).
- You cannot see build records, supplier lots or quality records. If asked who built an engine or
  which lot it used, say that belongs to another domain."""


def handle(question: str, context: AgentContext) -> AgentReply:
    """Answer a question about in-service maintenance using only the service tables."""
    return answer_with_sql(NAME, "service and maintenance", TABLES, NOTES, question, context)

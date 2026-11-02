"""Production traceability agent: where, when and from which parts each engine was built."""

from __future__ import annotations

from ...data import TABLE_OWNERS
from ...data.reference import PLANTS
from ..common import AgentContext, AgentReply, answer_with_sql

NAME = "production"
TABLES = TABLE_OWNERS[NAME]
_PLANT_NAMES = ", ".join(f"{plant.plant_id} = {plant.name}" for plant in PLANTS)

NOTES = f"""\
Facts about the data:
- engine_builds: one row per engine (plant_id, line, build_start, pass_off_date, EGT margin);
  plant ids map as follows: {_PLANT_NAMES}.
- module_builds: one row per module (FAN, LPC, HPC, COMB, HPT, LPT) of an engine, with the
  station, build_date, key_part and the supplier lot_id of that part.
- supplier_lots: lot_id, supplier, first_used/last_used window, engines_built and status
  ('consumed' or 'quarantined').
- To find the engines built with a lot, filter module_builds by lot_id.
- You cannot see inspections, nonconformance reports, deviations or in-service data. If asked about
  those, say they belong to another domain."""


def handle(question: str, context: AgentContext) -> AgentReply:
    """Answer a question about engine builds and supplier lots using only the production tables."""
    return answer_with_sql(NAME, "production traceability", TABLES, NOTES, question, context)

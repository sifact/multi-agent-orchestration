"""Engine telemetry agent: fleet engines and their C-MAPSS sensor readings."""

from __future__ import annotations

from ...data import TABLE_OWNERS
from ...data.cmapss import KEPT_SENSORS, SENSORS
from ..common import AgentContext, AgentReply, answer_with_sql

NAME = "telemetry"
TABLES = TABLE_OWNERS[NAME]


def _notes() -> str:
    glossary = "\n".join(f"- {n}: {d}{f' ({u})' if u else ''}" for n, d, u in SENSORS
                         if n in KEPT_SENSORS)
    return f"""\
Facts about the data:
- engine_telemetry holds one row per engine per flight cycle (report_date is the report date).
  Latest reading = the row with the highest cycle for that esn.
- engines.status is 'active' (still flying) or 'removed' (removal_date set). Engine serials look
  like CX7-10114. Temperatures are degR, pressures psia.
- Sensor columns:
{glossary}
- Health trend: a rising T50 or falling P30 over the engine's life signals degradation. Compare
  recent readings with the engine's first readings when asked about trends."""


def handle(question: str, context: AgentContext) -> AgentReply:
    """Answer a question about engine telemetry using only the fleet and sensor tables."""
    return answer_with_sql(NAME, "engine telemetry", TABLES, _notes(), question, context)

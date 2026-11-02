"""In-service records: removals, shop visits, FAA-style difficulty reports and borescope inspections.

Difficulty-report fields follow the public FAA Form 8070-1 layout, used for shape only.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from .fleet import Engine
from .reference import AIRCRAFT_TYPE, ENGINE_MODEL, FLIGHT_HOURS_PER_CYCLE, SHOPS
from .stories import FAN_STORY, HPC_STORY

# Report cycles between routine borescope inspections.
BORESCOPE_INTERVAL_CYCLES = 100

REMOVAL_REASONS = {
    "fan": "Fan vibration exceedance with fan efficiency loss",
    "hpc": "EGT margin exhausted from HPC performance deterioration",
}
WORKSCOPES = {"fan": "Fan module refurbishment", "hpc": "HPC performance restoration"}
FINDINGS = {
    ("fan", None): "Fan blade leading-edge erosion; fan efficiency below limit.",
    ("hpc", None): "HPC blade tip erosion with increased tip clearances.",
    ("fan", "fan_lot"): ("Fan blade root coating loss on 9 of 22 blades; coating thickness below "
                         "minimum; fretting at blade roots."),
    ("hpc", "hpc_station"): ("HPC stage 3 to 5 blisk tip rub; rotor stack bolt preload below "
                             "specification on 6 of 24 bolts."),
}
PARTS_REPLACED = {"fan": "Fan blade set (22 blades)", "hpc": "HPC stage 3-5 blisks"}
SDR_PARTS = {
    "fan": ("Fan blade", "CX7-72-1100", "Eroded", "Fan module", "Vibration"),
    "hpc": ("HPC blisk", "CX7-72-3100", "Worn", "HPC stage 3-5", "Exhaust gas temperature"),
}
ROUTINE_FINDINGS = (
    ("No findings.", "None; next inspection at interval."),
    ("Minor leading-edge erosion within limits.", "None; next inspection at interval."),
    ("Light combustor liner discoloration within limits.", "None; next inspection at interval."),
)
LATE_LIFE_FINDINGS = {
    "fan": ("Fan blade leading-edge erosion approaching limits.", "Reduce inspection interval to 50 cycles."),
    "hpc": ("HPC blade tip erosion approaching limits.", "Reduce inspection interval to 50 cycles."),
    "unknown": ("Minor erosion within limits.", "None; next inspection at interval."),
}


@dataclass(frozen=True, slots=True)
class ServiceRecords:
    removals: list[dict[str, object]]
    shop_visits: list[dict[str, object]]
    difficulty_reports: list[dict[str, object]]
    borescopes: list[dict[str, object]]


def build_service(engines: list[Engine], snapshot: date, rng: random.Random) -> ServiceRecords:
    """Removals and shop visits for every removed engine, borescopes for every engine."""
    removals, visits, reports = [], [], []
    for engine in sorted((e for e in engines if e.removal_date), key=lambda e: e.removal_date):
        removal = _removal(engine, len(removals) + 1)
        removals.append(removal)
        visits.append(_shop_visit(engine, removal, snapshot, len(visits) + 1, rng))
        reports.append(_difficulty_report(engine, removal, len(reports) + 1, rng))
    borescopes: list[dict[str, object]] = []
    for engine in sorted(engines, key=lambda e: e.esn):
        borescopes.extend(_borescopes(engine, snapshot, len(borescopes), rng))
    return ServiceRecords(removals, visits, reports, borescopes)


def _removal(engine: Engine, number: int) -> dict[str, object]:
    cycles = len(engine.report_dates)
    return {
        "removal_id": f"RMV-{engine.removal_date:%Y}-{number:04d}",
        "esn": engine.esn,
        "operator_id": engine.operator_id,
        "tail": engine.tail,
        "position": engine.position,
        "removal_date": engine.removal_date.isoformat(),
        "reason": REMOVAL_REASONS[engine.fault_mode],
        "unscheduled": 1,
        "cycles_since_install": cycles,
        "hours_since_install": round(cycles * FLIGHT_HOURS_PER_CYCLE, 1),
    }


def _shop_visit(engine: Engine, removal: dict[str, object], snapshot: date, number: int,
                rng: random.Random) -> dict[str, object]:
    inducted = engine.removal_date + timedelta(days=rng.randint(3, 20))
    completed = inducted + timedelta(days=rng.randint(40, 90))
    done = completed <= snapshot
    return {
        "shop_visit_id": f"SV-{inducted:%Y}-{number:04d}",
        "esn": engine.esn,
        "removal_id": removal["removal_id"],
        "shop": rng.choice(SHOPS),
        "induction_date": inducted.isoformat(),
        "completion_date": completed.isoformat() if done else None,
        "status": "completed" if done else "in work",
        "workscope": WORKSCOPES[engine.fault_mode],
        "findings": FINDINGS[(engine.fault_mode, engine.story)],
        "parts_replaced": PARTS_REPLACED[engine.fault_mode],
    }


def _difficulty_report(engine: Engine, removal: dict[str, object], number: int,
                       rng: random.Random) -> dict[str, object]:
    part, part_number, condition, location, nature = SDR_PARTS[engine.fault_mode]
    reported = engine.removal_date + timedelta(days=rng.randint(1, 5))
    return {
        "sdr_id": f"SDR-{reported:%Y}-{number:04d}",
        "report_date": reported.isoformat(),
        "submitter_type": "Air carrier",
        "operator_id": engine.operator_id,
        "aircraft_type": AIRCRAFT_TYPE,
        "tail": engine.tail,
        "engine_model": ENGINE_MODEL,
        "esn": engine.esn,
        "part_name": part,
        "part_number": part_number,
        "part_condition": condition,
        "part_location": location,
        "nature_of_condition": nature,
        "precautionary_procedure": "Unscheduled engine removal",
        "problem_description": f"{removal['reason']}. Engine removed for shop visit.",
        "part_cycles_since_new": removal["cycles_since_install"],
    }


def _borescopes(engine: Engine, snapshot: date, offset: int, rng: random.Random) -> list[dict[str, object]]:
    records = []
    n = len(engine.report_dates)
    for cycle in range(BORESCOPE_INTERVAL_CYCLES, n + 1, BORESCOPE_INTERVAL_CYCLES):
        late = engine.status == "removed" and cycle > n - BORESCOPE_INTERVAL_CYCLES
        finding, action = LATE_LIFE_FINDINGS[engine.fault_mode] if late else rng.choice(ROUTINE_FINDINGS)
        records.append(_borescope(engine, cycle, engine.report_dates[cycle - 1], finding, action,
                                  offset + len(records) + 1))
    if engine.status == "active" and engine.story:
        # Operators inspected story engines after the bulletin was issued.
        story = FAN_STORY if engine.story == "fan_lot" else HPC_STORY
        inspected = max(story.bulletin_date + timedelta(days=rng.randint(3, 20)), engine.install_date)
        inspected = min(inspected, snapshot)
        cycle = sum(1 for d in engine.report_dates if d <= inspected)
        finding, action = _story_borescope(engine.story)
        records.append(_borescope(engine, cycle, inspected, finding, action, offset + len(records) + 1))
    return records


def _story_borescope(story: str) -> tuple[str, str]:
    if story == "fan_lot":
        return ("Fan blade root coating loss on 4 blades.",
                f"Repeat inspection every 25 cycles per {FAN_STORY.bulletin_id}; plan removal.")
    return ("HPC stage 4 blisk tip rub.", f"Repeat inspection every 50 cycles per {HPC_STORY.bulletin_id}.")


def _borescope(engine: Engine, cycle: int, when: date, finding: str, action: str,
               number: int) -> dict[str, object]:
    return {
        "borescope_id": f"BSI-{number:05d}",
        "esn": engine.esn,
        "inspection_date": when.isoformat(),
        "cycle": cycle,
        "finding": finding,
        "action": action,
    }

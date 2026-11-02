"""Quality records: build inspections, nonconformance reports, deviations and lot quarantines."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from .production import ProductionRecords
from .reference import INSPECTORS
from .stories import FAN_STORY, HPC_STORY

# What is checked on each module before it joins an engine, with its unit of measure.
CHARACTERISTICS: dict[str, tuple[str, str]] = {
    "FAN": ("Blade root coating thickness", "um"),
    "LPC": ("Blade airfoil profile deviation", "mm"),
    "HPC": ("Rotor stack bolt torque", "N.m"),
    "COMB": ("Liner crack check (fluorescent penetrant)", ""),
    "HPT": ("Blade tip clearance", "mm"),
    "LPT": ("Blade tip clearance", "mm"),
}
FAIL_RATE = 0.03

BENIGN_DEVIATIONS: tuple[dict[str, object], ...] = (
    {"deviation_id": "DEV-2024-012", "module": "LPC", "approved_date": "2024-04-02",
     "valid_to": "2024-05-31", "lot_id": None,
     "description": "Alternate approved sealant used on LPC case flange while primary sealant was back-ordered.",
     "rationale": "Alternate sealant is qualified to the same specification; no effect on form, fit or function.",
     "status": "closed"},
    {"deviation_id": "DEV-2025-019", "module": "COMB", "approved_date": "2025-08-20",
     "valid_to": "2025-10-15", "lot_id": None,
     "description": "Combustor liner part marking applied by laser etch instead of ink stamp.",
     "rationale": "Marking method change only; legibility verified; no structural effect.",
     "status": "closed"},
    {"deviation_id": "DEV-2026-003", "module": "LPT", "approved_date": "2026-02-11",
     "valid_to": "2026-04-30", "lot_id": None,
     "description": "LPT blade sets shipped in reusable crates instead of single-use packaging.",
     "rationale": "Packaging change verified by drop test; parts inspected on receipt.",
     "status": "closed"},
)


@dataclass(frozen=True, slots=True)
class QualityRecords:
    inspections: list[dict[str, object]]
    ncrs: list[dict[str, object]]
    deviations: list[dict[str, object]]
    lot_quarantines: list[dict[str, object]]


def build_quality(production: ProductionRecords, rng: random.Random) -> QualityRecords:
    """Inspect every module build, raise an NCR for every failed inspection, and add the stories."""
    plant_line = {b["esn"]: (b["plant_id"], b["line"]) for b in production.engine_builds}
    inspections: list[dict[str, object]] = []
    ncrs: list[dict[str, object]] = []
    for build in sorted(production.module_builds, key=lambda b: (b["build_date"], b["module_serial"])):
        inspection = _inspection(build, len(inspections) + 1, rng)
        inspections.append(inspection)
        if inspection["result"] == "FAIL":
            ncrs.append(_rework_ncr(inspection, build, plant_line[build["esn"]], len(ncrs) + 1, rng))
            inspections.append(_reinspection(inspection, len(inspections) + 1, rng))
    ncrs.append(_story_ncr(production))
    deviations = [*BENIGN_DEVIATIONS, _story_deviation()]
    quarantines = [_story_quarantine(), _benign_quarantine(production, rng)]
    _mark_quarantined_lots(production, quarantines)
    return QualityRecords(inspections, ncrs, deviations, quarantines)


def _inspection(build: dict[str, object], number: int, rng: random.Random) -> dict[str, object]:
    module = str(build["module"])
    characteristic, unit = CHARACTERISTICS[module]
    built = date.fromisoformat(str(build["build_date"]))
    record = {
        "inspection_id": f"INS-{built:%Y}-{number:05d}",
        "module_serial": build["module_serial"],
        "esn": build["esn"],
        "module": module,
        "station": build["station"],
        "inspection_date": built.isoformat(),
        "characteristic": characteristic,
        "measured_value": _measurement(module, rng),
        "unit": unit,
        "tool_id": None,
        "inspector": rng.choice(INSPECTORS),
        "result": "FAIL" if rng.random() < FAIL_RATE else "PASS",
        "note": None,
    }
    window_start, window_end = HPC_STORY.build_window
    if build["station"] == HPC_STORY.station and window_start <= built <= window_end:
        # The torque reading looked fine; the wrench itself was later found out of calibration.
        record.update(tool_id=HPC_STORY.tool_id, result="PASS")
    if build["lot_id"] == FAN_STORY.lot_id:
        record.update(measured_value=round(rng.uniform(83.0, 86.0), 1), result="ACCEPTED_UNDER_DEVIATION",
                      note=f"Below 92 um minimum; accepted under {FAN_STORY.deviation_id}.")
    return record


def _measurement(module: str, rng: random.Random) -> float | None:
    ranges = {"FAN": (92.0, 108.0), "LPC": (0.00, 0.08), "HPC": (118.0, 126.0),
              "HPT": (0.38, 0.52), "LPT": (0.60, 0.80)}
    if module not in ranges:
        return None
    low, high = ranges[module]
    return round(rng.uniform(low, high), 2)


def _reinspection(failed: dict[str, object], number: int, rng: random.Random) -> dict[str, object]:
    redone = date.fromisoformat(str(failed["inspection_date"])) + timedelta(days=rng.randint(1, 3))
    return {**failed, "inspection_id": f"INS-{redone:%Y}-{number:05d}", "inspection_date": redone.isoformat(),
            "measured_value": _measurement(str(failed["module"]), rng), "result": "PASS",
            "note": "Re-inspection after rework."}


def _rework_ncr(inspection: dict[str, object], build: dict[str, object], plant_line: tuple[str, str],
                number: int, rng: random.Random) -> dict[str, object]:
    opened = date.fromisoformat(str(inspection["inspection_date"]))
    return {
        "ncr_id": f"NCR-{opened:%Y}-{number:04d}",
        "opened_date": opened.isoformat(),
        "closed_date": (opened + timedelta(days=rng.randint(2, 9))).isoformat(),
        "plant_id": plant_line[0],
        "line": plant_line[1],
        "station": inspection["station"],
        "module": inspection["module"],
        "module_serial": inspection["module_serial"],
        "lot_id": build["lot_id"],
        "description": f"{inspection['characteristic']} out of tolerance at {inspection['inspection_id']}.",
        "disposition": "rework",
        "root_cause": rng.choice(["Assembly variation", "Fixture wear", "Operator error",
                                  "Supplier part at tolerance limit"]),
        "status": "closed",
        "affected_from": None,
        "affected_to": None,
    }


def _story_ncr(production: ProductionRecords) -> dict[str, object]:
    start, end = HPC_STORY.build_window
    affected = sorted(b["module_serial"] for b in production.module_builds
                      if b["station"] == HPC_STORY.station
                      and start <= date.fromisoformat(str(b["build_date"])) <= end)
    return {
        "ncr_id": HPC_STORY.ncr_id,
        "opened_date": HPC_STORY.ncr_opened.isoformat(),
        "closed_date": HPC_STORY.ncr_closed.isoformat(),
        "plant_id": HPC_STORY.plant_id,
        "line": HPC_STORY.line,
        "station": HPC_STORY.station,
        "module": "HPC",
        "module_serial": None,
        "lot_id": None,
        "description": (f"Torque wrench {HPC_STORY.tool_id} found 9% under-reading at scheduled calibration. "
                        f"Rotor stack bolt torque on {len(affected)} HPC modules built at "
                        f"{HPC_STORY.station} between {start.isoformat()} and {end.isoformat()} may be below "
                        "specification."),
        "disposition": "use-as-is (MRB): engineering assessed preload margin as acceptable",
        "root_cause": "Calibration interval missed after tool transfer between lines",
        "status": "closed",
        "affected_from": start.isoformat(),
        "affected_to": end.isoformat(),
    }


def _story_deviation() -> dict[str, object]:
    return {
        "deviation_id": FAN_STORY.deviation_id,
        "module": "FAN",
        "approved_date": FAN_STORY.deviation_approved.isoformat(),
        "valid_to": FAN_STORY.build_window[1].isoformat(),
        "lot_id": FAN_STORY.lot_id,
        "description": (f"Fan blade set lot {FAN_STORY.lot_id} accepted with blade root coating thickness "
                        "83 to 86 um against a 92 um minimum."),
        "rationale": "Supplier fatigue analysis showed adequate life; accepted to protect delivery schedule.",
        "status": "closed",
    }


def _story_quarantine() -> dict[str, object]:
    return {
        "quarantine_id": "QTN-2026-004",
        "lot_id": FAN_STORY.lot_id,
        "quarantined_date": FAN_STORY.quarantine_date.isoformat(),
        "released_date": None,
        "reason": "Fan vibration removals in service traced to fan blades from this lot.",
        "status": "open",
    }


def _benign_quarantine(production: ProductionRecords, rng: random.Random) -> dict[str, object]:
    hpc_lots = [lot for lot in production.supplier_lots if lot["module"] == "HPC"]
    lot = rng.choice(hpc_lots)
    held = date.fromisoformat(str(lot["received_date"])) + timedelta(days=2)
    return {
        "quarantine_id": f"QTN-{held:%Y}-001",
        "lot_id": lot["lot_id"],
        "quarantined_date": held.isoformat(),
        "released_date": (held + timedelta(days=6)).isoformat(),
        "reason": "Supplier certificate of conformance missing a heat-treat record.",
        "status": "released",
    }


def _mark_quarantined_lots(production: ProductionRecords, quarantines: list[dict[str, object]]) -> None:
    held = {q["lot_id"] for q in quarantines if q["status"] == "open"}
    for lot in production.supplier_lots:
        if lot["lot_id"] in held:
            lot["status"] = "quarantined"

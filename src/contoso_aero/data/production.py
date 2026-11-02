"""Factory build records: engine builds, module builds and the supplier lots they consumed."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, timedelta

from .fleet import Engine
from .reference import ENGINE_MODEL, MODULE_TYPES, MODULES_BY_ID
from .stories import FAN_STORY, HPC_STORY

# Engines that share one supplier lot of a key part.
LOT_SIZE = (6, 10)
# Days a module is built before the engine passes off test.
MODULE_LEAD_DAYS = (3, 12)
# Non-story engines built in the fan story window that also used the deviated lot but did not
# fail by fan wear, so the lot does not look like a perfect predictor of failure.
EXTRA_FAN_LOT_ENGINES = 2


@dataclass(frozen=True, slots=True)
class ProductionRecords:
    engine_builds: list[dict[str, object]]
    module_builds: list[dict[str, object]]
    supplier_lots: list[dict[str, object]]


def build_production(engines: list[Engine], rng: random.Random) -> ProductionRecords:
    """Create one build per engine, six module builds per engine, and lots shared across engines."""
    engine_builds = [{
        "esn": e.esn,
        "engine_model": ENGINE_MODEL,
        "plant_id": e.plant_id,
        "line": e.line,
        "build_start": (e.build_date - timedelta(days=rng.randint(8, 16))).isoformat(),
        "pass_off_date": e.build_date.isoformat(),
        "pass_off_egt_margin_c": round(rng.uniform(38.0, 52.0), 1),
    } for e in engines]

    module_builds: list[dict[str, object]] = []
    for e in engines:
        for module in MODULE_TYPES:
            built = e.build_date - timedelta(days=rng.randint(*MODULE_LEAD_DAYS))
            if e.story == "hpc_station" and module.module == "HPC":
                # The story is defined by when the HPC module was stacked, so keep it in the window.
                built = max(built, HPC_STORY.build_window[0])
            module_builds.append({
                "module_serial": f"{module.module}-{e.esn[4:]}",
                "esn": e.esn,
                "module": module.module,
                "station": _station(e, module.module, rng),
                "build_date": built.isoformat(),
                "key_part": module.key_part,
                "part_number": module.part_number,
                "lot_id": "",
            })

    lots = _assign_lots(engines, module_builds, rng)
    return ProductionRecords(engine_builds, module_builds, lots)


def _station(engine: Engine, module: str, rng: random.Random) -> str:
    stations = MODULES_BY_ID[module].stations
    if module != "HPC":
        return rng.choice(stations)
    # HPC-04 is Riverside line 2's rotor-stacking station; other lines use HPC-02 or HPC-03.
    if (engine.plant_id, engine.line) == (HPC_STORY.plant_id, HPC_STORY.line):
        return HPC_STORY.station
    return rng.choice([s for s in stations if s != HPC_STORY.station])


def _assign_lots(engines: list[Engine], module_builds: list[dict[str, object]],
                 rng: random.Random) -> list[dict[str, object]]:
    """Group module builds into lots in build order; the fan story lot is pinned first."""
    story_esns = {e.esn for e in engines if e.story == "fan_lot"}
    start, end = FAN_STORY.build_window
    in_window = sorted((e for e in engines if not e.story and start <= e.build_date <= end),
                       key=lambda e: e.build_date)
    fan_lot_esns = story_esns | {e.esn for e in in_window[:EXTRA_FAN_LOT_ENGINES]}

    lots: list[dict[str, object]] = []
    for module in MODULE_TYPES:
        builds = sorted((b for b in module_builds if b["module"] == module.module),
                        key=lambda b: (b["build_date"], b["esn"]))
        if module.module == "FAN":
            pinned = [b for b in builds if b["esn"] in fan_lot_esns]
            for b in pinned:
                b["lot_id"] = FAN_STORY.lot_id
            lots.append(_lot_record(FAN_STORY.lot_id, module.module, pinned, rng))
            builds = [b for b in builds if b["esn"] not in fan_lot_esns]
        sequence = 0
        while builds:
            size = rng.randint(*LOT_SIZE)
            chunk, builds = builds[:size], builds[size:]
            sequence += 1
            first = date.fromisoformat(str(chunk[0]["build_date"]))
            lot_id = f"{module.lot_prefix}-{first:%y%m}-{100 + sequence:03d}"
            for b in chunk:
                b["lot_id"] = lot_id
            lots.append(_lot_record(lot_id, module.module, chunk, rng))
    return lots


def _lot_record(lot_id: str, module_id: str, builds: list[dict[str, object]],
                rng: random.Random) -> dict[str, object]:
    module = MODULES_BY_ID[module_id]
    dates = sorted(date.fromisoformat(str(b["build_date"])) for b in builds)
    return {
        "lot_id": lot_id,
        "module": module_id,
        "key_part": module.key_part,
        "part_number": module.part_number,
        "supplier": module.supplier,
        "received_date": (dates[0] - timedelta(days=rng.randint(10, 30))).isoformat(),
        "first_used": dates[0].isoformat(),
        "last_used": dates[-1].isoformat(),
        "engines_built": len(builds),
        "status": "consumed",
    }

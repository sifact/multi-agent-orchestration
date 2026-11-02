"""Run every generation step in order and write the dataset's outputs."""

from __future__ import annotations

import random
from dataclasses import dataclass

from ..config import DataSettings
from .cmapss import infer_fault_mode, load_subset
from .database import write_csvs, write_database
from .fleet import Engine, build_fleet
from .knowledge import build_documents, write_documents
from .production import build_production
from .quality import build_quality
from .reference import ENGINE_MODEL, OPERATORS
from .service import build_service
from .stories import assign_stories
from .telemetry import build_telemetry


@dataclass(frozen=True, slots=True)
class BuildSummary:
    table_rows: dict[str, int]
    documents: int


def build_dataset(settings: DataSettings | None = None) -> BuildSummary:
    """Build the whole dataset from the raw C-MAPSS files and one seed.

    One seeded generator is threaded through the steps in a fixed order, so the same inputs
    always give byte-identical tables, and the evaluation answers stay valid.
    """
    settings = settings or DataSettings()
    rng = random.Random(settings.seed)
    runs = load_subset(settings.raw_dir, settings.subset)
    fault_modes = {run.key: infer_fault_mode(run) for run in runs}
    stories = assign_stories(runs, fault_modes)
    engines, aircraft = build_fleet(runs, fault_modes, stories, settings.snapshot_date, rng)
    production = build_production(engines, rng)
    quality = build_quality(production, rng)
    service = build_service(engines, settings.snapshot_date, rng)

    tables = {
        "operators": [{"operator_id": o.operator_id, "name": o.name} for o in OPERATORS],
        "aircraft": [{"tail": a.tail, "operator_id": a.operator_id} for a in aircraft],
        "engines": [_engine_row(e) for e in sorted(engines, key=lambda e: e.esn)],
        "engine_telemetry": build_telemetry(engines),
        "engine_builds": production.engine_builds,
        "module_builds": production.module_builds,
        "supplier_lots": production.supplier_lots,
        "inspections": quality.inspections,
        "ncrs": quality.ncrs,
        "deviations": quality.deviations,
        "lot_quarantines": quality.lot_quarantines,
        "removals": service.removals,
        "shop_visits": service.shop_visits,
        "difficulty_reports": service.difficulty_reports,
        "borescope_inspections": service.borescopes,
        "ground_truth": [_truth_row(e, settings.subset) for e in sorted(engines, key=lambda e: e.esn)],
    }
    write_database(tables, settings.database_path)
    write_csvs(tables, settings.csv_dir)
    documents = build_documents()
    write_documents(documents, settings.knowledge_dir)
    return BuildSummary({name: len(rows) for name, rows in tables.items()}, len(documents))


def _engine_row(engine: Engine) -> dict[str, object]:
    return {
        "esn": engine.esn,
        "engine_model": ENGINE_MODEL,
        "status": engine.status,
        "operator_id": engine.operator_id,
        "tail": engine.tail,
        "position": engine.position,
        "install_date": engine.install_date.isoformat(),
        "last_report_date": engine.last_report_date.isoformat(),
        "removal_date": engine.removal_date.isoformat() if engine.removal_date else None,
        "cycles_since_install": len(engine.report_dates),
    }


def _truth_row(engine: Engine, subset: str) -> dict[str, object]:
    # Hidden answers for scoring only: agents must never read this table.
    return {
        "esn": engine.esn,
        "cmapss_subset": subset,
        "cmapss_split": engine.run.split,
        "cmapss_unit": engine.run.unit,
        "true_rul_cycles": engine.run.true_rul,
        "inferred_fault_mode": engine.fault_mode,
        "story": engine.story,
    }

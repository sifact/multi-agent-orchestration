"""End-to-end checks on the generated dataset. Skipped when the NASA files are not present."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import replace
from itertools import pairwise
from pathlib import Path

import pytest

from contoso_aero.config import DataSettings
from contoso_aero.data import TABLE_OWNERS, build_dataset
from contoso_aero.data.cmapss import KEPT_SENSORS, load_subset
from contoso_aero.data.stories import FAN_STORY, HPC_STORY
from contoso_aero.evaluation import build_questions, write_questions

RAW = DataSettings().raw_dir
pytestmark = pytest.mark.skipif(not (RAW / "train_FD003.txt").exists(),
                                reason="NASA C-MAPSS files not downloaded (see data/SOURCES.md)")


def _settings(root: Path) -> DataSettings:
    return replace(DataSettings(), generated_dir=root / "generated", knowledge_dir=root / "knowledge",
                   eval_path=root / "eval" / "questions.jsonl")


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> DataSettings:
    settings = _settings(tmp_path_factory.mktemp("build"))
    build_dataset(settings)
    write_questions(build_questions(settings.database_path, settings.snapshot_date, settings.seed),
                    settings.eval_path)
    return settings


@pytest.fixture(scope="module")
def db(built: DataSettings) -> sqlite3.Connection:
    connection = sqlite3.connect(built.database_path)
    yield connection
    connection.close()


def _dump(path: Path) -> list[str]:
    with sqlite3.connect(path) as connection:
        return list(connection.iterdump())


def test_given_same_seed_when_built_twice_then_tables_are_identical(
        built: DataSettings, tmp_path: Path) -> None:
    again = _settings(tmp_path)
    build_dataset(again)
    assert _dump(again.database_path) == _dump(built.database_path)


def test_given_built_tables_when_esns_checked_then_every_child_row_has_an_engine(db: sqlite3.Connection) -> None:
    engines = {r[0] for r in db.execute("SELECT esn FROM engines")}
    assert len(engines) == 200
    for table in ("engine_telemetry", "engine_builds", "module_builds", "inspections", "removals",
                  "shop_visits", "difficulty_reports", "borescope_inspections", "ground_truth"):
        orphans = {r[0] for r in db.execute(f"SELECT DISTINCT esn FROM {table}")} - engines
        assert not orphans, table


def test_given_aircraft_positions_when_installs_compared_then_no_position_holds_two_engines(
        db: sqlite3.Connection) -> None:
    rows = db.execute("SELECT tail, position, install_date, coalesce(removal_date, last_report_date) "
                      "FROM engines ORDER BY tail, position, install_date").fetchall()
    for before, after in pairwise(rows):
        if before[:2] == after[:2]:
            assert before[3] < after[2]


def test_given_raw_cmapss_when_telemetry_compared_then_readings_are_unchanged(
        db: sqlite3.Connection) -> None:
    runs = {r.key: r for r in load_subset(RAW, "FD003")}
    for esn, split, unit in db.execute("SELECT esn, cmapss_split, cmapss_unit FROM ground_truth LIMIT 20"):
        stored = db.execute(f"SELECT {', '.join(KEPT_SENSORS)} FROM engine_telemetry WHERE esn=? ORDER BY cycle",
                            (esn,)).fetchall()
        original = [tuple(c.sensors[s] for s in KEPT_SENSORS) for c in runs[(split, unit)].cycles]
        assert stored == original


def test_given_fan_story_when_traced_then_lot_deviation_quarantine_and_removals_agree(
        db: sqlite3.Connection) -> None:
    story = {r[0] for r in db.execute("SELECT esn FROM ground_truth WHERE story='fan_lot'")}
    lot = {r[0] for r in db.execute("SELECT esn FROM module_builds WHERE lot_id=?", (FAN_STORY.lot_id,))}
    assert story <= lot
    assert db.execute("SELECT status FROM supplier_lots WHERE lot_id=?", (FAN_STORY.lot_id,)).fetchone() == \
        ("quarantined",)
    last_removal = db.execute(f"SELECT max(removal_date) FROM removals WHERE esn IN ({','.join('?' * len(story))})",
                              tuple(story)).fetchone()[0]
    assert last_removal < FAN_STORY.quarantine_date.isoformat()


def test_given_hpc_story_when_traced_then_every_story_engine_is_in_the_ncr_window(db: sqlite3.Connection) -> None:
    start, end = (d.isoformat() for d in HPC_STORY.build_window)
    window = {r[0] for r in db.execute("SELECT esn FROM module_builds WHERE station=? AND module='HPC' AND "
                                       "build_date BETWEEN ? AND ?", (HPC_STORY.station, start, end))}
    story = {r[0] for r in db.execute("SELECT esn FROM ground_truth WHERE story='hpc_station'")}
    assert story <= window


def test_given_table_owners_when_listed_then_ground_truth_belongs_to_no_agent() -> None:
    agent_tables = {t for owner, tables in TABLE_OWNERS.items() if owner != "evaluation_only" for t in tables}
    assert "ground_truth" not in agent_tables


def test_given_questions_when_read_then_mix_and_entities_are_valid(built: DataSettings,
                                                                   db: sqlite3.Connection) -> None:
    questions = [json.loads(line) for line in built.eval_path.read_text().splitlines()]
    categories = [q["category"] for q in questions]
    assert categories.count("single") >= 20 and categories.count("multi") >= 20
    assert categories.count("unsupported") >= 10
    engines = {r[0] for r in db.execute("SELECT esn FROM engines")}
    for q in questions:
        assert (q["expected_agents"] == []) == (q["category"] == "unsupported")
        assert (len(q["expected_agents"]) > 1) == (q["category"] == "multi")
        for fact in q["expected_facts"]:
            if fact.startswith("CX7-"):
                assert fact in engines

"""Write the generated tables to one SQLite file and mirror them as CSV for easy browsing."""

from __future__ import annotations

import csv
import sqlite3
from collections.abc import Mapping, Sequence
from pathlib import Path

Rows = Sequence[Mapping[str, object]]

# Which agent module owns which tables. Each agent may query only its own tables; this is the
# boundary that lets project 2 split agents into separate services without moving data around.
TABLE_OWNERS: dict[str, tuple[str, ...]] = {
    "telemetry": ("operators", "aircraft", "engines", "engine_telemetry"),
    "service": ("removals", "shop_visits", "difficulty_reports", "borescope_inspections"),
    "production": ("engine_builds", "module_builds", "supplier_lots"),
    "quality": ("inspections", "ncrs", "deviations", "lot_quarantines"),
    "evaluation_only": ("ground_truth",),
}
PRIMARY_KEYS: dict[str, tuple[str, ...]] = {"engine_telemetry": ("esn", "cycle")}


def write_database(tables: Mapping[str, Rows], path: Path) -> None:
    """Rebuild the SQLite file from scratch so a rerun never mixes old and new rows."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.unlink(missing_ok=True)
    with sqlite3.connect(temporary) as connection:
        for name, rows in tables.items():
            _create_table(connection, name, rows)
    temporary.replace(path)


def write_csvs(tables: Mapping[str, Rows], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, rows in tables.items():
        with (directory / f"{name}.csv").open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def _create_table(connection: sqlite3.Connection, name: str, rows: Rows) -> None:
    if not rows:
        raise ValueError(f"table {name} has no rows")
    columns = list(rows[0])
    key = PRIMARY_KEYS.get(name, (columns[0],))
    definitions = [f'"{c}" {_sql_type(rows, c)}' for c in columns]
    definitions.append(f"PRIMARY KEY ({', '.join(key)})")
    connection.execute(f'CREATE TABLE "{name}" ({", ".join(definitions)})')
    placeholders = ", ".join("?" for _ in columns)
    connection.executemany(f'INSERT INTO "{name}" VALUES ({placeholders})',
                           ([row[c] for c in columns] for row in rows))
    if "esn" in columns and key != ("esn",):
        connection.execute(f'CREATE INDEX "idx_{name}_esn" ON "{name}" (esn)')


def _sql_type(rows: Rows, column: str) -> str:
    # The first non-null value decides, so a leading NULL does not turn numbers into text.
    value = next((row[column] for row in rows if row[column] is not None), "")
    if isinstance(value, bool | int):
        return "INTEGER"
    if isinstance(value, float):
        return "REAL"
    return "TEXT"

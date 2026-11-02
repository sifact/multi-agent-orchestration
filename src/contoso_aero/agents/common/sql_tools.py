"""Read-only SQL tool that confines an agent to the tables it owns."""

from __future__ import annotations

import sqlite3
import time
from collections.abc import Sequence
from pathlib import Path

from .types import Tool

MAX_ROWS = 40
MAX_CELL_CHARS = 240
QUERY_SECONDS = 5.0

_ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_FUNCTION, sqlite3.SQLITE_RECURSIVE}
_SCHEMA_TABLES = {"sqlite_master", "sqlite_schema", "sqlite_temp_master", "sqlite_temp_schema",
                  "sqlite_sequence"}


def schema_text(database_path: Path, tables: Sequence[str]) -> str:
    """Describe the owned tables so the model writes SQL against real column names."""
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    try:
        lines = []
        for table in tables:
            columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            lines.append(f"{table}({', '.join(f'{c[1]} {c[2]}' for c in columns)})")
    finally:
        connection.close()
    return "\n".join(lines)


def sql_tool(database_path: Path, tables: Sequence[str]) -> Tool:
    """Build a `query_sql` tool limited to SELECT statements over `tables`."""

    def run(arguments: dict[str, object]) -> str:
        sql = arguments.get("sql")
        if not isinstance(sql, str) or not sql.strip():
            return "Error: provide a SQL SELECT statement in 'sql'."
        return run_query(database_path, tables, sql)

    return Tool(
        name="query_sql",
        description=f"Run one read-only SQLite SELECT over these tables only: {', '.join(tables)}. "
                    f"At most {MAX_ROWS} rows are returned, so aggregate or filter in SQL.",
        parameters={"type": "object", "required": ["sql"],
                    "properties": {"sql": {"type": "string", "description": "One SELECT statement."}}},
        run=run)


def run_query(database_path: Path, tables: Sequence[str], sql: str) -> str:
    """Execute `sql` and format the rows; errors come back as text so the model can retry."""
    deadline = time.monotonic() + QUERY_SECONDS
    connection = _connect(database_path, tables)
    try:
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
        cursor = connection.execute(sql)
        columns = [d[0] for d in cursor.description or []]
        rows = cursor.fetchmany(MAX_ROWS + 1)
    except sqlite3.Error as error:
        return f"Error: {error}"
    finally:
        connection.close()
    lines = [" | ".join(columns)]
    lines += [" | ".join(_cell(value) for value in row) for row in rows[:MAX_ROWS]]
    if len(rows) > MAX_ROWS:
        lines.append(f"... truncated to {MAX_ROWS} rows; narrow the query.")
    elif not rows:
        lines.append("(no rows)")
    return "\n".join(lines)


def _connect(database_path: Path, tables: Sequence[str]) -> sqlite3.Connection:
    """Open the database read-only and deny any table the agent does not own."""
    connection = sqlite3.connect(f"file:{database_path}?mode=ro", uri=True)
    allowed = {table.casefold() for table in tables}
    # SQLite also checks reads of materialized CTEs and subqueries by their alias. An alias that
    # is not a real schema object only exposes data whose own table reads were already checked,
    # so it is allowed; a real name the agent does not own (or a schema table) is always denied.
    real = {row[0].casefold() for row in connection.execute("SELECT name FROM sqlite_master")}
    real |= _SCHEMA_TABLES

    def authorize(action: int, arg1: str | None, *_: object) -> int:
        if action in _ALLOWED_ACTIONS:
            return sqlite3.SQLITE_OK
        if action == sqlite3.SQLITE_READ and arg1 is not None:
            name = arg1.casefold()
            if name in allowed or name not in real:
                return sqlite3.SQLITE_OK
        return sqlite3.SQLITE_DENY

    connection.set_authorizer(authorize)
    return connection


def _cell(value: object) -> str:
    text = "" if value is None else str(value)
    return text if len(text) <= MAX_CELL_CHARS else text[:MAX_CELL_CHARS] + "..."

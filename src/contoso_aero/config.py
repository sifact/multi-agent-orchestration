"""Paths, seed and fixed dates shared by every pipeline stage."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class DataSettings:
    """Where dataset inputs and outputs live, and what makes a build reproducible.

    The snapshot date is fixed rather than "today" so that every rebuild produces
    identical dates, and the evaluation answers never drift.
    """

    raw_dir: Path = PROJECT_ROOT / "data" / "raw" / "cmapss"
    generated_dir: Path = PROJECT_ROOT / "data" / "generated"
    knowledge_dir: Path = PROJECT_ROOT / "data" / "knowledge"
    eval_path: Path = PROJECT_ROOT / "data" / "eval" / "questions.jsonl"
    probe_path: Path = PROJECT_ROOT / "data" / "eval" / "routing_probe.jsonl"
    coordination_probe_path: Path = PROJECT_ROOT / "data" / "eval" / "coordination_probe.jsonl"
    subset: str = "FD003"
    seed: int = 20260612
    snapshot_date: date = date(2026, 10, 29)

    @property
    def database_path(self) -> Path:
        return self.generated_dir / "contoso_aero.sqlite3"

    @property
    def csv_dir(self) -> Path:
        return self.generated_dir / "csv"


class SettingsError(Exception):
    """Raised when model connection settings are missing."""


@dataclass(frozen=True, slots=True)
class ModelSettings:
    """Connection settings for the OpenAI-compatible endpoint shared with nl-to-sql.

    The variable names match nl-to-sql so one set of values works for both projects.
    The key is hidden from repr so it never reaches logs or tracebacks.
    """

    base_url: str = ""
    api_key: str = field(default="", repr=False)
    model_name: str = ""
    timeout_seconds: float = 60.0
    max_agent_steps: int = 6

    @property
    def completion_url(self) -> str:
        return f"{self.base_url.rstrip('/')}/chat/completions"

    def require_complete(self) -> None:
        missing = [name for name, value in (("NL_SQL_BASE_URL", self.base_url),
                                            ("NL_SQL_API_KEY", self.api_key),
                                            ("NL_SQL_MODEL", self.model_name)) if not value]
        if missing:
            raise SettingsError(f"Set {', '.join(missing)} in .env or the environment.")


def load_model_settings(env_path: Path | None = None) -> ModelSettings:
    """Read model settings from this project's .env, letting real environment variables win."""
    values = _read_env_file(PROJECT_ROOT / ".env" if env_path is None else env_path)
    values.update({k: v for k, v in os.environ.items() if k.startswith("NL_SQL_")})
    try:
        timeout = float(values.get("NL_SQL_MODEL_TIMEOUT_SECONDS") or 60.0)
    except ValueError:
        raise SettingsError("NL_SQL_MODEL_TIMEOUT_SECONDS must be a number.") from None
    return ModelSettings(base_url=values.get("NL_SQL_BASE_URL", "").strip(),
                         api_key=values.get("NL_SQL_API_KEY", "").strip(),
                         model_name=values.get("NL_SQL_MODEL", "").strip(),
                         timeout_seconds=timeout)


def _read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip("\"'")
    return values

"""Engine condition reports: one dated row per C-MAPSS cycle, keyed by Contoso serial number."""

from __future__ import annotations

from .cmapss import KEPT_SENSORS
from .fleet import Engine


def build_telemetry(engines: list[Engine]) -> list[dict[str, object]]:
    """Copy the real C-MAPSS readings unchanged and attach the engine's report dates.

    Readings are not altered: the telemetry is the one part of the dataset that is real data.
    """
    rows: list[dict[str, object]] = []
    for engine in sorted(engines, key=lambda e: e.esn):
        for cycle, report_date in zip(engine.run.cycles, engine.report_dates):
            row: dict[str, object] = {
                "esn": engine.esn,
                "cycle": cycle.cycle,
                "report_date": report_date.isoformat(),
                "setting_1": cycle.settings[0],
                "setting_2": cycle.settings[1],
                "setting_3": cycle.settings[2],
            }
            row.update({name: cycle.sensors[name] for name in KEPT_SENSORS})
            rows.append(row)
    return rows

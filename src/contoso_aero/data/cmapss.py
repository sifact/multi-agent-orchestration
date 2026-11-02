"""Load NASA C-MAPSS run-to-failure data and label each engine's likely fault mode."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from statistics import mean

# Names, descriptions and units from Table 2 of Saxena et al. (2008), in file column order.
SENSORS: tuple[tuple[str, str, str], ...] = (
    ("T2", "Total temperature at fan inlet", "degR"),
    ("T24", "Total temperature at LPC outlet", "degR"),
    ("T30", "Total temperature at HPC outlet", "degR"),
    ("T50", "Total temperature at LPT outlet", "degR"),
    ("P2", "Pressure at fan inlet", "psia"),
    ("P15", "Total pressure in bypass duct", "psia"),
    ("P30", "Total pressure at HPC outlet", "psia"),
    ("Nf", "Physical fan speed", "rpm"),
    ("Nc", "Physical core speed", "rpm"),
    ("epr", "Engine pressure ratio (P50/P2)", ""),
    ("Ps30", "Static pressure at HPC outlet", "psia"),
    ("phi", "Ratio of fuel flow to Ps30", "pps/psi"),
    ("NRf", "Corrected fan speed", "rpm"),
    ("NRc", "Corrected core speed", "rpm"),
    ("BPR", "Bypass ratio", ""),
    ("farB", "Burner fuel-air ratio", ""),
    ("htBleed", "Bleed enthalpy", ""),
    ("Nf_dmd", "Demanded fan speed", "rpm"),
    ("PCNfR_dmd", "Demanded corrected fan speed", "rpm"),
    ("W31", "HPT coolant bleed", "lbm/s"),
    ("W32", "LPT coolant bleed", "lbm/s"),
)
# Flat in FD003 (standard deviation 0), so they carry no health signal and are not stored.
CONSTANT_SENSORS = frozenset({"T2", "P2", "farB", "Nf_dmd", "PCNfR_dmd"})
KEPT_SENSORS: tuple[str, ...] = tuple(name for name, _, _ in SENSORS if name not in CONSTANT_SENSORS)

# P30 falls as the HPC degrades (it does in all 100 FD001 engines, which have HPC faults only)
# and rises with fan degradation, so its trend separates FD003's two fault modes.
FAULT_SIGNAL = "P30"
# Trend strength, in noise-standard-errors, needed before a short test series is labelled.
MIN_TREND_T_STAT = 3.0


@dataclass(frozen=True, slots=True)
class Cycle:
    """One row of C-MAPSS: an engine's operating settings and sensor readings for one cycle."""

    cycle: int
    settings: tuple[float, float, float]
    sensors: dict[str, float]


@dataclass(frozen=True, slots=True)
class EngineRun:
    """One C-MAPSS engine: a train run ends at failure, a test run stops before it."""

    split: str
    unit: int
    cycles: tuple[Cycle, ...]
    true_rul: int | None

    @property
    def key(self) -> tuple[str, int]:
        return (self.split, self.unit)


def load_subset(raw_dir: Path, subset: str) -> list[EngineRun]:
    """Read the train and test files of one subset, attaching NASA's true RUL to test runs."""
    runs: list[EngineRun] = []
    for split in ("train", "test"):
        rows = _read_rows(raw_dir / f"{split}_{subset}.txt")
        ruls = _read_ruls(raw_dir / f"RUL_{subset}.txt") if split == "test" else {}
        for unit in sorted(rows):
            runs.append(EngineRun(split, unit, tuple(rows[unit]), ruls.get(unit)))
    return runs


def infer_fault_mode(run: EngineRun) -> str:
    """Return "hpc", "fan" or "unknown" from the direction of the P30 trend.

    Train runs reach failure, so comparing the first and last ten cycles is decisive.
    Test runs can be short and noisy, so a regression slope must clear a t-statistic first.
    """
    values = [c.sensors[FAULT_SIGNAL] for c in run.cycles]
    if run.split == "train":
        return "hpc" if mean(values[-10:]) < mean(values[:10]) else "fan"
    slope, t_stat = _slope_and_t(values)
    if abs(t_stat) < MIN_TREND_T_STAT:
        return "unknown"
    return "hpc" if slope < 0 else "fan"


def _read_rows(path: Path) -> dict[int, list[Cycle]]:
    rows: dict[int, list[Cycle]] = {}
    for line in path.read_text().splitlines():
        values = line.split()
        if not values:
            continue
        unit, cycle = int(values[0]), int(values[1])
        settings = (float(values[2]), float(values[3]), float(values[4]))
        readings = [float(v) for v in values[5:]]
        sensors = {name: readings[i] for i, (name, _, _) in enumerate(SENSORS)}
        rows.setdefault(unit, []).append(Cycle(cycle, settings, sensors))
    return rows


def _read_ruls(path: Path) -> dict[int, int]:
    values = [int(v) for v in path.read_text().split()]
    return {unit: rul for unit, rul in enumerate(values, start=1)}


def _slope_and_t(values: list[float]) -> tuple[float, float]:
    n = len(values)
    if n < 10:
        return 0.0, 0.0
    xs = range(n)
    x_bar, y_bar = (n - 1) / 2, mean(values)
    sxx = sum((x - x_bar) ** 2 for x in xs)
    slope = sum((x - x_bar) * (y - y_bar) for x, y in zip(xs, values)) / sxx
    residual = sum((y - y_bar - slope * (x - x_bar)) ** 2 for x, y in zip(xs, values))
    std_err = (residual / (n - 2) / sxx) ** 0.5
    return slope, (slope / std_err if std_err else 0.0)

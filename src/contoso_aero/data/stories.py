"""The two planted factory-to-fleet stories and the engines chosen to carry them.

The stories give the evaluation questions known answers that need several agents:
a fleet symptom (telemetry, service) traces back to a factory cause (production, quality).
Engines are chosen from real C-MAPSS outcomes, then factory history is written to fit them.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .cmapss import EngineRun


@dataclass(frozen=True, slots=True)
class FanLotStory:
    """A fan blade lot accepted under a coating deviation, later linked to fan-wear removals."""

    lot_id: str = "FBL-2501-117"
    deviation_id: str = "DEV-2025-007"
    build_window: tuple[date, date] = (date(2025, 1, 13), date(2025, 3, 21))
    deviation_approved: date = date(2025, 1, 9)
    quarantine_date: date = date(2026, 9, 22)
    bulletin_id: str = "SB-CX7-72-0042"
    bulletin_date: date = date(2026, 10, 1)
    removed_count: int = 6
    active_count: int = 4


@dataclass(frozen=True, slots=True)
class HpcStationStory:
    """An out-of-calibration torque wrench at one HPC station, later linked to HPC-wear removals."""

    plant_id: str = "P2"
    line: str = "L2"
    station: str = "HPC-04"
    tool_id: str = "TW-118"
    build_window: tuple[date, date] = (date(2025, 6, 2), date(2025, 7, 18))
    ncr_id: str = "NCR-2025-0388"
    ncr_opened: date = date(2025, 7, 18)
    ncr_closed: date = date(2025, 8, 5)
    bulletin_id: str = "SB-CX7-72-0051"
    bulletin_date: date = date(2026, 8, 14)
    removed_count: int = 5
    active_count: int = 4


FAN_STORY = FanLotStory()
HPC_STORY = HpcStationStory()

# Active engines need enough observed cycles for their install date to reach back to the
# story's build window without implausibly sparse condition reports.
MIN_ACTIVE_STORY_CYCLES = 150


@dataclass(frozen=True, slots=True)
class StoryAssignment:
    """Which C-MAPSS engines carry each story, keyed by (split, unit)."""

    fan_lot: frozenset[tuple[str, int]]
    hpc_station: frozenset[tuple[str, int]]

    def story_for(self, key: tuple[str, int]) -> str | None:
        if key in self.fan_lot:
            return "fan_lot"
        if key in self.hpc_station:
            return "hpc_station"
        return None


def assign_stories(runs: list[EngineRun], fault_modes: dict[tuple[str, int], str]) -> StoryAssignment:
    """Pick the engines whose real outcomes fit each story best.

    Removed engines: the shortest-lived in the matching fault mode.
    Active engines: the lowest true remaining life in the matching fault mode, so the story
    is visible in the live fleet too.
    """
    fan = _pick(runs, fault_modes, "fan", FAN_STORY.removed_count, FAN_STORY.active_count)
    hpc = _pick(runs, fault_modes, "hpc", HPC_STORY.removed_count, HPC_STORY.active_count)
    return StoryAssignment(frozenset(fan), frozenset(hpc))


def _pick(runs: list[EngineRun], fault_modes: dict[tuple[str, int], str], mode: str,
          removed: int, active: int) -> list[tuple[str, int]]:
    matching = [r for r in runs if fault_modes[r.key] == mode]
    trains = sorted((r for r in matching if r.split == "train"), key=lambda r: len(r.cycles))
    tests = sorted(
        (r for r in matching if r.split == "test" and len(r.cycles) >= MIN_ACTIVE_STORY_CYCLES),
        key=lambda r: r.true_rul or 0,
    )
    return [r.key for r in trains[:removed]] + [r.key for r in tests[:active]]

"""Turn C-MAPSS runs into a Contoso fleet: serials, dates, plants and aircraft positions."""

from __future__ import annotations

import heapq
import random
from dataclasses import dataclass
from datetime import date, timedelta

from .cmapss import EngineRun
from .reference import OPERATORS, PLANTS
from .stories import FAN_STORY, HPC_STORY, StoryAssignment

# Days between factory pass-off and first flight on wing.
INSTALL_DELAY_DAYS = (25, 75)
# Days between consecutive condition reports (one report per C-MAPSS cycle).
REPORT_SPACING_DAYS = (0.6, 2.5)
# Story engines may report more sparsely, because their build dates are pinned to a window.
MAX_STORY_SPACING_DAYS = 6.0
# Days a position stands empty (spare engine fitted) between one engine's removal and the next install.
POSITION_GAP_DAYS = (4, 45)
# Removed engines must leave the fleet this long before the snapshot.
REMOVAL_MARGIN_DAYS = 20
ESN_START = 10001

Slot = tuple[str, int]  # (tail, position)


@dataclass(slots=True)
class Engine:
    """One Contoso CX-7 engine, linked to the C-MAPSS run that supplies its telemetry."""

    run: EngineRun
    fault_mode: str
    story: str | None
    status: str
    plant_id: str
    line: str
    build_date: date
    install_date: date
    report_dates: list[date]
    removal_date: date | None
    esn: str = ""
    operator_id: str = ""
    tail: str = ""
    position: int = 0

    @property
    def last_report_date(self) -> date:
        return self.report_dates[-1]


@dataclass(frozen=True, slots=True)
class Aircraft:
    tail: str
    operator_id: str


def build_fleet(runs: list[EngineRun], fault_modes: dict[tuple[str, int], str],
                stories: StoryAssignment, snapshot: date,
                rng: random.Random) -> tuple[list[Engine], list[Aircraft]]:
    """Give every engine a timeline that fits one aircraft position, then number them by build date.

    Active engines hold today's positions. Each position's history is then filled backwards:
    a removed engine leaves the wing shortly before the next engine in that slot was installed.
    Story engines are placed first because their build windows are fixed.
    """
    aircraft = [Aircraft(f"{op.tail_prefix}-{101 + i}", op.operator_id)
                for op in OPERATORS for i in range(op.aircraft_count)]
    operator_of = {a.tail: a.operator_id for a in aircraft}
    slots: list[Slot] = [(a.tail, p) for a in aircraft for p in (1, 2)]
    rng.shuffle(slots)

    active = [r for r in runs if r.split == "test"]
    if len(active) != len(slots):
        raise ValueError(f"{len(active)} active engines for {len(slots)} positions")
    engines: list[Engine] = []
    free_until: dict[Slot, date] = {}
    for run, slot in zip(active, slots):
        engine = _active_engine(run, fault_modes[run.key], stories.story_for(run.key), snapshot, rng)
        _place(engine, slot, operator_of)
        engines.append(engine)
        free_until[slot] = min(engine.install_date - _gap(rng),
                               snapshot - timedelta(days=REMOVAL_MARGIN_DAYS))

    removed = [r for r in runs if r.split == "train"]
    for run in (r for r in removed if stories.story_for(r.key)):
        engine = _story_removed_engine(run, fault_modes[run.key], stories.story_for(run.key), rng)
        fitting = [s for s in slots if engine.removal_date < free_until[s]]
        if not fitting:
            raise ValueError(f"no free position for story engine {run.key}")
        slot = rng.choice(fitting)
        _place(engine, slot, operator_of)
        engines.append(engine)
        free_until[slot] = engine.install_date - _gap(rng)

    # Fill the slot with the most open history first, so engines spread across the fleet.
    heap = [(-free_until[s].toordinal(), s) for s in slots]
    heapq.heapify(heap)
    for run in (r for r in removed if not stories.story_for(r.key)):
        _, slot = heapq.heappop(heap)
        engine = _history_engine(run, fault_modes[run.key], free_until[slot], rng)
        _place(engine, slot, operator_of)
        engines.append(engine)
        free_until[slot] = engine.install_date - _gap(rng)
        heapq.heappush(heap, (-free_until[slot].toordinal(), slot))

    engines.sort(key=lambda e: (e.build_date, e.run.split, e.run.unit))
    for offset, engine in enumerate(engines):
        engine.esn = f"CX7-{ESN_START + offset}"
    return engines, aircraft


def _active_engine(run: EngineRun, fault_mode: str, story: str | None, snapshot: date,
                   rng: random.Random) -> Engine:
    n = len(run.cycles)
    last = snapshot - timedelta(days=rng.randint(0, 3))
    if story:
        build = _random_day(_window(story), rng)
        install = build + timedelta(days=rng.randint(*INSTALL_DELAY_DAYS))
        spacing = (last - install).days / (n - 1)
        if not 0.2 <= spacing <= MAX_STORY_SPACING_DAYS:
            raise ValueError(f"story engine {run.key} cannot fit its window (spacing {spacing:.2f})")
    else:
        spacing = rng.uniform(*REPORT_SPACING_DAYS)
        install = last - timedelta(days=round((n - 1) * spacing))
        build = install - timedelta(days=rng.randint(*INSTALL_DELAY_DAYS))
    return _engine(run, fault_mode, story, "active", build, install, spacing, None, rng)


def _story_removed_engine(run: EngineRun, fault_mode: str, story: str, rng: random.Random) -> Engine:
    n = len(run.cycles)
    build = _random_day(_window(story), rng)
    install = build + timedelta(days=rng.randint(*INSTALL_DELAY_DAYS))
    # Removals must precede the response they triggered: the quarantine or the bulletin.
    deadline = (FAN_STORY.quarantine_date if story == "fan_lot" else HPC_STORY.bulletin_date)
    max_spacing = ((deadline - timedelta(days=14)) - install).days / (n - 1)
    spacing = min(rng.uniform(*REPORT_SPACING_DAYS), max_spacing)
    removal = install + timedelta(days=round((n - 1) * spacing))
    return _engine(run, fault_mode, story, "removed", build, install, spacing, removal, rng)


def _history_engine(run: EngineRun, fault_mode: str, removal: date, rng: random.Random) -> Engine:
    n = len(run.cycles)
    spacing = rng.uniform(*REPORT_SPACING_DAYS)
    install = removal - timedelta(days=round((n - 1) * spacing))
    build = install - timedelta(days=rng.randint(*INSTALL_DELAY_DAYS))
    return _engine(run, fault_mode, None, "removed", build, install, spacing, removal, rng)


def _engine(run: EngineRun, fault_mode: str, story: str | None, status: str, build: date,
            install: date, spacing: float, removal: date | None, rng: random.Random) -> Engine:
    if story == "hpc_station":
        plant_id, line = HPC_STORY.plant_id, HPC_STORY.line
    else:
        plant = rng.choice(PLANTS)
        plant_id, line = plant.plant_id, rng.choice(plant.lines)
    dates = [install + timedelta(days=round(i * spacing)) for i in range(len(run.cycles))]
    if removal is not None:
        dates[-1] = removal  # the last report is the removal day itself
    return Engine(run, fault_mode, story, status, plant_id, line, build, install, dates, removal)


def _window(story: str) -> tuple[date, date]:
    return FAN_STORY.build_window if story == "fan_lot" else HPC_STORY.build_window


def _random_day(window: tuple[date, date], rng: random.Random) -> date:
    return window[0] + timedelta(days=rng.randint(0, (window[1] - window[0]).days))


def _gap(rng: random.Random) -> timedelta:
    return timedelta(days=rng.randint(*POSITION_GAP_DAYS))


def _place(engine: Engine, slot: Slot, operator_of: dict[str, str]) -> None:
    engine.tail, engine.position = slot
    engine.operator_id = operator_of[engine.tail]

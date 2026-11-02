"""Fictional reference entities: operators, plants, modules, suppliers and shops.

Every name uses Microsoft's standard fictional brands so that nothing reads as a real
manufacturer's, airline's or supplier's internal data.
"""

from __future__ import annotations

from dataclasses import dataclass

ENGINE_MODEL = "CX-7"
AIRCRAFT_TYPE = "FX-220"  # fictional twinjet; each aircraft carries two CX-7 engines


@dataclass(frozen=True, slots=True)
class Operator:
    operator_id: str
    name: str
    tail_prefix: str
    aircraft_count: int


@dataclass(frozen=True, slots=True)
class Plant:
    plant_id: str
    name: str
    lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ModuleType:
    """An engine module, the part whose supplier lot is tracked, and that part's supplier."""

    module: str
    name: str
    key_part: str
    part_number: str
    supplier: str
    lot_prefix: str
    stations: tuple[str, ...]


OPERATORS: tuple[Operator, ...] = (
    Operator("NWA", "Northwind Air", "NW", 16),
    Operator("FAB", "Fabrikam Airlines", "FB", 14),
    Operator("TSP", "Tailspin Air", "TS", 12),
    Operator("WTR", "Wingtip Regional", "WT", 8),
)

PLANTS: tuple[Plant, ...] = (
    Plant("P1", "Northgate Assembly", ("L1", "L2")),
    Plant("P2", "Riverside Assembly", ("L1", "L2")),
)

MODULE_TYPES: tuple[ModuleType, ...] = (
    ModuleType("FAN", "Fan module", "Fan blade set", "CX7-72-1100", "Litware Composites",
               "FBL", ("FAN-01", "FAN-02")),
    ModuleType("LPC", "Low-pressure compressor", "LPC rotor", "CX7-72-2100", "Lamna Precision",
               "LPR", ("LPC-01", "LPC-02")),
    ModuleType("HPC", "High-pressure compressor", "HPC blisk set", "CX7-72-3100",
               "Proseware Alloys", "HCB", ("HPC-02", "HPC-03", "HPC-04")),
    ModuleType("COMB", "Combustor", "Combustor liner", "CX7-72-4100", "Wide World Metals",
               "CBL", ("CMB-01",)),
    ModuleType("HPT", "High-pressure turbine", "HPT blade set", "CX7-72-5100",
               "A. Datum Castings", "HTB", ("HPT-01", "HPT-02")),
    ModuleType("LPT", "Low-pressure turbine", "LPT blade set", "CX7-72-6100", "Lamna Precision",
               "LTB", ("LPT-01",)),
)
MODULES_BY_ID = {m.module: m for m in MODULE_TYPES}

SHOPS: tuple[str, ...] = ("Contoso Engine Services Northgate", "Contoso Engine Services Riverside")
INSPECTORS: tuple[str, ...] = ("QI-104", "QI-117", "QI-122", "QI-131", "QI-140")

# Mean flight hours per cycle for an FX-220 sector, used to turn cycles into hours.
FLIGHT_HOURS_PER_CYCLE = 1.9

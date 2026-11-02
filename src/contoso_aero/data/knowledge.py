"""Write the knowledge agent's corpus: Contoso procedures and service bulletins as Markdown.

All documents are fictional. The two bulletins close the planted stories, so a multi-agent
question can end with "what should the operator do?".
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .cmapss import CONSTANT_SENSORS, SENSORS
from .reference import ENGINE_MODEL, MODULE_TYPES
from .service import BORESCOPE_INTERVAL_CYCLES
from .stories import FAN_STORY, HPC_STORY


@dataclass(frozen=True, slots=True)
class Document:
    doc_id: str
    title: str
    doc_type: str
    effective_date: str
    body: str

    def render(self) -> str:
        return (f"# {self.doc_id}: {self.title}\n\n"
                f"| Field | Value |\n|---|---|\n| Document | {self.doc_id} |\n"
                f"| Type | {self.doc_type} |\n| Effective | {self.effective_date} |\n"
                f"| Applies to | Contoso Aero Engines {ENGINE_MODEL} |\n\n{self.body.strip()}\n\n"
                "*Fictional document for the Contoso Aero Engines demo. Not for operational use.*\n")


def build_documents() -> list[Document]:
    """Return every knowledge document, built from the same constants the data uses."""
    return [_overview(), _health_monitoring(), _borescope(), _removal_criteria(), _fan_bulletin(),
            _hpc_bulletin(), _ncr_procedure(), _deviation_procedure(), _quarantine_procedure(),
            _difficulty_reporting()]


def write_documents(documents: list[Document], directory: Path) -> list[Path]:
    """Replace the corpus folder's Markdown files so removed documents do not linger."""
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.glob("*.md"):
        stale.unlink()
    paths = []
    for doc in documents:
        path = directory / f"{doc.doc_id}.md"
        path.write_text(doc.render())
        paths.append(path)
    return paths


def _overview() -> Document:
    modules = "\n".join(f"| {m.module} | {m.name} | {m.key_part} ({m.part_number}) | {m.supplier} |"
                        for m in MODULE_TYPES)
    sensors = "\n".join(f"| {name} | {desc} | {unit or '-'} |" for name, desc, unit in SENSORS
                        if name not in CONSTANT_SENSORS)
    return Document("CX7-OVR-001", "CX-7 engine overview and sensor glossary", "Engine manual",
                    "2023-01-15", f"""
## Engine

The CX-7 is a two-spool, high-bypass turbofan built at Northgate Assembly (P1) and Riverside
Assembly (P2), each with lines L1 and L2. It powers the FX-220 twinjet; every aircraft carries
two engines (position 1 left, position 2 right).

## Modules and tracked parts

| Module | Name | Tracked part | Supplier |
|---|---|---|---|
{modules}

Every module carries a serial number of the form `<MODULE>-<engine number>`, for example
`HPC-10091`. Every tracked part comes from a supplier lot, for example `FBL-2501-117`.

## Condition report sensors

Each condition report holds three operating settings and these sensors:

| Sensor | Description | Unit |
|---|---|---|
{sensors}

T2, P2, farB, Nf_dmd and PCNfR_dmd are constant in service and are not reported.
""")


def _health_monitoring() -> Document:
    return Document("CX7-EHM-002", "Engine health monitoring trend limits", "Maintenance procedure",
                    "2024-03-01", """
## Baseline

The baseline for each engine is the average of its first 20 condition reports after installation.

## Trend limits

| Signal | Advisory | Alert | Usual cause |
|---|---|---|---|
| T50 (LPT outlet temperature) | rise of 10 degR | rise of 18 degR | Fan or HPC deterioration |
| P30 (HPC outlet pressure) | fall of 1.0 psia | fall of 1.8 psia | HPC deterioration |
| P30 (HPC outlet pressure) | rise of 4.0 psia | rise of 8.0 psia | Fan deterioration |
| phi (fuel flow to Ps30 ratio) | fall of 0.8 | fall of 1.5 | HPC deterioration |
| Nc (core speed) | rise of 20 rpm | rise of 40 rpm | Fan deterioration |

## Actions

* **Advisory:** check the trend at every report and schedule a borescope at the next opportunity.
* **Alert:** borescope within 10 cycles; engineering review of removal per CX7-RMV-004.
* Compare against the last 20 reports, not single readings, because reports contain sensor noise.
""")


def _borescope() -> Document:
    return Document("CX7-BSI-003", "Borescope inspection procedure", "Maintenance procedure",
                    "2024-03-01", f"""
## Interval

Inspect the fan, HPC, combustor and HPT every {BORESCOPE_INTERVAL_CYCLES} cycles.

## Reduced intervals

* Erosion approaching limits: reduce to 50 cycles.
* Any engine affected by a service bulletin: follow the bulletin's interval.
* Any alert under CX7-EHM-002: inspect within 10 cycles.

## Recording

Record the finding, the action and the engine's cycle count for every inspection.
""")


def _removal_criteria() -> Document:
    return Document("CX7-RMV-004", "Engine removal criteria", "Maintenance procedure", "2024-03-01", """
## Remove the engine when any of these apply

1. EGT margin is exhausted: T50 alert under CX7-EHM-002 confirmed on two consecutive borescopes.
2. Fan vibration exceeds 4.0 units on two flights, or fan efficiency loss is confirmed.
3. A borescope finding exceeds the limits in the engine manual.
4. A service bulletin requires removal.

## After removal

* Raise a service difficulty report within 72 hours (see CX7-SDR-013).
* Send the engine to a Contoso Engine Services shop for a shop visit.
""")


def _fan_bulletin() -> Document:
    start, end = FAN_STORY.build_window
    return Document(FAN_STORY.bulletin_id, "Fan blade root coating inspection", "Service bulletin",
                    FAN_STORY.bulletin_date.isoformat(), f"""
## Reason

Engines removed for fan vibration showed fan blade root coating loss. The affected blades come
from fan blade set lot **{FAN_STORY.lot_id}** (Litware Composites), accepted under deviation
**{FAN_STORY.deviation_id}** with coating below the 92 um minimum. The lot has been quarantined since
{FAN_STORY.quarantine_date.isoformat()}.

## Affected engines

CX-7 engines whose fan module contains a blade set from lot {FAN_STORY.lot_id}. These engines were
built between {start.isoformat()} and {end.isoformat()}.

## Required action

1. Borescope the fan blade roots within 25 cycles of this bulletin.
2. Repeat every 25 cycles.
3. Coating loss on more than 6 blades, or any fretting: remove the engine and replace the fan blade set.
""")


def _hpc_bulletin() -> Document:
    start, end = HPC_STORY.build_window
    return Document(HPC_STORY.bulletin_id, "HPC rotor stack bolt preload verification", "Service bulletin",
                    HPC_STORY.bulletin_date.isoformat(), f"""
## Reason

Shop visits found low rotor stack bolt preload on HPC modules built at station {HPC_STORY.station}
(Riverside Assembly, line {HPC_STORY.line}). Torque wrench {HPC_STORY.tool_id} was under-reading
(see {HPC_STORY.ncr_id}). Low preload lets the blisks move and rub, which speeds HPC deterioration.

## Affected engines

CX-7 engines whose HPC module was built at {HPC_STORY.station} between {start.isoformat()} and
{end.isoformat()}.

## Required action

1. Borescope HPC stages 3 to 5 every 50 cycles.
2. Trend P30 and T50 at every report against CX7-EHM-002 limits.
3. At the next shop visit, re-torque the rotor stack to specification.
""")


def _ncr_procedure() -> Document:
    return Document("QP-NCR-010", "Nonconformance reports and MRB disposition", "Quality procedure",
                    "2023-01-15", """
## When to raise an NCR

Raise a nonconformance report (NCR) when an inspection fails, or when a tool, process or part is
found outside specification.

## Dispositions

| Disposition | Meaning |
|---|---|
| rework | Fix the part to specification and re-inspect. |
| use-as-is (MRB) | The Material Review Board accepts the part after engineering analysis. |
| scrap | The part cannot be used. |

## Closure

An NCR is closed when the disposition is complete and the root cause is recorded.
""")


def _deviation_procedure() -> Document:
    return Document("QP-DEV-011", "Deviation approval", "Quality procedure", "2023-01-15", """
## What a deviation is

A deviation is planned, approved permission to build with a known departure from specification,
for a stated period or lot. It is approved **before** use, unlike an NCR.

## Approval

Engineering and Quality must both approve. The deviation names the module, the lot or period
covered, the description and the rationale.
""")


def _quarantine_procedure() -> Document:
    return Document("QP-QTN-012", "Supplier lot quarantine", "Quality procedure", "2023-01-15", """
## When to quarantine

Quarantine a supplier lot when its paperwork is incomplete, or when field or factory evidence links
it to a defect.

## Effect

No part from a quarantined lot may be fitted. Engines already built with the lot are reviewed by
engineering, which may issue a service bulletin.

## Release

Release the lot only when the cause is resolved and Quality signs the release.
""")


def _difficulty_reporting() -> Document:
    return Document("CX7-SDR-013", "Reporting service difficulties", "Operator guidance", "2024-03-01", """
## What to report

Operators report every unscheduled engine removal as a service difficulty report (SDR). Contoso
uses the field layout of the public FAA Form 8070-1 for consistency: aircraft type and
registration, engine model and serial number, part name and number, part condition and location,
nature of the condition, precautionary procedure, problem description, and part time since new.

## When

Within 72 hours of the removal.
""")

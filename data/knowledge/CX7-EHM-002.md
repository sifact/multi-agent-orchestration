# CX7-EHM-002: Engine health monitoring trend limits

| Field | Value |
|---|---|
| Document | CX7-EHM-002 |
| Type | Maintenance procedure |
| Effective | 2024-03-01 |
| Applies to | Contoso Aero Engines CX-7 |

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

*Fictional document for the Contoso Aero Engines demo. Not for operational use.*

# CX7-OVR-001: CX-7 engine overview and sensor glossary

| Field | Value |
|---|---|
| Document | CX7-OVR-001 |
| Type | Engine manual |
| Effective | 2023-01-15 |
| Applies to | Contoso Aero Engines CX-7 |

## Engine

The CX-7 is a two-spool, high-bypass turbofan built at Northgate Assembly (P1) and Riverside
Assembly (P2), each with lines L1 and L2. It powers the FX-220 twinjet; every aircraft carries
two engines (position 1 left, position 2 right).

## Modules and tracked parts

| Module | Name | Tracked part | Supplier |
|---|---|---|---|
| FAN | Fan module | Fan blade set (CX7-72-1100) | Litware Composites |
| LPC | Low-pressure compressor | LPC rotor (CX7-72-2100) | Lamna Precision |
| HPC | High-pressure compressor | HPC blisk set (CX7-72-3100) | Proseware Alloys |
| COMB | Combustor | Combustor liner (CX7-72-4100) | Wide World Metals |
| HPT | High-pressure turbine | HPT blade set (CX7-72-5100) | A. Datum Castings |
| LPT | Low-pressure turbine | LPT blade set (CX7-72-6100) | Lamna Precision |

Every module carries a serial number of the form `<MODULE>-<engine number>`, for example
`HPC-10091`. Every tracked part comes from a supplier lot, for example `FBL-2501-117`.

## Condition report sensors

Each condition report holds three operating settings and these sensors:

| Sensor | Description | Unit |
|---|---|---|
| T24 | Total temperature at LPC outlet | degR |
| T30 | Total temperature at HPC outlet | degR |
| T50 | Total temperature at LPT outlet | degR |
| P15 | Total pressure in bypass duct | psia |
| P30 | Total pressure at HPC outlet | psia |
| Nf | Physical fan speed | rpm |
| Nc | Physical core speed | rpm |
| epr | Engine pressure ratio (P50/P2) | - |
| Ps30 | Static pressure at HPC outlet | psia |
| phi | Ratio of fuel flow to Ps30 | pps/psi |
| NRf | Corrected fan speed | rpm |
| NRc | Corrected core speed | rpm |
| BPR | Bypass ratio | - |
| htBleed | Bleed enthalpy | - |
| W31 | HPT coolant bleed | lbm/s |
| W32 | LPT coolant bleed | lbm/s |

T2, P2, farB, Nf_dmd and PCNfR_dmd are constant in service and are not reported.

*Fictional document for the Contoso Aero Engines demo. Not for operational use.*

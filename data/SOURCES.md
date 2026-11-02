# Data sources

## NASA C-MAPSS turbofan engine degradation data

Real engine telemetry for the engine telemetry agent. The files are stored locally in `data/raw/cmapss/`, which is git-ignored, so they are not redistributed with this repository.

| Field | Value |
|---|---|
| Source page | [NASA PCoE Data Set Repository](https://www.nasa.gov/intelligent-systems-division/discovery-and-systems-health/pcoe/pcoe-data-set-repository/), item 6 "Turbofan Engine Degradation Simulation" |
| Download | <https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip> |
| Outer zip SHA-256 | `c9c5dec12a945a82e8bb4446589d7fb3cc057b5e5d81fa1a12e25ee9912ad3b2` (12,429,152 bytes) |
| Retrieved | 2026-10-29 |
| Licence | None stated. NASA asks users to cite the data set (below). |
| Citation | A. Saxena and K. Goebel (2008). "Turbofan Engine Degradation Simulation Data Set", NASA Prognostics Data Repository, NASA Ames Research Center, Moffett Field, CA. |
| Paper | A. Saxena, K. Goebel, D. Simon, and N. Eklund, "Damage Propagation Modeling for Aircraft Engine Run-to-Failure Simulation", PHM08, Denver CO, Oct 2008 (included as `Damage Propagation Modeling.pdf`). |

NASA's separate data catalog entry (data.nasa.gov) marks C-MAPSS as unavailable. The PCoE repository download above is the working official source.

### Contents

The zip contains a nested `CMAPSSData.zip` with these files:

* `train_FD00x.txt`: engines run to failure.
* `test_FD00x.txt`: engines stopped before failure.
* `RUL_FD00x.txt`: the true remaining cycles for each test engine.
* `readme.txt`: the dataset description.

Each file holds space-separated rows with 26 columns: unit number, cycle, 3 operational settings, then sensors 1–21. The readme says "26 sensors", but only 21 sensor columns exist. Sensor names (T2, T24, T30, T50, P2, …) are listed in the paper.

| Subset | Train engines | Test engines | Conditions | Fault modes |
|---|---|---|---|---|
| FD001 | 100 | 100 | 1 (sea level) | HPC degradation |
| FD002 | 260 | 259 | 6 | HPC degradation |
| FD003 | 100 | 100 | 1 (sea level) | HPC and fan degradation |
| FD004 | 249 (readme says 248) | 249 | 6 | HPC and fan degradation |

**Chosen subset: FD003.** It has 100 engines, a believable fleet size, and two fault modes. That allows two planted factory stories: fan wear traced to a fan supplier lot, and compressor (HPC) wear traced to a compressor build deviation.

### Re-fetching

```bash
mkdir -p data/raw/cmapss && cd data/raw/cmapss
curl -L -o cmapss.zip "https://phm-datasets.s3.amazonaws.com/NASA/6.+Turbofan+Engine+Degradation+Simulation+Data+Set.zip"
shasum -a 256 cmapss.zip   # must match the hash above
unzip -j cmapss.zip && unzip -o CMAPSSData.zip && rm cmapss.zip CMAPSSData.zip
```

Contoso Aero Engines engine serial numbers are a fictional mapping onto C-MAPSS unit numbers. No real manufacturer is implied.

### What FD003 gives the project

* **Removed engines:** the 100 train engines become Contoso's removed engines. Each real failure becomes an unscheduled removal.
* **Active fleet:** the 100 test engines become the active fleet. NASA's true remaining life (6 to 145 cycles) is the hidden answer key.
* **Fault modes are inferred, not labelled by NASA.** P30 falls with HPC wear (it falls in all 100 FD001 engines, which have HPC faults only) and rises with fan wear.
  * Train engines: 56 HPC and 44 fan.
  * Test engines: 44 fan, 31 HPC, and 25 unknown (too short to tell). On truncated train runs this rule never mislabelled an engine.

## Generated dataset

Build it with `uv run python -m contoso_aero.data`. One seed (`20260612`) and a fixed snapshot date (2026-10-29) make every rebuild byte-identical.

| Output | Where | In git? |
|---|---|---|
| SQLite database, 16 tables | `data/generated/contoso_aero.sqlite3` | No: contains NASA telemetry |
| CSV copy of every table | `data/generated/csv/` | No |
| 10 knowledge documents | `data/knowledge/*.md` | Yes: fully synthetic |
| 59 evaluation questions | `data/eval/questions.jsonl` | Yes: shared with project 2 |

### Tables by owning agent

Each agent may query only its own tables (see `TABLE_OWNERS` in `src/contoso_aero/data/database.py`).

| Agent | Tables (rows) | Real or synthetic |
|---|---|---|
| Telemetry | `operators` (4), `aircraft` (50), `engines` (200), `engine_telemetry` (41,316) | Telemetry readings are **real** C-MAPSS; serials, dates and aircraft are synthetic |
| Service | `removals` (100), `shop_visits` (100), `difficulty_reports` (100), `borescope_inspections` (320) | Synthetic; difficulty reports use the FAA Form 8070-1 field layout |
| Production | `engine_builds` (200), `module_builds` (1,200), `supplier_lots` (150) | Synthetic |
| Quality | `inspections` (1,229), `ncrs` (30), `deviations` (4), `lot_quarantines` (2) | Synthetic |
| Knowledge | `data/knowledge/*.md` (10 documents) | Synthetic |
| None (scoring only) | `ground_truth` (200): C-MAPSS unit, true remaining life, inferred fault mode, story | Hidden from all agents |

### Planted stories

The stories give multi-agent questions known answers. Their engines were chosen from real C-MAPSS outcomes, and the factory history was written to fit them.

1. **Fan blade lot.**
   * Lot `FBL-2501-117` (Litware Composites) was accepted under deviation `DEV-2025-007` with blade root coating below the 92 um minimum.
   * 12 engines carry the lot: 10 story engines plus 2 that did not fail by fan wear.
   * Six were removed for fan vibration between 2025-09 and 2026-05. The lot was quarantined on 2026-09-22, and bulletin `SB-CX7-72-0042` followed on 2026-10-01.
   * The 4 active engines with the lot have 6 to 8 cycles of true remaining life.
2. **HPC torque wrench.**
   * Wrench `TW-118` at station `HPC-04` (Riverside, line L2) was under-reading, raised as `NCR-2025-0388` (disposition use-as-is).
   * It affects 11 HPC modules built between 2025-06-02 and 2025-07-18. Six of those engines have since been removed.
   * Bulletin `SB-CX7-72-0051` was issued on 2026-08-14.

**Trend limits.** The limits in `CX7-EHM-002` are calibrated on the real drift. 15 active engines are in alert, and every one has 35 cycles or fewer of true remaining life.

# cmapss.py

Loads NASA C-MAPSS run-to-failure files and labels each engine's likely fault mode.

* Reads the space-separated train and test files of one subset into engine runs.
* Names the 21 sensors from Table 2 of the NASA paper and drops the 5 that never change.
* Attaches NASA's true remaining life to each test engine from the RUL file.
* Labels fault mode from the P30 trend: falling means HPC wear, rising means fan wear.
* Returns unknown for short test runs whose trend is not statistically clear.

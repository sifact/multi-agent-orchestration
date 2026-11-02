# stats.py

Pure statistics helpers that give evaluation rates a confidence interval.

* Provides `wilson_interval(successes, total, z=1.96)` for a proportion.
* Uses the Wilson score interval, which behaves well for small samples and rates near 0% or 100%.
* Returns `(0.0, 0.0)` when there are no cases.
* Clamps bounds to the range 0 to 1.
* Has no I/O and no dependencies beyond the standard library.

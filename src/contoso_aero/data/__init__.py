"""Dataset generation: real C-MAPSS telemetry plus linked synthetic factory and fleet records."""

from .builder import BuildSummary, build_dataset
from .database import TABLE_OWNERS

__all__ = ["TABLE_OWNERS", "BuildSummary", "build_dataset"]

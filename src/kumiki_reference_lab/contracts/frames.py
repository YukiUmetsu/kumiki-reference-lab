"""Internal raw frame observations. Persistent JSON contracts are versioned separately."""

from dataclasses import dataclass


@dataclass(frozen=True)
class FramePts:
    ordinal: int
    pts: int | None
    origin: str  # best_effort_timestamp, pts-fallback, or missing

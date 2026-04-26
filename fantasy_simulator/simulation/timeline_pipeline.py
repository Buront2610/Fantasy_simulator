"""Structured day-pipeline helpers for ``TimelineMixin``."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True, slots=True)
class DayPhaseContext:
    """Immutable date context shared by day-pipeline phases."""

    month: int
    day: int
    days_in_month: int
    year_fraction_per_day: float
    is_month_start: bool
    is_month_end: bool


class DayPhaseKind(str, Enum):
    MONTH_START = "month_start"
    DYING_RESOLUTION = "dying_resolution"
    NATURAL_HEALTH = "natural_health"
    INJURY_RECOVERY = "injury_recovery"
    ADVENTURE = "adventure"
    RANDOM_EVENTS = "random_events"
    MONTH_END = "month_end"


@dataclass(frozen=True, slots=True)
class DayPhase:
    """A named day-processing phase."""

    kind: DayPhaseKind


def build_day_phase_context(
    *,
    month: int,
    day: int,
    days_in_month: int,
    days_per_year: int,
) -> DayPhaseContext:
    """Build the immutable per-day context consumed by the pipeline."""
    safe_days_per_year = max(1, int(days_per_year))
    return DayPhaseContext(
        month=month,
        day=day,
        days_in_month=days_in_month,
        year_fraction_per_day=1.0 / safe_days_per_year,
        is_month_start=(day == 1),
        is_month_end=(day == days_in_month),
    )


def build_day_phase_plan(day_context: DayPhaseContext) -> list[DayPhase]:
    """Return explicit chronological phases for a single in-world day."""
    phases: list[DayPhase] = []
    if day_context.is_month_start:
        phases.append(DayPhase(DayPhaseKind.MONTH_START))
    phases.extend(
        [
            DayPhase(DayPhaseKind.DYING_RESOLUTION),
            DayPhase(DayPhaseKind.NATURAL_HEALTH),
            DayPhase(DayPhaseKind.INJURY_RECOVERY),
            DayPhase(DayPhaseKind.ADVENTURE),
            DayPhase(DayPhaseKind.RANDOM_EVENTS),
        ]
    )
    if day_context.is_month_end:
        phases.append(DayPhase(DayPhaseKind.MONTH_END))
    return phases

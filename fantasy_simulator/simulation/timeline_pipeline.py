"""Structured day-pipeline helpers for ``TimelineMixin``."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DayPhaseContext:
    """Immutable date context shared by day-pipeline phases."""

    month: int
    day: int
    days_in_month: int
    year_fraction_per_day: float
    is_month_start: bool
    is_month_end: bool


@dataclass(frozen=True, slots=True)
class DayPhase:
    """A named day-processing phase bound to a mixin method name."""

    name: str
    handler_name: str


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
        phases.append(DayPhase("month_start", "_run_month_start_phase"))
    phases.extend(
        [
            DayPhase("dying_resolution", "_run_dying_resolution_phase"),
            DayPhase("natural_health", "_run_natural_health_phase"),
            DayPhase("injury_recovery", "_run_injury_recovery_phase"),
            DayPhase("adventure", "_run_adventure_phase"),
            DayPhase("random_events", "_run_random_event_phase"),
        ]
    )
    if day_context.is_month_end:
        phases.append(DayPhase("month_end", "_run_month_end_phase"))
    return phases

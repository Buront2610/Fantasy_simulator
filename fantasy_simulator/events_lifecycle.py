"""Backward-compatible lifecycle event imports."""

from __future__ import annotations

from .events.lifecycle import (
    DeathEventCallback,
    character_lifespan_years,
    check_dying_resolution,
    check_natural_death,
    natural_death_chance,
    resolve_aging_event,
    resolve_death_event,
    should_record_aging_event,
)

__all__ = [
    "DeathEventCallback",
    "character_lifespan_years",
    "check_dying_resolution",
    "check_natural_death",
    "natural_death_chance",
    "resolve_aging_event",
    "resolve_death_event",
    "should_record_aging_event",
]

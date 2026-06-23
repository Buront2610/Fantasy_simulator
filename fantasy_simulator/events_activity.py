"""Backward-compatible solo activity event imports."""

from __future__ import annotations

from .events.activity import (
    resolve_discovery_event,
    resolve_journey_event,
    resolve_skill_training_event,
)

__all__ = [
    "resolve_discovery_event",
    "resolve_journey_event",
    "resolve_skill_training_event",
]

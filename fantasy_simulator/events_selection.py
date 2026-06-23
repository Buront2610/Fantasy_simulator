"""Backward-compatible random event selection imports."""

from __future__ import annotations

from .events.selection import (
    BIRTH_EVENT_WEIGHT,
    EVENT_WEIGHTS,
    birth_pairs,
    eligible_random_event_characters,
    find_birth_pair,
    find_collocated_pair,
    find_romance_pair,
    generate_random_event,
)

__all__ = [
    "BIRTH_EVENT_WEIGHT",
    "EVENT_WEIGHTS",
    "birth_pairs",
    "eligible_random_event_characters",
    "find_birth_pair",
    "find_collocated_pair",
    "find_romance_pair",
    "generate_random_event",
]

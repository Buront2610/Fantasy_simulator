"""Backward-compatible family event imports."""

from __future__ import annotations

from .events.family import BIRTH_PARENT_RELATIONSHIP_DELTA, resolve_birth_event

__all__ = [
    "BIRTH_PARENT_RELATIONSHIP_DELTA",
    "resolve_birth_event",
]

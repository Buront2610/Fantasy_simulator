"""Compatibility facade for ``World`` serialization and hydration."""

from __future__ import annotations

from .world_persistence_hydrator import hydrate_world_state
from .world_persistence_serializer import serialize_world_state

__all__ = [
    "hydrate_world_state",
    "serialize_world_state",
]

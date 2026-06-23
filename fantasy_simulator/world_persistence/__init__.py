"""Compatibility facade for ``World`` serialization and hydration."""

from __future__ import annotations

from .hydrator import hydrate_world_state
from .serializer import serialize_world_state

__all__ = [
    "hydrate_world_state",
    "serialize_world_state",
]

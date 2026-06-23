"""Backward-compatible adventure domain facade imports."""

from __future__ import annotations

from .adventure import domain as _adventure_domain
from .adventure.domain import *  # noqa: F401,F403

__all__ = _adventure_domain.__all__

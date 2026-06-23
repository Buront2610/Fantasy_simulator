"""Backward-compatible combat event imports."""

from __future__ import annotations

from .events.combat import resolve_battle_event

__all__ = [
    "resolve_battle_event",
]

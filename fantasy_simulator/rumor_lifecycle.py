"""Backward-compatible rumor lifecycle imports."""

from __future__ import annotations

from .rumor.lifecycle import age_rumors, trim_rumors

__all__ = [
    "age_rumors",
    "trim_rumors",
]

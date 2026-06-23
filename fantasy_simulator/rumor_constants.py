"""Backward-compatible rumor constant imports."""

from __future__ import annotations

from .rumor.constants import (
    DISCLOSURE,
    MAX_ACTIVE_RUMORS,
    MIN_SEVERITY_FOR_RUMOR,
    RELIABILITY_LEVELS,
    RUMOR_BASE_CHANCE,
    RUMOR_MAX_AGE_MONTHS,
)

__all__ = [
    "DISCLOSURE",
    "MAX_ACTIVE_RUMORS",
    "MIN_SEVERITY_FOR_RUMOR",
    "RELIABILITY_LEVELS",
    "RUMOR_BASE_CHANCE",
    "RUMOR_MAX_AGE_MONTHS",
]

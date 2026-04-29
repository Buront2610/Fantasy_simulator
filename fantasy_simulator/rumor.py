"""Compatibility exports for the Fantasy Simulator rumor system.

Rumors are generated from WorldEventRecord entries and spread through
the world with varying reliability. They give players indirect,
imperfect information about events they did not directly observe.
"""

from __future__ import annotations

from .event_models import WorldEventRecord
from .rumor_constants import (
    DISCLOSURE,
    MAX_ACTIVE_RUMORS,
    MIN_SEVERITY_FOR_RUMOR as _MIN_SEVERITY_FOR_RUMOR,
    RELIABILITY_LEVELS,
    RUMOR_BASE_CHANCE as _RUMOR_BASE_CHANCE,
    RUMOR_MAX_AGE_MONTHS,
)
from .rumor_generation import (
    _build_rumor_description,
    _category_from_event_kind,
    _content_tags_from_event,
    _determine_reliability,
    generate_rumor_from_event,
    generate_rumors_for_period,
)
from .rumor_lifecycle import age_rumors, trim_rumors
from .rumor_models import Rumor

__all__ = [
    "DISCLOSURE",
    "MAX_ACTIVE_RUMORS",
    "RELIABILITY_LEVELS",
    "RUMOR_MAX_AGE_MONTHS",
    "Rumor",
    "WorldEventRecord",
    "_MIN_SEVERITY_FOR_RUMOR",
    "_RUMOR_BASE_CHANCE",
    "_build_rumor_description",
    "_category_from_event_kind",
    "_content_tags_from_event",
    "_determine_reliability",
    "age_rumors",
    "generate_rumor_from_event",
    "generate_rumors_for_period",
    "trim_rumors",
]

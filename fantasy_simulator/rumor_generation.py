"""Backward-compatible rumor generation imports."""

from __future__ import annotations

from .rumor.generation import (
    _build_rumor_description,
    _category_from_event_kind,
    _content_tags_from_event,
    _determine_reliability,
    generate_rumor_from_event,
    generate_rumors_for_period,
    generate_tracked_rumor_from_world_change,
)

__all__ = [
    "_build_rumor_description",
    "_category_from_event_kind",
    "_content_tags_from_event",
    "_determine_reliability",
    "generate_rumor_from_event",
    "generate_rumors_for_period",
    "generate_tracked_rumor_from_world_change",
]

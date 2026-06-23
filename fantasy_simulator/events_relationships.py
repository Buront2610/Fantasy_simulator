"""Backward-compatible relationship event imports."""

from __future__ import annotations

from .events.relationships import (
    CATALYST_EVENT_KINDS,
    CATALYST_RELATION_TAGS,
    PERSONALITY_TURNING_POINT_KINDS,
    RelationshipCatalyst,
    RelationshipPersonality,
    resolve_marriage_event,
    resolve_meeting_event,
    resolve_relationship_turning_point_event,
)

__all__ = [
    "CATALYST_EVENT_KINDS",
    "CATALYST_RELATION_TAGS",
    "PERSONALITY_TURNING_POINT_KINDS",
    "RelationshipCatalyst",
    "RelationshipPersonality",
    "resolve_marriage_event",
    "resolve_meeting_event",
    "resolve_relationship_turning_point_event",
]

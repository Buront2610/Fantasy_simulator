"""Canonical event-history query helpers for the World aggregate."""

from __future__ import annotations

from typing import List

from .event_models import WorldEventRecord
from .world_event_index import EventHistoryIndex


def events_by_location(
    event_index: EventHistoryIndex,
    event_records: List[WorldEventRecord],
    location_id: str,
) -> List[WorldEventRecord]:
    """Return all event records for a specific location."""
    return event_index.by_location_id(event_records, location_id)


def events_by_actor(
    event_index: EventHistoryIndex,
    event_records: List[WorldEventRecord],
    char_id: str,
) -> List[WorldEventRecord]:
    """Return all event records involving a specific character."""
    return event_index.by_actor_id(event_records, char_id)


def events_by_year(
    event_index: EventHistoryIndex,
    event_records: List[WorldEventRecord],
    year: int,
) -> List[WorldEventRecord]:
    """Return all event records for a specific year."""
    return event_index.by_year_value(event_records, year)


def events_by_month(
    event_index: EventHistoryIndex,
    event_records: List[WorldEventRecord],
    year: int,
    month: int,
) -> List[WorldEventRecord]:
    """Return all event records for a specific in-world month."""
    return event_index.by_month_value(event_records, year, month)


def events_by_kind(
    event_index: EventHistoryIndex,
    event_records: List[WorldEventRecord],
    kind: str,
) -> List[WorldEventRecord]:
    """Return all event records for a specific canonical event kind."""
    return event_index.by_kind_value(event_records, kind)

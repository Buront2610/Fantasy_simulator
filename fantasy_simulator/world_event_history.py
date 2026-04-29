"""Canonical world-event history helpers."""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable, List, Mapping, Sequence

from .event_models import WorldEventRecord
from .world_event_index import EventHistoryIndex
from .world_event_state import SupportsEventIndex, append_canonical_event_record


def latest_absolute_day_before_or_on(
    event_records: Sequence[WorldEventRecord],
    *,
    year: int,
    month: int,
) -> int:
    """Return the latest known absolute day on or before a report period."""
    matching_days = [
        record.absolute_day
        for record in event_records
        if record.absolute_day > 0 and (record.year, record.month) <= (year, month)
    ]
    return max(matching_days, default=0)


def watched_actor_tags_for_record(
    record: WorldEventRecord,
    *,
    get_character_by_id: Callable[[str], Any],
    watched_actor_tag_prefix: str,
) -> List[str]:
    """Return watched-actor tags implied by a record's participating actors."""
    watched_tags: List[str] = []
    actor_ids = [record.primary_actor_id] + list(record.secondary_actor_ids)
    for actor_id in actor_ids:
        if not actor_id:
            continue
        actor = get_character_by_id(actor_id)
        if actor is None:
            continue
        if actor.favorite or actor.spotlighted or actor.playable:
            watched_tags.append(f"{watched_actor_tag_prefix}{actor_id}")
    return watched_tags


def record_world_event(
    *,
    record: WorldEventRecord,
    event_records: List[WorldEventRecord],
    event_index: EventHistoryIndex,
    location_index: Mapping[str, SupportsEventIndex],
    grid: Mapping[Any, SupportsEventIndex],
    max_event_records: int,
    get_character_by_id: Callable[[str], Any],
    watched_actor_tag_prefix: str,
) -> WorldEventRecord:
    """Store a canonical world event and keep event-history indexes coherent."""
    event_index.ensure_current(event_records)
    watched_tags = watched_actor_tags_for_record(
        record,
        get_character_by_id=get_character_by_id,
        watched_actor_tag_prefix=watched_actor_tag_prefix,
    )
    normalized_record = record
    if watched_tags:
        normalized_record = replace(record, tags=list(dict.fromkeys(list(record.tags) + watched_tags)))

    stored_record = append_canonical_event_record(
        record=normalized_record,
        event_records=event_records,
        location_index=location_index,
        grid=grid,
        max_event_records=max_event_records,
        existing_record_ids=event_index.record_ids,
    )
    event_index.invalidate()
    return stored_record

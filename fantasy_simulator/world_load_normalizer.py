"""Post-load repair helpers for ``World``.

This module isolates save/load normalization and derived-index rebuilding from
the core world aggregate.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Mapping, MutableSequence, Protocol, Sequence

from .event_models import WorldEventRecord
from .world_event_index import location_ids_for_record
from .world_event_record_updates import event_record_with_normalized_location_references


class SupportsRecentEvents(Protocol):
    recent_event_ids: List[str]


def ensure_unique_event_record_ids(event_records: Sequence[WorldEventRecord]) -> None:
    """Fail fast when canonical history contains duplicate record IDs."""
    seen: set[str] = set()
    for record in event_records:
        if record.record_id in seen:
            raise ValueError(f"Duplicate event record ID during rebuild: {record.record_id!r}")
        seen.add(record.record_id)


def rebuild_recent_event_ids(
    *,
    locations: Iterable[SupportsRecentEvents],
    location_index: Mapping[str, SupportsRecentEvents],
    event_records: MutableSequence[WorldEventRecord],
    max_recent_event_ids: int = 12,
) -> None:
    """Rebuild derived per-location recent event IDs from canonical records.

    Unknown location references are normalized out of stored records before
    indexing so recent-event IDs are derived from the same repaired references
    that reports and event-history queries use.
    """
    for location in locations:
        location.recent_event_ids = []

    def normalize_indexed_location_id(location_id: str | None) -> str | None:
        if location_id is None or location_id not in location_index:
            return None
        return location_id

    for index, record in enumerate(event_records):
        original_record = record
        record = event_record_with_normalized_location_references(record, normalize_indexed_location_id)
        if record != original_record:
            event_records[index] = record
        for attached_location_id in location_ids_for_record(record):
            attached_location = location_index.get(attached_location_id)
            if attached_location is None:
                continue
            attached_location.recent_event_ids.append(record.record_id)

    for location in locations:
        location.recent_event_ids = location.recent_event_ids[-max_recent_event_ids:]


def normalize_after_load(
    *,
    event_records: Sequence[WorldEventRecord],
    repair_location_references: Callable[[], None],
    rebuild_char_index: Callable[[], None],
    backfill_watched_actor_tags: Callable[[], None],
    ensure_valid_character_locations: Callable[[], None],
    rebuild_adventure_index: Callable[[], None],
    rebuild_recent_event_ids_fn: Callable[[], None],
    rebuild_location_memorial_ids_fn: Callable[[], None],
    rebuild_compatibility_event_log: Callable[[], None],
) -> None:
    """Rebuild derived indexes and repair invariants after deserialization."""
    repair_location_references()
    rebuild_char_index()
    ensure_unique_event_record_ids(event_records)
    backfill_watched_actor_tags()
    ensure_valid_character_locations()
    rebuild_adventure_index()
    rebuild_recent_event_ids_fn()
    rebuild_location_memorial_ids_fn()
    if event_records:
        rebuild_compatibility_event_log()

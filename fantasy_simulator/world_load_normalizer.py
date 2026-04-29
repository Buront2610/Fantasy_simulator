"""Post-load repair helpers for ``World``.

This module isolates save/load normalization and derived-index rebuilding from
the core world aggregate.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Mapping, Protocol, Sequence

from .event_models import WorldEventRecord


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
    event_records: Sequence[WorldEventRecord],
    max_recent_event_ids: int = 12,
) -> None:
    """Rebuild derived per-location recent event IDs from canonical records."""
    for location in locations:
        location.recent_event_ids = []

    for record in event_records:
        location_id = record.location_id
        if location_id is None or location_id not in location_index:
            record.location_id = None
            continue
        location_index[location_id].recent_event_ids.append(record.record_id)

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

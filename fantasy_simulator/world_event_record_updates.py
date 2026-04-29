"""Copy-based update helpers for canonical world event records."""

from __future__ import annotations

from dataclasses import replace
from typing import Callable, Iterable

from .event_models import WorldEventRecord


def event_record_with_location_id(
    record: WorldEventRecord,
    location_id: str | None,
) -> WorldEventRecord:
    """Return a copy of *record* with a normalized location reference."""
    return replace(record, location_id=location_id)


def normalize_event_record_locations(
    records: Iterable[WorldEventRecord],
    normalize_location_id: Callable[[str | None], str | None],
) -> list[WorldEventRecord]:
    """Return event record copies with location IDs normalized."""
    return [
        event_record_with_location_id(record, normalize_location_id(record.location_id))
        for record in records
    ]


def event_record_with_added_tags(
    record: WorldEventRecord,
    tags: Iterable[str],
) -> WorldEventRecord:
    """Return a copy of *record* with unique appended tags."""
    return replace(record, tags=list(dict.fromkeys([*record.tags, *tags])))

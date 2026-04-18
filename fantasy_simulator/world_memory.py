"""World-memory helpers for ``World``.

This module isolates location memories such as live traces, memorials, and
aliases from the core aggregate orchestration.
"""

from __future__ import annotations

from typing import Iterable, List, Mapping, MutableMapping, Protocol, Sequence


class SupportsLiveTraces(Protocol):
    live_traces: List[dict]


class SupportsAliases(Protocol):
    aliases: List[str]


class SupportsMemorialIds(Protocol):
    memorial_ids: List[str]


class SupportsMemorialRecord(Protocol):
    memorial_id: str
    location_id: str


def add_live_trace(
    *,
    location_index: Mapping[str, SupportsLiveTraces],
    location_id: str,
    year: int,
    char_name: str,
    text: str,
    max_live_traces: int,
) -> None:
    """Record a visitor trace at a location, trimming to a rolling cap."""
    location = location_index.get(location_id)
    if location is None:
        return
    location.live_traces.append({"year": year, "char_name": char_name, "text": text})
    if len(location.live_traces) > max_live_traces:
        location.live_traces = location.live_traces[-max_live_traces:]


def link_memorial_record(
    *,
    memorials: MutableMapping[str, SupportsMemorialRecord],
    location_index: Mapping[str, SupportsMemorialIds],
    record: SupportsMemorialRecord,
) -> None:
    """Store a memorial record and link it to the live location when present."""
    memorials[record.memorial_id] = record
    location = location_index.get(record.location_id)
    if location is not None and record.memorial_id not in location.memorial_ids:
        location.memorial_ids.append(record.memorial_id)


def add_alias(
    *,
    location_index: Mapping[str, SupportsAliases],
    location_id: str,
    alias: str,
    max_aliases: int,
) -> None:
    """Append a location alias if it is new and within the configured cap."""
    location = location_index.get(location_id)
    if location is None:
        return
    if alias not in location.aliases and len(location.aliases) < max_aliases:
        location.aliases.append(alias)


def memorials_for_location(
    *,
    location_index: Mapping[str, SupportsMemorialIds],
    memorials: Mapping[str, SupportsMemorialRecord],
    location_id: str,
) -> List[SupportsMemorialRecord]:
    """Return linked memorial records for a location, skipping stale IDs."""
    location = location_index.get(location_id)
    if location is None:
        return []
    return [memorials[memorial_id] for memorial_id in location.memorial_ids if memorial_id in memorials]


def rebuild_location_memorial_ids(
    *,
    locations: Iterable[SupportsMemorialIds],
    location_index: Mapping[str, SupportsMemorialIds],
    memorials: Sequence[SupportsMemorialRecord] | Iterable[SupportsMemorialRecord],
) -> None:
    """Rebuild per-location memorial indices from canonical memorial records."""
    for location in locations:
        location.memorial_ids = []
    for memorial in memorials:
        location = location_index.get(memorial.location_id)
        if location is not None and memorial.memorial_id not in location.memorial_ids:
            location.memorial_ids.append(memorial.memorial_id)

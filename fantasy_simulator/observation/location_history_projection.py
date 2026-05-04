"""Location history projection for PR-K world-change observation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from fantasy_simulator.event_models import WorldEventRecord

from ._record_helpers import (
    as_string,
    first_record_location_id,
    impact_string,
    record_location_ids,
    semantic_render_params,
    string_param,
)


LOCATION_CONTROL_KINDS = {"location_faction_changed", "location_occupied", "location_liberated"}


class SupportsLocationHistory(Protocol):
    id: str
    canonical_name: str
    aliases: list[str]
    recent_event_ids: list[str]


@dataclass(frozen=True)
class LocationRenameHistoryEntry:
    """A location rename event summarized for observation."""

    record_id: str
    year: int
    month: int
    day: int
    old_name: str
    new_name: str
    description: str
    summary_key: str = ""
    render_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LocationControlHistoryEntry:
    """A location control or occupation event summarized for observation."""

    record_id: str
    kind: str
    year: int
    month: int
    day: int
    old_faction_id: str | None
    new_faction_id: str | None
    description: str
    summary_key: str = ""
    render_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LocationHistoryProjection:
    """Read model for one location's current name, aliases, and change history."""

    location_id: str
    official_name: str
    aliases: tuple[str, ...]
    rename_history: tuple[LocationRenameHistoryEntry, ...]
    recent_event_ids: tuple[str, ...]
    control_history: tuple[LocationControlHistoryEntry, ...] = ()


def _location_by_id(
    locations: Iterable[SupportsLocationHistory],
    location_id: str,
) -> SupportsLocationHistory:
    for location in locations:
        if location.id == location_id:
            return location
    raise KeyError(location_id)


def _record_location_id(record: WorldEventRecord) -> str | None:
    value = string_param(record, "location_id")
    if value is not None:
        return value
    if as_string(record.location_id) is not None:
        return record.location_id
    return first_record_location_id(record)


def _rename_names(record: WorldEventRecord, location_id: str) -> tuple[str, str] | None:
    old_name = string_param(record, "old_name")
    new_name = string_param(record, "new_name")
    if old_name is None:
        old_name = impact_string(
            record,
            value_key="old_value",
            attributes=("canonical_name", "name"),
            target_type="location",
            target_id=location_id,
        )
    if new_name is None:
        new_name = impact_string(
            record,
            value_key="new_value",
            attributes=("canonical_name", "name"),
            target_type="location",
            target_id=location_id,
        )
    if old_name is None or new_name is None:
        return None
    return old_name, new_name


def _rename_history_entries(
    event_records: Iterable[WorldEventRecord],
    location_id: str,
) -> tuple[LocationRenameHistoryEntry, ...]:
    entries: list[LocationRenameHistoryEntry] = []
    for record in event_records:
        if record.kind != "location_renamed":
            continue
        if _record_location_id(record) != location_id:
            continue
        names = _rename_names(record, location_id)
        if names is None:
            continue
        old_name, new_name = names
        entries.append(
            LocationRenameHistoryEntry(
                record_id=record.record_id,
                year=record.year,
                month=record.month,
                day=record.day,
                old_name=old_name,
                new_name=new_name,
                description=record.description,
                summary_key=record.summary_key,
                render_params=semantic_render_params(record),
            )
        )
    return tuple(entries)


def _is_location_control_record(record: WorldEventRecord) -> bool:
    return (
        record.kind in LOCATION_CONTROL_KINDS
        or record.kind.startswith("occupation_")
        or record.kind.endswith("_occupied")
        or record.kind.endswith("_liberated")
    )


def _control_faction_ids(record: WorldEventRecord, location_id: str) -> tuple[str | None, str | None]:
    old_faction_id = string_param(record, "old_faction_id", "previous_faction_id")
    new_faction_id = string_param(
        record,
        "new_faction_id",
        "controlling_faction_id",
        "occupying_faction_id",
        "faction_id",
    )
    if old_faction_id is None:
        old_faction_id = impact_string(
            record,
            value_key="old_value",
            attributes=("controlling_faction_id", "occupying_faction_id", "faction_id"),
            target_type="location",
            target_id=location_id,
        )
    if new_faction_id is None:
        new_faction_id = impact_string(
            record,
            value_key="new_value",
            attributes=("controlling_faction_id", "occupying_faction_id", "faction_id"),
            target_type="location",
            target_id=location_id,
        )
    if record.kind in {"location_liberated", "occupation_ended"} and new_faction_id is None:
        return old_faction_id, None
    return old_faction_id, new_faction_id


def _control_history_entries(
    event_records: Iterable[WorldEventRecord],
    location_id: str,
) -> tuple[LocationControlHistoryEntry, ...]:
    entries: list[LocationControlHistoryEntry] = []
    for record in event_records:
        if not _is_location_control_record(record):
            continue
        if location_id not in record_location_ids(record):
            continue
        old_faction_id, new_faction_id = _control_faction_ids(record, location_id)
        if old_faction_id is None and new_faction_id is None:
            continue
        entries.append(
            LocationControlHistoryEntry(
                record_id=record.record_id,
                kind=record.kind,
                year=record.year,
                month=record.month,
                day=record.day,
                old_faction_id=old_faction_id,
                new_faction_id=new_faction_id,
                description=record.description,
                summary_key=record.summary_key,
                render_params=semantic_render_params(record),
            )
        )
    return tuple(entries)


def build_location_history_projection(
    *,
    locations: Iterable[SupportsLocationHistory],
    event_records: Iterable[WorldEventRecord],
    location_id: str,
) -> LocationHistoryProjection:
    """Build the observation read model for a single location."""
    location = _location_by_id(locations, location_id)
    return LocationHistoryProjection(
        location_id=location.id,
        official_name=location.canonical_name,
        aliases=tuple(location.aliases),
        rename_history=_rename_history_entries(event_records, location.id),
        recent_event_ids=tuple(location.recent_event_ids),
        control_history=_control_history_entries(event_records, location.id),
    )

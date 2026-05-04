"""Headless war and occupation projection from canonical event records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from fantasy_simulator.event_models import WorldEventRecord

from ._record_helpers import (
    as_string,
    first_record_location_id,
    record_location_ids,
    semantic_render_params,
    string_param,
    string_params,
)


OCCUPATION_KINDS = {
    "location_faction_changed",
    "location_occupied",
    "location_liberated",
    "occupation_started",
    "occupation_ended",
}


@dataclass(frozen=True)
class WarMapEventEntry:
    """A war, conflict, or occupation event summarized for map observation."""

    record_id: str
    kind: str
    year: int
    month: int
    day: int
    location_ids: tuple[str, ...]
    faction_ids: tuple[str, ...]
    description: str
    summary_key: str = ""
    render_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class OccupationEntry:
    """A location control state transition derived only from event history."""

    record_id: str
    location_id: str
    previous_faction_id: str | None
    controlling_faction_id: str | None
    year: int
    month: int
    day: int
    status: str
    description: str
    summary_key: str = ""
    render_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WarMapProjection:
    """Read model for war/conflict events and current occupation state."""

    events: tuple[WarMapEventEntry, ...]
    occupation_history: tuple[OccupationEntry, ...]
    current_occupations: tuple[OccupationEntry, ...]
    affected_location_ids: tuple[str, ...]
    faction_ids: tuple[str, ...]


def _append_unique(values: list[str], value: str | None) -> None:
    if value is not None and value not in values:
        values.append(value)


def _is_war_or_occupation_record(record: WorldEventRecord) -> bool:
    kind = record.kind.casefold()
    return (
        kind in OCCUPATION_KINDS
        or kind.startswith("war_")
        or kind.startswith("conflict_")
        or kind.startswith("occupation_")
        or "occupation" in kind
        or kind.endswith("_occupied")
        or kind.endswith("_liberated")
    )


def _record_faction_ids(record: WorldEventRecord) -> tuple[str, ...]:
    values: list[str] = []
    for value in string_params(
        record,
        "faction_id",
        "faction_ids",
        "old_faction_id",
        "new_faction_id",
        "previous_faction_id",
        "controlling_faction_id",
        "occupying_faction_id",
        "attacker_faction_id",
        "defender_faction_id",
        "aggressor_faction_id",
        "target_faction_id",
        "belligerent_faction_ids",
        "participant_faction_ids",
        "side_a_faction_id",
        "side_b_faction_id",
        "winner_faction_id",
        "loser_faction_id",
    ):
        _append_unique(values, value)

    for impact in record.impacts:
        if impact.get("target_type") == "faction":
            _append_unique(values, as_string(impact.get("target_id")))
        attribute = as_string(impact.get("attribute")) or ""
        if "faction" in attribute:
            _append_unique(values, as_string(impact.get("old_value")))
            _append_unique(values, as_string(impact.get("new_value")))
    return tuple(values)


def _occupation_location_id(record: WorldEventRecord) -> str | None:
    return (
        string_param(record, "location_id", "occupied_location_id", "target_location_id")
        or first_record_location_id(record)
    )


def _occupation_faction_ids(record: WorldEventRecord) -> tuple[str | None, str | None]:
    previous_faction_id = string_param(record, "old_faction_id", "previous_faction_id")
    controlling_faction_id = string_param(
        record,
        "new_faction_id",
        "controlling_faction_id",
        "occupying_faction_id",
        "faction_id",
    )
    for impact in record.impacts:
        if impact.get("target_type") != "location":
            continue
        attribute = as_string(impact.get("attribute")) or ""
        if "faction" not in attribute:
            continue
        previous_faction_id = previous_faction_id or as_string(impact.get("old_value"))
        controlling_faction_id = controlling_faction_id or as_string(impact.get("new_value"))

    if record.kind in {"location_liberated", "occupation_ended"} and controlling_faction_id is None:
        return previous_faction_id, None
    return previous_faction_id, controlling_faction_id


def _occupation_entry(record: WorldEventRecord) -> OccupationEntry | None:
    if not (
        record.kind in OCCUPATION_KINDS
        or record.kind.startswith("occupation_")
        or record.kind.endswith("_occupied")
        or record.kind.endswith("_liberated")
    ):
        return None
    location_id = _occupation_location_id(record)
    if location_id is None:
        return None
    previous_faction_id, controlling_faction_id = _occupation_faction_ids(record)
    if previous_faction_id is None and controlling_faction_id is None:
        return None
    return OccupationEntry(
        record_id=record.record_id,
        location_id=location_id,
        previous_faction_id=previous_faction_id,
        controlling_faction_id=controlling_faction_id,
        year=record.year,
        month=record.month,
        day=record.day,
        status="unoccupied" if controlling_faction_id is None else "occupied",
        description=record.description,
        summary_key=record.summary_key,
        render_params=semantic_render_params(record),
    )


def build_war_map_projection(
    *,
    event_records: Iterable[WorldEventRecord],
) -> WarMapProjection:
    """Build a war/occupation read model using only canonical event records."""
    events: list[WarMapEventEntry] = []
    occupation_history: list[OccupationEntry] = []
    current_by_location: dict[str, OccupationEntry] = {}
    affected_location_ids: list[str] = []
    faction_ids: list[str] = []

    for record in event_records:
        if not _is_war_or_occupation_record(record):
            continue

        location_ids = record_location_ids(record)
        record_faction_ids = _record_faction_ids(record)
        for location_id in location_ids:
            _append_unique(affected_location_ids, location_id)
        for faction_id in record_faction_ids:
            _append_unique(faction_ids, faction_id)

        events.append(
            WarMapEventEntry(
                record_id=record.record_id,
                kind=record.kind,
                year=record.year,
                month=record.month,
                day=record.day,
                location_ids=location_ids,
                faction_ids=record_faction_ids,
                description=record.description,
                summary_key=record.summary_key,
                render_params=semantic_render_params(record),
            )
        )

        occupation = _occupation_entry(record)
        if occupation is None:
            continue
        occupation_history.append(occupation)
        _append_unique(affected_location_ids, occupation.location_id)
        _append_unique(faction_ids, occupation.previous_faction_id)
        _append_unique(faction_ids, occupation.controlling_faction_id)
        if occupation.controlling_faction_id is None:
            current_by_location.pop(occupation.location_id, None)
        else:
            current_by_location[occupation.location_id] = occupation

    return WarMapProjection(
        events=tuple(events),
        occupation_history=tuple(occupation_history),
        current_occupations=tuple(current_by_location[location_id] for location_id in sorted(current_by_location)),
        affected_location_ids=tuple(affected_location_ids),
        faction_ids=tuple(faction_ids),
    )

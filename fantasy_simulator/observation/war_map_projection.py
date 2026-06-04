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
    """A location control state transition or seeded current control state."""

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
class WarRelationshipEntry:
    """An active faction war relationship derived from event history."""

    record_id: str
    aggressor_faction_id: str
    target_faction_id: str
    faction_ids: tuple[str, str]
    location_ids: tuple[str, ...]
    year: int
    month: int
    day: int
    description: str
    summary_key: str = ""
    render_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WarMapProjection:
    """Read model for war/conflict events and current occupation state."""

    events: tuple[WarMapEventEntry, ...]
    occupation_history: tuple[OccupationEntry, ...]
    current_occupations: tuple[OccupationEntry, ...]
    active_wars: tuple[WarRelationshipEntry, ...]
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


def _war_pair(record: WorldEventRecord) -> tuple[str, str] | None:
    aggressor = string_param(record, "aggressor_faction_id")
    target = string_param(record, "target_faction_id")
    if aggressor is None or target is None:
        faction_ids = _record_faction_ids(record)
        if len(faction_ids) >= 2:
            aggressor, target = faction_ids[0], faction_ids[1]
    if aggressor is None or target is None or aggressor == target:
        return None
    first, second = sorted((aggressor, target))
    return first, second


def _war_relationship_entry(record: WorldEventRecord) -> WarRelationshipEntry | None:
    pair = _war_pair(record)
    if pair is None:
        return None
    aggressor = string_param(record, "aggressor_faction_id") or pair[0]
    target = string_param(record, "target_faction_id") or pair[1]
    return WarRelationshipEntry(
        record_id=record.record_id,
        aggressor_faction_id=aggressor,
        target_faction_id=target,
        faction_ids=(pair[0], pair[1]),
        location_ids=record_location_ids(record),
        year=record.year,
        month=record.month,
        day=record.day,
        description=record.description,
        summary_key=record.summary_key,
        render_params=semantic_render_params(record),
    )


def _authored_relationship_status(relationship: Any) -> str:
    return str(getattr(relationship, "status", "")).strip()


def _authored_relationship_pair(relationship: Any) -> tuple[str, str] | None:
    faction_a_id = str(getattr(relationship, "faction_a_id", "")).strip()
    faction_b_id = str(getattr(relationship, "faction_b_id", "")).strip()
    if not faction_a_id or not faction_b_id or faction_a_id == faction_b_id:
        return None
    first, second = sorted((faction_a_id, faction_b_id))
    return first, second


def _authored_war_relationship_entry(relationship: Any) -> WarRelationshipEntry | None:
    if _authored_relationship_status(relationship) != "war":
        return None
    pair = _authored_relationship_pair(relationship)
    if pair is None:
        return None
    faction_a_id = str(getattr(relationship, "faction_a_id")).strip()
    faction_b_id = str(getattr(relationship, "faction_b_id")).strip()
    location_ids = tuple(
        str(location_id).strip()
        for location_id in getattr(relationship, "location_ids", ())
        if str(location_id).strip()
    )
    record_id = f"bundle:faction_relationship:{pair[0]}:{pair[1]}"
    description = str(getattr(relationship, "description", "")).strip()
    if not description:
        description = f"{faction_a_id} and {faction_b_id} are already at war."
    return WarRelationshipEntry(
        record_id=record_id,
        aggressor_faction_id=faction_a_id,
        target_faction_id=faction_b_id,
        faction_ids=(pair[0], pair[1]),
        location_ids=location_ids,
        year=0,
        month=0,
        day=0,
        description=description,
        summary_key="dashboard_authored_active_war",
        render_params={
            "aggressor_faction_id": faction_a_id,
            "target_faction_id": faction_b_id,
            "location_ids": list(location_ids),
        },
    )


def build_war_map_projection(
    *,
    event_records: Iterable[WorldEventRecord],
    faction_relationships: Iterable[Any] = (),
    current_locations: Iterable[Any] = (),
) -> WarMapProjection:
    """Build a war/occupation read model from authored baselines and canonical records."""
    events: list[WarMapEventEntry] = []
    occupation_history: list[OccupationEntry] = []
    current_by_location: dict[str, OccupationEntry] = {}
    active_wars_by_pair: dict[tuple[str, str], WarRelationshipEntry] = {}
    affected_location_ids: list[str] = []
    faction_ids: list[str] = []

    _seed_authored_war_relationships(
        faction_relationships,
        active_wars_by_pair=active_wars_by_pair,
        affected_location_ids=affected_location_ids,
        faction_ids=faction_ids,
    )
    _seed_current_location_controls(
        current_locations,
        current_by_location=current_by_location,
        affected_location_ids=affected_location_ids,
        faction_ids=faction_ids,
    )

    for record in event_records:
        if not _is_war_or_occupation_record(record):
            continue
        _apply_war_map_record(
            record,
            events=events,
            occupation_history=occupation_history,
            current_by_location=current_by_location,
            active_wars_by_pair=active_wars_by_pair,
            affected_location_ids=affected_location_ids,
            faction_ids=faction_ids,
        )

    return WarMapProjection(
        events=tuple(events),
        occupation_history=tuple(occupation_history),
        current_occupations=tuple(current_by_location[location_id] for location_id in sorted(current_by_location)),
        active_wars=tuple(active_wars_by_pair[pair] for pair in sorted(active_wars_by_pair)),
        affected_location_ids=tuple(affected_location_ids),
        faction_ids=tuple(faction_ids),
    )


def _seed_current_location_controls(
    current_locations: Iterable[Any],
    *,
    current_by_location: dict[str, OccupationEntry],
    affected_location_ids: list[str],
    faction_ids: list[str],
) -> None:
    for location in current_locations:
        entry = _current_location_control_entry(location)
        if entry is None:
            continue
        current_by_location[entry.location_id] = entry
        _append_unique(affected_location_ids, entry.location_id)
        _append_unique(faction_ids, entry.controlling_faction_id)


def _current_location_control_entry(location: Any) -> OccupationEntry | None:
    location_id = str(getattr(location, "id", "")).strip()
    faction_id = str(getattr(location, "controlling_faction_id", "") or "").strip()
    if not location_id or not faction_id:
        return None
    record_id = f"state:location_control:{location_id}"
    description = f"{location_id} is controlled by {faction_id}."
    return OccupationEntry(
        record_id=record_id,
        location_id=location_id,
        previous_faction_id=None,
        controlling_faction_id=faction_id,
        year=0,
        month=0,
        day=0,
        status="controlled",
        description=description,
        summary_key="dashboard_initial_site_control",
        render_params={
            "location_id": location_id,
            "controlling_faction_id": faction_id,
        },
    )


def _seed_authored_war_relationships(
    faction_relationships: Iterable[Any],
    *,
    active_wars_by_pair: dict[tuple[str, str], WarRelationshipEntry],
    affected_location_ids: list[str],
    faction_ids: list[str],
) -> None:
    for relationship in faction_relationships:
        relationship_entry = _authored_war_relationship_entry(relationship)
        if relationship_entry is None:
            continue
        active_wars_by_pair[relationship_entry.faction_ids] = relationship_entry
        for faction_id in relationship_entry.faction_ids:
            _append_unique(faction_ids, faction_id)
        for location_id in relationship_entry.location_ids:
            _append_unique(affected_location_ids, location_id)


def _apply_war_map_record(
    record: WorldEventRecord,
    *,
    events: list[WarMapEventEntry],
    occupation_history: list[OccupationEntry],
    current_by_location: dict[str, OccupationEntry],
    active_wars_by_pair: dict[tuple[str, str], WarRelationshipEntry],
    affected_location_ids: list[str],
    faction_ids: list[str],
) -> None:
    location_ids = record_location_ids(record)
    record_faction_ids = _record_faction_ids(record)
    for location_id in location_ids:
        _append_unique(affected_location_ids, location_id)
    for faction_id in record_faction_ids:
        _append_unique(faction_ids, faction_id)

    events.append(_war_map_event_entry(record, location_ids=location_ids, faction_ids=record_faction_ids))
    _apply_war_relationship_record(record, active_wars_by_pair)
    _apply_occupation_record(
        record,
        occupation_history=occupation_history,
        current_by_location=current_by_location,
        affected_location_ids=affected_location_ids,
        faction_ids=faction_ids,
    )


def _war_map_event_entry(
    record: WorldEventRecord,
    *,
    location_ids: tuple[str, ...],
    faction_ids: tuple[str, ...],
) -> WarMapEventEntry:
    return WarMapEventEntry(
        record_id=record.record_id,
        kind=record.kind,
        year=record.year,
        month=record.month,
        day=record.day,
        location_ids=location_ids,
        faction_ids=faction_ids,
        description=record.description,
        summary_key=record.summary_key,
        render_params=semantic_render_params(record),
    )


def _apply_war_relationship_record(
    record: WorldEventRecord,
    active_wars_by_pair: dict[tuple[str, str], WarRelationshipEntry],
) -> None:
    if record.kind == "war_declared":
        relationship = _war_relationship_entry(record)
        if relationship is not None:
            active_wars_by_pair[relationship.faction_ids] = relationship
    elif record.kind == "war_ended":
        pair = _war_pair(record)
        if pair is not None:
            active_wars_by_pair.pop(pair, None)


def _apply_occupation_record(
    record: WorldEventRecord,
    *,
    occupation_history: list[OccupationEntry],
    current_by_location: dict[str, OccupationEntry],
    affected_location_ids: list[str],
    faction_ids: list[str],
) -> None:
    occupation = _occupation_entry(record)
    if occupation is None:
        return
    occupation_history.append(occupation)
    _append_unique(affected_location_ids, occupation.location_id)
    _append_unique(faction_ids, occupation.previous_faction_id)
    _append_unique(faction_ids, occupation.controlling_faction_id)
    if occupation.controlling_faction_id is None:
        current_by_location.pop(occupation.location_id, None)
    else:
        current_by_location[occupation.location_id] = occupation

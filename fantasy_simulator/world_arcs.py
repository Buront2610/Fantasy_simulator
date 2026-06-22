"""Helpers for persistent world-arc management."""

from __future__ import annotations

from typing import Any, Iterable, List, Optional

from .event_models import WorldEventRecord
from .world_arc import WorldArc


WAR_LOCATION_FALLBACK_KINDS = {
    "war_battle",
    "war_ended",
    "location_occupied",
    "location_liberated",
    "location_faction_changed",
    "route_blocked",
    "route_reopened",
}


def war_pair(aggressor_faction_id: str, target_faction_id: str) -> tuple[str, str]:
    """Return the order-independent identity for a faction war."""
    first, second = sorted((aggressor_faction_id, target_faction_id))
    return first, second


def active_world_arcs(world: Any, *, kind: str = "") -> list[WorldArc]:
    """Return active arcs for a world, optionally filtered by kind."""
    arcs = getattr(world, "world_arcs", [])
    return [
        arc for arc in arcs
        if isinstance(arc, WorldArc) and arc.is_active and (not kind or arc.kind == kind)
    ]


def find_active_war_arc(
    world: Any,
    aggressor_faction_id: str,
    target_faction_id: str,
) -> Optional[WorldArc]:
    """Find the active war arc matching two factions."""
    expected = war_pair(aggressor_faction_id, target_faction_id)
    for arc in active_world_arcs(world, kind="war"):
        if tuple(sorted(arc.participant_faction_ids[:2])) == expected:
            return arc
    return None


def create_war_arc_from_record(world: Any, record: WorldEventRecord) -> WorldArc:
    """Create or reuse a persistent war arc for a war declaration record."""
    params = record.render_params
    aggressor = str(params.get("aggressor_faction_id", ""))
    target = str(params.get("target_faction_id", ""))
    existing = find_active_war_arc(world, aggressor, target)
    if existing is not None:
        existing.touch(year=record.year, month=record.month, day=record.day, record_id=record.record_id)
        return existing

    arc = WorldArc(
        arc_id=f"arc_war_{record.record_id}",
        kind="war",
        phase="active",
        start_year=record.year,
        start_month=record.month,
        start_day=record.day,
        last_year=record.year,
        last_month=record.month,
        last_day=record.day,
        cause_event_id=record.record_id,
        related_event_ids=[record.record_id],
        location_ids=tuple(_string_values(params.get("location_ids", []))),
        participant_faction_ids=(aggressor, target),
        metadata={
            "aggressor_faction_id": aggressor,
            "target_faction_id": target,
            "declaration_record_id": record.record_id,
            "cause_key": str(params.get("cause_key", "")),
        },
    )
    world.world_arcs.append(arc)
    return arc


def close_war_arc_from_record(world: Any, record: WorldEventRecord) -> Optional[WorldArc]:
    """Mark the matching active war arc as resolved by an ending record."""
    params = record.render_params
    aggressor = str(params.get("aggressor_faction_id", ""))
    target = str(params.get("target_faction_id", ""))
    arc = find_active_war_arc(world, aggressor, target)
    if arc is None:
        return None
    arc.phase = "resolved"
    arc.metadata["resolution_record_id"] = record.record_id
    arc.metadata["resolution_cause_key"] = str(params.get("cause_key", ""))
    arc.touch(year=record.year, month=record.month, day=record.day, record_id=record.record_id)
    return arc


def attach_record_to_arc(arc: WorldArc, record: WorldEventRecord) -> None:
    """Append a world-change record to an arc's durable timeline."""
    arc.touch(year=record.year, month=record.month, day=record.day, record_id=record.record_id)


def last_arc_event_id(arc: WorldArc) -> str | None:
    """Return the most recent related event id for cause-linking."""
    if arc.related_event_ids:
        return arc.related_event_ids[-1]
    return arc.cause_event_id


def reconstruct_world_arcs_from_records(records: Iterable[dict[str, Any] | WorldEventRecord]) -> List[WorldArc]:
    """Build v9 world arcs from legacy canonical event records."""
    arcs: list[WorldArc] = []
    active_by_pair: dict[tuple[str, str], WorldArc] = {}
    for raw_record in records:
        record = raw_record if isinstance(raw_record, WorldEventRecord) else WorldEventRecord.from_dict(raw_record)
        params = record.render_params
        if record.kind == "war_declared":
            aggressor = str(params.get("aggressor_faction_id", ""))
            target = str(params.get("target_faction_id", ""))
            if not aggressor or not target or aggressor == target:
                continue
            arc = _war_arc_from_declaration_record(record)
            arcs.append(arc)
            active_by_pair[war_pair(aggressor, target)] = arc
            continue
        if record.kind == "war_ended":
            aggressor = str(params.get("aggressor_faction_id", ""))
            target = str(params.get("target_faction_id", ""))
            arc = active_by_pair.pop(war_pair(aggressor, target), None)
            if arc is None:
                continue
            arc.phase = "resolved"
            arc.metadata["resolution_record_id"] = record.record_id
            arc.touch(year=record.year, month=record.month, day=record.day, record_id=record.record_id)
            continue
        arc = _record_arc_match(record, active_by_pair.values())
        if arc is not None:
            arc.touch(year=record.year, month=record.month, day=record.day, record_id=record.record_id)
    return arcs


def _war_arc_from_declaration_record(record: WorldEventRecord) -> WorldArc:
    params = record.render_params
    aggressor = str(params.get("aggressor_faction_id", ""))
    target = str(params.get("target_faction_id", ""))
    return WorldArc(
        arc_id=f"arc_war_{record.record_id}",
        kind="war",
        phase="active",
        start_year=record.year,
        start_month=record.month,
        start_day=record.day,
        last_year=record.year,
        last_month=record.month,
        last_day=record.day,
        cause_event_id=record.record_id,
        related_event_ids=[record.record_id],
        location_ids=tuple(_string_values(params.get("location_ids", []))),
        participant_faction_ids=(aggressor, target),
        metadata={
            "aggressor_faction_id": aggressor,
            "target_faction_id": target,
            "declaration_record_id": record.record_id,
            "cause_key": str(params.get("cause_key", "")),
        },
    )


def _record_arc_match(record: WorldEventRecord, arcs: Iterable[WorldArc]) -> Optional[WorldArc]:
    params = record.render_params
    arc_id = params.get("arc_id")
    if isinstance(arc_id, str):
        for arc in arcs:
            if arc.arc_id == arc_id:
                return arc
    cause_event_id = params.get("cause_event_id")
    if isinstance(cause_event_id, str):
        for arc in arcs:
            if cause_event_id in arc.related_event_ids or cause_event_id == arc.cause_event_id:
                return arc
    if record.kind not in WAR_LOCATION_FALLBACK_KINDS and "war" not in record.tags:
        return None
    record_locations = set(_string_values(params.get("location_ids", [])))
    if isinstance(params.get("location_id"), str):
        record_locations.add(str(params["location_id"]))
    for arc in arcs:
        if record_locations.intersection(arc.location_ids):
            return arc
    return None


def _string_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, str)]

"""World-state pressure applied to adventure routes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..i18n import tr
from ..world_arc.management import active_world_arcs, war_pair


@dataclass(frozen=True)
class AdventureWorldPressure:
    danger_bonus: int = 0
    detail_lines: tuple[str, ...] = ()


def adventure_world_pressure(world: Any, origin_id: str, destination_id: str) -> AdventureWorldPressure:
    """Return route pressure from blocked roads and active war fronts."""
    details: list[str] = []
    danger_bonus = 0
    if destination_id in active_war_location_ids(world):
        danger_bonus += 20
        details.append(tr("detail_adventure_warfront_pressure", destination=world.location_name(destination_id)))

    blocked_endpoints = _blocked_route_endpoint_ids(world)
    pressure_locations = [
        location_id
        for location_id in (origin_id, destination_id)
        if location_id in blocked_endpoints
    ]
    for location_id in dict.fromkeys(pressure_locations):
        danger_bonus += 10
        details.append(tr("detail_adventure_blocked_route_pressure", location=world.location_name(location_id)))

    return AdventureWorldPressure(danger_bonus=danger_bonus, detail_lines=tuple(details))


def active_war_location_ids(world: Any) -> set[str]:
    """Return locations currently named by active war arcs or open war records."""
    location_ids: set[str] = set()
    for arc in active_world_arcs(world, kind="war"):
        location_ids.update(arc.location_ids)
    location_ids.update(_active_war_record_locations(world))
    return location_ids


def _active_war_record_locations(world: Any) -> set[str]:
    active_by_pair: dict[tuple[str, str], set[str]] = {}
    for record in getattr(world, "event_records", []):
        params = getattr(record, "render_params", {})
        aggressor = str(params.get("aggressor_faction_id", ""))
        target = str(params.get("target_faction_id", ""))
        if not aggressor or not target or aggressor == target:
            continue
        pair = war_pair(aggressor, target)
        if getattr(record, "kind", "") == "war_declared":
            active_by_pair[pair] = set(_record_location_ids(record))
        elif getattr(record, "kind", "") == "war_ended":
            active_by_pair.pop(pair, None)
    return set().union(*active_by_pair.values()) if active_by_pair else set()


def _record_location_ids(record: Any) -> list[str]:
    values: list[str] = []
    location_id = getattr(record, "location_id", None)
    if isinstance(location_id, str) and location_id:
        values.append(location_id)
    params = getattr(record, "render_params", {})
    for value in params.get("location_ids", []):
        if isinstance(value, str) and value:
            values.append(value)
    return list(dict.fromkeys(values))


def _blocked_route_endpoint_ids(world: Any) -> set[str]:
    endpoints: set[str] = set()
    for route in getattr(world, "routes", []):
        if not getattr(route, "blocked", False):
            continue
        endpoints.add(str(getattr(route, "from_site_id", "")))
        endpoints.add(str(getattr(route, "to_site_id", "")))
    endpoints.discard("")
    return endpoints

"""Small world-mutation helpers for PR-K style dynamic changes."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def apply_location_rename(
    location_index: Mapping[str, Any],
    *,
    location_id: str,
    new_name: str,
    max_aliases: int,
) -> str:
    """Rename a location while preserving the previous canonical name as an alias."""
    location = location_index.get(location_id)
    if location is None:
        raise KeyError(location_id)
    normalized_name = new_name.strip()
    if not normalized_name:
        raise ValueError("new_name must not be blank")

    old_name = location.canonical_name
    if old_name == normalized_name:
        return old_name
    if old_name and old_name not in location.aliases and len(location.aliases) < max_aliases:
        location.aliases.append(old_name)
    location.canonical_name = normalized_name
    return old_name


def apply_controlling_faction(
    location_index: Mapping[str, Any],
    *,
    location_id: str,
    faction_id: str | None,
) -> str | None:
    """Set a location's controlling faction and return the previous value."""
    location = location_index.get(location_id)
    if location is None:
        raise KeyError(location_id)
    old_faction_id = location.controlling_faction_id
    location.controlling_faction_id = faction_id.strip() if isinstance(faction_id, str) and faction_id.strip() else None
    return old_faction_id


def apply_route_blocked_state(
    routes: Iterable[Any],
    *,
    route_id: str,
    blocked: bool,
) -> bool:
    """Set a route blocked flag and return the previous value."""
    if not isinstance(blocked, bool):
        raise TypeError("blocked must be a bool")
    route = route_by_id(routes, route_id=route_id)
    old_blocked = bool(route.blocked)
    route.blocked = blocked
    return old_blocked


def route_by_id(routes: Iterable[Any], *, route_id: str) -> Any:
    """Return a route by ID or raise ``KeyError``."""
    for route in routes:
        if route.route_id == route_id:
            return route
    raise KeyError(route_id)

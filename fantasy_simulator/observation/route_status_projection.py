"""Route status projection for PR-K world-change observation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Protocol

from fantasy_simulator.event_models import WorldEventRecord

from ._record_helpers import as_string, impact_value, record_location_ids, semantic_render_params, string_param


ROUTE_STATUS_KINDS = {"route_blocked", "route_reopened"}


class SupportsRouteStatus(Protocol):
    route_id: str
    from_site_id: str
    to_site_id: str
    blocked: bool


@dataclass(frozen=True)
class RouteStatusHistoryEntry:
    """A route status event summarized for observation."""

    record_id: str
    kind: str
    year: int
    month: int
    day: int
    blocked: bool | None
    description: str
    summary_key: str = ""
    render_params: dict[str, Any] = field(default_factory=dict)
    from_location_id: str = ""
    to_location_id: str = ""


@dataclass(frozen=True)
class RouteStatusProjection:
    """Read model for one route's current status and route-change history."""

    route_id: str
    from_location_id: str
    to_location_id: str
    status: str
    blocked: bool
    history: tuple[RouteStatusHistoryEntry, ...]


def _route_attr(route: SupportsRouteStatus, *names: str) -> str:
    for name in names:
        value = as_string(getattr(route, name, None))
        if value is not None:
            return value
    raise AttributeError(f"route is missing one of: {', '.join(names)}")


def _route_by_id(routes: Iterable[SupportsRouteStatus], route_id: str) -> SupportsRouteStatus:
    for route in routes:
        if _route_attr(route, "route_id", "id") == route_id:
            return route
    raise KeyError(route_id)


def _bool_value(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"true", "blocked", "closed", "1", "yes"}:
            return True
        if lowered in {"false", "open", "reopened", "0", "no"}:
            return False
    return None


def _blocked_value(record: WorldEventRecord) -> bool | None:
    value = _bool_value(
        impact_value(
            record,
            value_key="new_value",
            attributes=("blocked", "status"),
            target_type="route",
        )
    )
    if value is not None:
        return value
    if record.kind == "route_blocked":
        return True
    if record.kind == "route_reopened":
        return False
    return None


def _record_route_id(record: WorldEventRecord) -> str | None:
    route_id = string_param(record, "route_id")
    if route_id is not None:
        return route_id
    for impact in record.impacts:
        if impact.get("target_type") != "route":
            continue
        value = as_string(impact.get("target_id"))
        if value is not None:
            return value
    return None


def _route_endpoint_ids(record: WorldEventRecord) -> tuple[str, str]:
    from_location_id = string_param(record, "from_location_id")
    to_location_id = string_param(record, "to_location_id")
    if from_location_id is not None and to_location_id is not None:
        return from_location_id, to_location_id

    endpoint_location_ids = record.render_params.get("endpoint_location_ids")
    if isinstance(endpoint_location_ids, list):
        endpoints = [value for value in (as_string(item) for item in endpoint_location_ids) if value is not None]
        if len(endpoints) >= 2:
            return endpoints[0], endpoints[1]

    location_ids = record_location_ids(record)
    if len(location_ids) >= 2:
        return location_ids[0], location_ids[1]
    if len(location_ids) == 1:
        return location_ids[0], ""
    return "", ""


def _route_history_entries(
    event_records: Iterable[WorldEventRecord],
    route_id: str,
) -> tuple[RouteStatusHistoryEntry, ...]:
    entries: list[RouteStatusHistoryEntry] = []
    for record in event_records:
        if record.kind not in ROUTE_STATUS_KINDS:
            continue
        if _record_route_id(record) != route_id:
            continue
        from_location_id, to_location_id = _route_endpoint_ids(record)
        entries.append(
            RouteStatusHistoryEntry(
                record_id=record.record_id,
                kind=record.kind,
                year=record.year,
                month=record.month,
                day=record.day,
                blocked=_blocked_value(record),
                description=record.description,
                summary_key=record.summary_key,
                render_params=semantic_render_params(record),
                from_location_id=from_location_id,
                to_location_id=to_location_id,
            )
        )
    return tuple(entries)


def build_route_status_projection(
    *,
    routes: Iterable[SupportsRouteStatus],
    event_records: Iterable[WorldEventRecord],
    route_id: str,
) -> RouteStatusProjection:
    """Build the observation read model for a single route."""
    route = _route_by_id(routes, route_id)
    blocked = bool(getattr(route, "blocked", False))
    from_location_id = _route_attr(route, "from_site_id", "from_location_id")
    to_location_id = _route_attr(route, "to_site_id", "to_location_id")
    return RouteStatusProjection(
        route_id=_route_attr(route, "route_id", "id"),
        from_location_id=from_location_id,
        to_location_id=to_location_id,
        status="blocked" if blocked else "open",
        blocked=blocked,
        history=_route_history_entries(event_records, route_id),
    )

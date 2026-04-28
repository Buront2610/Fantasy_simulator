"""Route lookup and prioritization helpers for regional maps."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from .map_view_models import MapCellInfo, RouteRenderInfo


_UNKNOWN_ROUTE_TYPE_PRIORITY = 99
_REACHABILITY_OPEN = 0
_REACHABILITY_VISIBLE = 1
_REACHABILITY_BLOCKED = 2
_ROUTE_TYPE_PRIORITY: Dict[str, int] = {
    "road": 0,
    "mountain_pass": 1,
    "river": 2,
    "trail": 3,
}


def route_endpoint_name(cells_by_id: Dict[str, MapCellInfo], location_id: str) -> str:
    cell = cells_by_id.get(location_id)
    return cell.canonical_name if cell is not None else location_id


def route_other_endpoint(route: RouteRenderInfo, center_location_id: str) -> str:
    if route.from_site_id == center_location_id:
        return route.to_site_id
    return route.from_site_id


def pick_standout_route(
    region_routes: List[RouteRenderInfo],
    center_location_id: str,
    cells_by_id: Dict[str, MapCellInfo],
) -> Optional[RouteRenderInfo]:
    open_routes = [route for route in region_routes if not route.blocked]
    if not open_routes:
        return None
    return min(
        open_routes,
        key=lambda route: (
            _ROUTE_TYPE_PRIORITY.get(route.route_type, _UNKNOWN_ROUTE_TYPE_PRIORITY),
            route_endpoint_name(cells_by_id, route_other_endpoint(route, center_location_id)).lower(),
        ),
    )


def pick_blocked_route_notice(
    region_routes: List[RouteRenderInfo],
    center_location_id: str,
    cells_by_id: Dict[str, MapCellInfo],
) -> Optional[RouteRenderInfo]:
    blocked_routes = [route for route in region_routes if route.blocked]
    if not blocked_routes:
        return None
    return min(
        blocked_routes,
        key=lambda route: (
            _ROUTE_TYPE_PRIORITY.get(route.route_type, _UNKNOWN_ROUTE_TYPE_PRIORITY),
            route_endpoint_name(cells_by_id, route_other_endpoint(route, center_location_id)).lower(),
        ),
    )


def region_reachability_tier(
    location_id: str,
    connected_open_ids: Set[str],
    connected_blocked_ids: Set[str],
) -> int:
    if location_id in connected_open_ids:
        return _REACHABILITY_OPEN
    if location_id not in connected_blocked_ids:
        return _REACHABILITY_VISIBLE
    return _REACHABILITY_BLOCKED


def center_route_connections(
    routes: List[RouteRenderInfo],
    center_location_id: str,
) -> Tuple[Set[str], Set[str]]:
    connected_open_ids: Set[str] = set()
    connected_blocked_ids: Set[str] = set()
    for route in routes:
        if route.from_site_id == center_location_id:
            if route.blocked:
                connected_blocked_ids.add(route.to_site_id)
            else:
                connected_open_ids.add(route.to_site_id)
        elif route.to_site_id == center_location_id:
            if route.blocked:
                connected_blocked_ids.add(route.from_site_id)
            else:
                connected_open_ids.add(route.from_site_id)
    return connected_open_ids, connected_blocked_ids


def center_region_routes(routes: List[RouteRenderInfo], center_location_id: str) -> List[RouteRenderInfo]:
    return [
        route for route in routes
        if route.from_site_id == center_location_id or route.to_site_id == center_location_id
    ]

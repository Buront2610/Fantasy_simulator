"""Topology query helpers for the World aggregate."""

from __future__ import annotations

from collections import deque
from typing import Callable, List, Mapping, Protocol, Sequence, Tuple

from .world_topology import (
    PROPAGATION_TOPOLOGY_GRID,
    PROPAGATION_TOPOLOGY_TRAVEL,
    grid_neighbor_ids,
    route_neighbor_ids,
)


class SupportsTopologyLocation(Protocol):
    id: str
    x: int
    y: int


class SupportsRouteEdge(Protocol):
    blocked: bool

    def other_end(self, site_id: str) -> str | None: ...


LocationIndex = Mapping[str, SupportsTopologyLocation]
GridIndex = Mapping[Tuple[int, int], SupportsTopologyLocation]
RouteLookup = Callable[[str], Sequence[SupportsRouteEdge]]


def locations_for_ids(
    location_ids: List[str],
    *,
    location_index: LocationIndex,
) -> List[SupportsTopologyLocation]:
    """Return live locations for IDs that still exist in the current world."""
    return [
        location_index[location_id]
        for location_id in location_ids
        if location_id in location_index
    ]


def connected_site_ids(
    location_id: str,
    *,
    get_routes_for_site: RouteLookup,
) -> List[str]:
    """Return sorted site IDs connected by currently passable routes."""
    return sorted(route_neighbor_ids(location_id, routes=get_routes_for_site(location_id)))


def grid_neighboring_locations(
    location_id: str,
    *,
    location_index: LocationIndex,
    grid: GridIndex,
) -> List[SupportsTopologyLocation]:
    """Return adjacency by physical map grid, regardless of route state."""
    neighbor_ids = grid_neighbor_ids(location_id, location_index=location_index, grid=grid)
    return locations_for_ids(neighbor_ids, location_index=location_index)


def travel_neighboring_locations(
    location_id: str,
    *,
    location_index: LocationIndex,
    grid: GridIndex,
    routes: Sequence[SupportsRouteEdge],
    route_graph_explicit: bool,
    get_routes_for_site: RouteLookup,
) -> List[SupportsTopologyLocation]:
    """Return neighbors reachable for travel using the travel topology contract."""
    if routes:
        neighbor_ids = connected_site_ids(location_id, get_routes_for_site=get_routes_for_site)
    elif route_graph_explicit:
        neighbor_ids = []
    else:
        neighbor_ids = grid_neighbor_ids(location_id, location_index=location_index, grid=grid)
    return locations_for_ids(neighbor_ids, location_index=location_index)


def propagation_neighboring_locations(
    location_id: str,
    *,
    location_index: LocationIndex,
    grid: GridIndex,
    routes: Sequence[SupportsRouteEdge],
    route_graph_explicit: bool,
    get_routes_for_site: RouteLookup,
    topology_mode: str = PROPAGATION_TOPOLOGY_TRAVEL,
    include_blocked_routes: bool = False,
) -> List[SupportsTopologyLocation]:
    """Return neighbors used for state propagation."""
    if topology_mode == PROPAGATION_TOPOLOGY_TRAVEL:
        if routes:
            neighbor_ids = sorted(
                route_neighbor_ids(
                    location_id,
                    routes=get_routes_for_site(location_id),
                    include_blocked=include_blocked_routes,
                )
            )
        elif route_graph_explicit:
            neighbor_ids = []
        else:
            neighbor_ids = grid_neighbor_ids(location_id, location_index=location_index, grid=grid)
    elif topology_mode == PROPAGATION_TOPOLOGY_GRID:
        neighbor_ids = grid_neighbor_ids(location_id, location_index=location_index, grid=grid)
    else:
        raise ValueError(f"Unsupported propagation topology mode: {topology_mode}")
    return locations_for_ids(neighbor_ids, location_index=location_index)


def reachable_location_ids(
    location_id: str,
    *,
    location_index: LocationIndex,
    get_travel_neighbors: Callable[[str], List[SupportsTopologyLocation]],
) -> List[str]:
    """Return all reachable location IDs from ``location_id``."""
    if location_id not in location_index:
        return []

    visited = {location_id}
    queue = deque([location_id])
    reachable: List[str] = []

    while queue:
        current = queue.popleft()
        for neighbor in get_travel_neighbors(current):
            if neighbor.id in visited or neighbor.id not in location_index:
                continue
            visited.add(neighbor.id)
            reachable.append(neighbor.id)
            queue.append(neighbor.id)

    return reachable

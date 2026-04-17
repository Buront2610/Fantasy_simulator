"""Neighbor-topology helpers for world travel and state propagation.

This module makes the topology contract explicit:
- travel neighbors follow open routes when route data exists, otherwise grid adjacency
- propagation neighbors may intentionally choose a different topology
"""

from __future__ import annotations

from typing import Iterable, List, Mapping, Protocol, Tuple


PROPAGATION_TOPOLOGY_TRAVEL = "travel"
PROPAGATION_TOPOLOGY_GRID = "grid"
VALID_PROPAGATION_TOPOLOGIES = (
    PROPAGATION_TOPOLOGY_TRAVEL,
    PROPAGATION_TOPOLOGY_GRID,
)


class SupportsTopologyLocation(Protocol):
    id: str
    x: int
    y: int


class SupportsRouteEdge(Protocol):
    blocked: bool

    def other_end(self, site_id: str) -> str | None: ...


def grid_neighbor_ids(
    location_id: str,
    *,
    location_index: Mapping[str, SupportsTopologyLocation],
    grid: Mapping[Tuple[int, int], SupportsTopologyLocation],
) -> List[str]:
    """Return cardinally adjacent site IDs for the given location."""
    source = location_index.get(location_id)
    if source is None:
        return []

    neighbors: List[str] = []
    for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
        loc = grid.get((source.x + dx, source.y + dy))
        if loc is not None:
            neighbors.append(loc.id)
    return neighbors


def route_neighbor_ids(
    location_id: str,
    *,
    routes: Iterable[SupportsRouteEdge],
    include_blocked: bool = False,
) -> List[str]:
    """Return neighboring site IDs connected by route edges."""
    result: List[str] = []
    seen: set[str] = set()
    for route in routes:
        if route.blocked and not include_blocked:
            continue
        other = route.other_end(location_id)
        if other is None or other in seen:
            continue
        seen.add(other)
        result.append(other)
    return result


def resolve_neighbor_ids(
    location_id: str,
    *,
    location_index: Mapping[str, SupportsTopologyLocation],
    grid: Mapping[Tuple[int, int], SupportsTopologyLocation],
    routes: Iterable[SupportsRouteEdge],
    mode: str = PROPAGATION_TOPOLOGY_TRAVEL,
    include_blocked_routes: bool = False,
) -> List[str]:
    """Resolve neighbor IDs using the requested topology contract."""
    if mode == PROPAGATION_TOPOLOGY_GRID:
        return grid_neighbor_ids(location_id, location_index=location_index, grid=grid)
    if mode == PROPAGATION_TOPOLOGY_TRAVEL:
        route_list = list(routes)
        if route_list:
            return route_neighbor_ids(
                location_id,
                routes=route_list,
                include_blocked=include_blocked_routes,
            )
        return grid_neighbor_ids(location_id, location_index=location_index, grid=grid)
    raise ValueError(f"Unsupported propagation topology mode: {mode}")

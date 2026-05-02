"""Runtime topology cache helpers for the World aggregate."""

from __future__ import annotations

from typing import Dict, Iterable, List

from .terrain import RouteEdge, Site
from .world_route_graph import rebuild_route_index
from .world_topology_state import WorldTopologyState
from .world_protocols import RouteIndexChangeHandler, TopologyRuntimeWorld


def site_index_by_location(sites: Iterable[Site]) -> Dict[str, Site]:
    """Build a site lookup index keyed by location id."""
    return {site.location_id: site for site in sites}


def route_index_by_site(
    *,
    sites: Iterable[Site],
    routes: Iterable[RouteEdge],
    on_change: RouteIndexChangeHandler,
    owner_token: object | None = None,
) -> Dict[str, List[RouteEdge]]:
    """Build route adjacency lists keyed by endpoint location id."""
    return rebuild_route_index(
        sites=sites,
        routes=routes,
        on_change=on_change,
        owner_token=owner_token,
    )


def apply_topology_state(world: TopologyRuntimeWorld, topology_state: WorldTopologyState) -> None:
    """Apply a reconstructed topology snapshot to a live world object."""
    world.terrain_map = topology_state.terrain_map
    world.sites = topology_state.sites
    world.routes = topology_state.routes
    world._rebuild_site_index()
    world._rebuild_route_index()
    world._route_graph_explicit = topology_state.route_graph_explicit
    world.atlas_layout = topology_state.atlas_layout

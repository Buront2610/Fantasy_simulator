"""Topology build and restore helpers for ``World``.

This module isolates terrain/site/route reconstruction from the aggregate so
``World`` can orchestrate state without owning every topology detail.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Protocol, Tuple

from .terrain import (
    AtlasLayout,
    RouteEdge,
    Site,
    TerrainMap,
    assemble_atlas_layout_inputs,
    build_cached_world_structure,
    build_default_atlas_layout,
    normalize_route_payload,
)


class SupportsLocationState(Protocol):
    id: str
    canonical_name: str
    description: str
    region_type: str
    x: int
    y: int


NormalizeLocationId = Callable[[Optional[str]], Optional[str]]


@dataclass(slots=True)
class WorldTopologyState:
    terrain_map: Optional[TerrainMap]
    sites: List[Site]
    routes: List[RouteEdge]
    atlas_layout: Optional[AtlasLayout]
    route_graph_explicit: bool


def build_topology_from_locations(
    *,
    width: int,
    height: int,
    locations: Iterable[SupportsLocationState],
    route_specs: Optional[List[Dict[str, Any]]] = None,
    explicit_route_graph: bool,
) -> WorldTopologyState:
    """Build terrain, sites, routes, and atlas layout from current locations."""
    location_tuples = [
        (
            loc.id,
            loc.canonical_name,
            loc.description,
            loc.region_type,
            loc.x,
            loc.y,
        )
        for loc in locations
    ]
    terrain_map, sites, routes, atlas_layout = build_cached_world_structure(
        width=width,
        height=height,
        locations=location_tuples,
        route_specs=route_specs if explicit_route_graph else None,
    )
    return WorldTopologyState(
        terrain_map=terrain_map,
        sites=sites,
        routes=routes,
        atlas_layout=atlas_layout,
        route_graph_explicit=explicit_route_graph,
    )


def build_atlas_layout_from_topology(
    *,
    width: int,
    height: int,
    terrain_map: Optional[TerrainMap],
    sites: Iterable[Site],
    routes: Iterable[RouteEdge],
) -> AtlasLayout:
    """Generate the persistent atlas layout from current topology state."""
    site_list = list(sites)
    route_list = list(routes)
    inputs = assemble_atlas_layout_inputs(
        width=width,
        height=height,
        sites=site_list,
        routes=route_list,
        terrain_cells=list(terrain_map.cells.values()) if terrain_map is not None else [],
    )
    return build_default_atlas_layout(inputs)


def overlay_serialized_route_state(
    routes: Iterable[RouteEdge],
    serialized_routes: List[Dict[str, Any]],
) -> None:
    """Overlay mutable route state onto the canonical route graph."""
    if not serialized_routes:
        return
    route_list = list(routes)
    serialized_by_id: Dict[str, Dict[str, Any]] = {}
    for item in serialized_routes:
        if not isinstance(item, dict):
            raise ValueError("Serialized route overlay entries must be dicts")
        payload = normalize_route_payload(item)
        route_id = payload["route_id"]
        if route_id in serialized_by_id:
            raise ValueError(f"Serialized route overlay contains duplicate route id: {route_id!r}")
        serialized_by_id[route_id] = payload
    known_route_ids = {route.route_id for route in route_list}
    known_route_pairs = {
        tuple(sorted((route.from_site_id, route.to_site_id)))
        for route in route_list
    }
    unknown_route_ids = sorted(set(serialized_by_id) - known_route_ids)
    for route_id in unknown_route_ids:
        unknown_route_payload = serialized_by_id[route_id]
        route_pair = tuple(sorted((unknown_route_payload["from_site_id"], unknown_route_payload["to_site_id"])))
        if route_pair in known_route_pairs:
            raise ValueError(f"Serialized route overlay references unknown route id: {route_id!r}")
    for route in route_list:
        overlay_payload = serialized_by_id.get(route.route_id)
        if overlay_payload is None:
            continue
        if overlay_payload["from_site_id"] != route.from_site_id or overlay_payload["to_site_id"] != route.to_site_id:
            raise ValueError(f"Serialized route overlay disagrees with canonical endpoints: {route.route_id!r}")
        route.route_type = overlay_payload["route_type"]
        route.distance = overlay_payload["distance"]
        route.blocked = overlay_payload["blocked"]


def validate_topology_integrity(
    *,
    sites: Iterable[Site],
    routes: Iterable[RouteEdge],
    location_index: Mapping[str, SupportsLocationState],
) -> None:
    """Validate that restored topology is coherent with the active grid."""
    site_list = list(sites)
    route_list = list(routes)
    site_index = {site.location_id: site for site in site_list}

    for site in site_list:
        location = location_index.get(site.location_id)
        if location is None:
            raise ValueError(f"Serialized site references unknown location: {site.location_id!r}")
        if (site.x, site.y) != (location.x, location.y):
            raise ValueError(
                f"Serialized site coordinates disagree with location state for {site.location_id!r}"
            )

    seen_route_ids: set[str] = set()
    seen_route_pairs: set[Tuple[str, str]] = set()
    for route in route_list:
        if route.route_id in seen_route_ids:
            raise ValueError(f"Serialized topology contains duplicate route id: {route.route_id!r}")
        seen_route_ids.add(route.route_id)
        if route.from_site_id == route.to_site_id:
            raise ValueError(f"Serialized route forms a self-loop: {route.route_id!r}")
        if route.from_site_id not in site_index or route.to_site_id not in site_index:
            raise ValueError(f"Serialized route references unknown site: {route.route_id!r}")
        first_site_id, second_site_id = sorted((route.from_site_id, route.to_site_id))
        pair = (first_site_id, second_site_id)
        if pair in seen_route_pairs:
            raise ValueError(f"Serialized topology contains duplicate route pair: {pair[0]}->{pair[1]}")
        seen_route_pairs.add(pair)


def restore_serialized_topology(
    *,
    terrain_map_data: Dict[str, Any],
    site_data: List[Dict[str, Any]],
    route_data: List[Dict[str, Any]],
    normalize_location_id: NormalizeLocationId,
    location_index: Mapping[str, SupportsLocationState],
) -> WorldTopologyState:
    """Restore serialized topology and normalize location references before validation."""
    terrain_map = TerrainMap.from_dict(terrain_map_data)
    sites = [Site.from_dict(item) for item in site_data]
    routes = [RouteEdge.from_dict(item) for item in route_data]
    for site in sites:
        site.location_id = normalize_location_id(site.location_id) or site.location_id
    for route in routes:
        route.from_site_id = normalize_location_id(route.from_site_id) or route.from_site_id
        route.to_site_id = normalize_location_id(route.to_site_id) or route.to_site_id
    validate_topology_integrity(
        sites=sites,
        routes=routes,
        location_index=location_index,
    )
    return WorldTopologyState(
        terrain_map=terrain_map,
        sites=sites,
        routes=routes,
        atlas_layout=None,
        route_graph_explicit=True,
    )

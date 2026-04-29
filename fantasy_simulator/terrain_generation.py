"""Default terrain and atlas structure generation."""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple

from .terrain_models import AtlasLayout, RouteEdge, Site, TerrainCell, TerrainMap
from .terrain_payloads import normalize_route_payload, terrain_structure_payload
from .terrain_route_generation import (
    AtlasLayoutInputs,
    assemble_atlas_layout_inputs,
    build_default_atlas_layout_data,
    project_atlas_coords,
    provisional_route_specs_from_grid_adjacency,
)

REGION_TYPE_TO_BIOME: Dict[str, str] = {
    "city": "plains",
    "village": "plains",
    "forest": "forest",
    "dungeon": "hills",
    "mountain": "mountain",
    "plains": "plains",
    "sea": "ocean",
}

SITE_IMPORTANCE: Dict[str, int] = {
    "city": 80,
    "village": 40,
    "forest": 20,
    "dungeon": 60,
    "mountain": 30,
    "plains": 20,
    "sea": 10,
}


def build_default_atlas_layout(
    inputs: Optional[AtlasLayoutInputs] = None,
    *,
    site_coords: Optional[List[Tuple[int, int]]] = None,
    route_coords: Optional[List[Tuple[Tuple[int, int], Tuple[int, int]]]] = None,
    mountain_coords: Optional[List[Tuple[int, int]]] = None,
) -> AtlasLayout:
    """Create the default persistent atlas layout for the current world."""
    return AtlasLayout.from_dict(
        build_default_atlas_layout_data(
            inputs,
            site_coords=site_coords,
            route_coords=route_coords,
            mountain_coords=mountain_coords,
        )
    )


@lru_cache(maxsize=64)
def _cached_atlas_layout_template(
    site_coords: Tuple[Tuple[int, int], ...],
    route_coords: Tuple[Tuple[Tuple[int, int], Tuple[int, int]], ...],
    mountain_coords: Tuple[Tuple[int, int], ...],
) -> AtlasLayout:
    return build_default_atlas_layout(
        AtlasLayoutInputs(
            site_coords=list(site_coords),
            route_coords=list(route_coords),
            mountain_coords=list(mountain_coords),
        )
    )


def build_cached_world_structure(
    *,
    width: int,
    height: int,
    locations: Optional[List[Tuple[str, str, str, str, int, int]]] = None,
    route_specs: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[TerrainMap, List[Site], List[RouteEdge], AtlasLayout]:
    """Build world structure while caching only the atlas geometry projection."""
    terrain_map, sites, routes = build_default_terrain(
        width=width,
        height=height,
        locations=locations,
        route_specs=route_specs,
    )
    inputs = assemble_atlas_layout_inputs(
        width=width,
        height=height,
        sites=sites,
        routes=routes,
        terrain_cells=list(terrain_map.cells.values()),
    )
    atlas_layout = _cached_atlas_layout_template(
        tuple(inputs.site_coords),
        tuple(inputs.route_coords),
        tuple(inputs.mountain_coords),
    )
    return (
        terrain_map,
        sites,
        routes,
        deepcopy(atlas_layout),
    )


def build_default_terrain(
    width: int = 5,
    height: int = 5,
    locations: Optional[List] = None,
    route_specs: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[TerrainMap, List[Site], List[RouteEdge]]:
    """Generate terrain, sites, and routes from a location list."""
    if locations is None:
        raise ValueError("locations must be provided by the compatibility facade")

    tmap = TerrainMap(width=width, height=height)

    for y in range(height):
        for x in range(width):
            tmap.set_cell(TerrainCell(x=x, y=y, biome="plains"))

    sites: List[Site] = []
    site_coords: Dict[Tuple[int, int], str] = {}
    for entry in locations:
        loc_id, _name, _desc, region_type, x, y = entry
        if not tmap.in_bounds(x, y):
            continue
        biome = REGION_TYPE_TO_BIOME.get(region_type, "plains")
        importance = SITE_IMPORTANCE.get(region_type, 50)

        cell = tmap.get(x, y)
        if cell is not None:
            cell.biome = biome

        sites.append(Site(
            location_id=loc_id,
            x=x,
            y=y,
            site_type=region_type,
            importance=importance,
        ))
        site_coords[(x, y)] = loc_id

    routes: List[RouteEdge] = []
    if route_specs is not None:
        valid_site_ids = {site.location_id for site in sites}
        for spec in route_specs:
            payload = normalize_route_payload(spec)
            if payload["from_site_id"] not in valid_site_ids or payload["to_site_id"] not in valid_site_ids:
                raise ValueError(f"route {payload['route_id']} references an unknown site")
            routes.append(RouteEdge.from_dict(payload))
    else:
        routes = [
            RouteEdge.from_dict(spec)
            for spec in provisional_route_specs_from_grid_adjacency(
                site_coords,
                biome_at=lambda x, y: (tmap.get(x, y) or TerrainCell(x=x, y=y)).biome,
            )
        ]

    for site in sites:
        site.atlas_x, site.atlas_y = project_atlas_coords(
            site.x,
            site.y,
            width=width,
            height=height,
        )

    return tmap, sites, routes


def build_terrain_payload_from_locations(
    width: int,
    height: int,
    locations: List,
    route_specs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return serialized terrain/site/route payloads for a location list."""
    terrain_map, sites, routes = build_default_terrain(
        width=width,
        height=height,
        locations=locations,
        route_specs=route_specs,
    )
    return terrain_structure_payload(terrain_map, sites, routes)

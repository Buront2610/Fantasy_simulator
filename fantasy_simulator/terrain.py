"""Compatibility facade for terrain models and generation helpers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .terrain_generation import (
    REGION_TYPE_TO_BIOME,
    SITE_IMPORTANCE,
    build_cached_world_structure as _build_cached_world_structure,
    build_default_atlas_layout,
    build_default_terrain as _build_default_terrain,
    build_terrain_payload_from_locations as _build_terrain_payload_from_locations,
)
from .terrain_payloads import normalize_route_payload
from .terrain_models import (
    BIOME_GLYPHS,
    BIOME_MOVE_COST,
    BIOME_TYPES,
    ROUTE_BASE_COST,
    ROUTE_TYPES,
    AtlasLayout,
    RouteEdge,
    Site,
    TerrainCell,
    TerrainMap,
)
from .terrain_route_generation import (
    ATLAS_CANVAS_H,
    ATLAS_CANVAS_W,
    ATLAS_MARGIN_X,
    ATLAS_MARGIN_Y,
    AtlasLayoutInputs,
    assemble_atlas_layout_inputs,
    project_atlas_coords,
    provisional_route_specs_from_grid_adjacency,
)


def _default_locations() -> List[Any]:
    from .content.world_data import DEFAULT_LOCATIONS
    return DEFAULT_LOCATIONS


def build_default_terrain(
    width: int = 5,
    height: int = 5,
    locations: Optional[List[Any]] = None,
    route_specs: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[TerrainMap, List[Site], List[RouteEdge]]:
    return _build_default_terrain(
        width=width,
        height=height,
        locations=locations if locations is not None else _default_locations(),
        route_specs=route_specs,
    )


def build_cached_world_structure(
    *,
    width: int,
    height: int,
    locations: Optional[List[Tuple[str, str, str, str, int, int]]] = None,
    route_specs: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[TerrainMap, List[Site], List[RouteEdge], AtlasLayout]:
    return _build_cached_world_structure(
        width=width,
        height=height,
        locations=locations if locations is not None else _default_locations(),
        route_specs=route_specs,
    )


def build_terrain_payload_from_locations(
    width: int,
    height: int,
    locations: List[Any],
    route_specs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    return _build_terrain_payload_from_locations(
        width=width,
        height=height,
        locations=locations,
        route_specs=route_specs,
    )


__all__ = [
    "ATLAS_CANVAS_H",
    "ATLAS_CANVAS_W",
    "ATLAS_MARGIN_X",
    "ATLAS_MARGIN_Y",
    "BIOME_GLYPHS",
    "BIOME_MOVE_COST",
    "BIOME_TYPES",
    "REGION_TYPE_TO_BIOME",
    "ROUTE_BASE_COST",
    "ROUTE_TYPES",
    "SITE_IMPORTANCE",
    "AtlasLayout",
    "AtlasLayoutInputs",
    "RouteEdge",
    "Site",
    "TerrainCell",
    "TerrainMap",
    "assemble_atlas_layout_inputs",
    "build_cached_world_structure",
    "build_default_atlas_layout",
    "build_default_terrain",
    "build_terrain_payload_from_locations",
    "normalize_route_payload",
    "project_atlas_coords",
    "provisional_route_specs_from_grid_adjacency",
]

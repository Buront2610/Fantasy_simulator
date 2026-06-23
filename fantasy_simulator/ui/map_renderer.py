"""
map_renderer.py - Compatibility facade for map rendering.

The renderer-agnostic map snapshots live in ``world_map.view_models``.  The
world/region observation renderers live in ``map_overview_renderer`` and
single-site detail rendering lives in ``map_location_renderer``.  This module
keeps the historic import surface stable and retains the legacy ASCII grid
renderer used by ``world.render_map()``.
"""

from __future__ import annotations

from ..world_map.ascii_renderer import render_map_ascii
from ..world_map.view_models import (
    MapCellInfo,
    MapRenderInfo,
    RouteRenderInfo,
    TerrainCellRenderInfo,
    build_map_info,
)
from .map_location_renderer import render_location_detail
from .map_overview_renderer import (
    _overlay_suffix,
    render_region_map,
    render_world_overview,
)

__all__ = [
    "MapCellInfo",
    "MapRenderInfo",
    "RouteRenderInfo",
    "TerrainCellRenderInfo",
    "build_map_info",
    "render_map_ascii",
    "render_world_overview",
    "render_region_map",
    "render_location_detail",
    "_overlay_suffix",
]

"""World and region map observation renderers."""

from __future__ import annotations

from typing import Dict, List, Optional

from ..i18n import tr
from .map_overlays import _overlay_suffix
from .map_region_focus import region_focus_lines
from .map_region_grid import (
    append_region_grid,
    build_region_route_layer,
    find_region_center_cell,
    region_bounds,
    visible_region_cells,
)
from .map_region_sections import (
    append_nearby_sites,
    append_region_focus,
    append_region_landmarks,
    append_region_routes,
)
from .map_route_helpers import center_region_routes, center_route_connections
from .map_view_models import MapCellInfo, MapRenderInfo
from .map_world_overview import render_world_overview

__all__ = [
    "_overlay_suffix",
    "render_region_map",
    "render_world_overview",
]


def render_region_map(
    info: MapRenderInfo,
    center_location_id: str,
    radius: int = 2,
    *,
    site_memorials: Optional[Dict[str, List[str]]] = None,
    site_aliases: Optional[Dict[str, List[str]]] = None,
    site_traces: Optional[Dict[str, List[str]]] = None,
    site_endonyms: Optional[Dict[str, str]] = None,
) -> str:
    """Render a zoomed region map around a selected site."""
    center_cell = find_region_center_cell(info, center_location_id)
    if center_cell is None:
        return f"  {tr('map_region_not_found', location=center_location_id)}"

    lines: List[str] = [
        f"  === {tr('map_region_title')}: {center_cell.canonical_name} ===",
        "",
    ]

    cells_by_id: Dict[str, MapCellInfo] = {
        c.location_id: c for c in info.cells.values()
    }
    bounds = region_bounds(info, center_cell, radius)
    route_layer = build_region_route_layer(info, bounds)
    append_region_grid(lines, info, center_location_id, bounds, route_layer)

    connected_open_ids, connected_blocked_ids = center_route_connections(info.routes, center_location_id)
    region_routes = center_region_routes(info.routes, center_location_id)
    visible_cells = visible_region_cells(info, bounds)

    memorials = site_memorials or {}
    aliases = site_aliases or {}
    traces = site_traces or {}
    endonyms = site_endonyms or {}
    standout_lines = region_focus_lines(
        visible_cells,
        center_cell,
        region_routes,
        cells_by_id,
        connected_open_ids,
        connected_blocked_ids,
        memorials,
        aliases,
        traces,
        endonyms,
    )
    append_region_focus(lines, standout_lines)
    append_nearby_sites(lines, visible_cells, center_location_id, connected_open_ids, connected_blocked_ids)
    append_region_routes(lines, region_routes, cells_by_id)
    append_region_landmarks(lines, visible_cells, memorials, aliases, traces, endonyms)

    return "\n".join(lines)

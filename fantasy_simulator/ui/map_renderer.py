"""
map_renderer.py - Compatibility facade for map rendering.

The renderer-agnostic map snapshots live in ``map_view_models``.  The
world/region observation renderers live in ``map_overview_renderer`` and
single-site detail rendering lives in ``map_location_renderer``.  This module
keeps the historic import surface stable and retains the legacy ASCII grid
renderer used by ``world.render_map()``.
"""

from __future__ import annotations

from typing import List

from ..i18n import tr, tr_term
from .map_location_renderer import render_location_detail
from .map_overview_renderer import (
    _overlay_suffix,
    render_region_map,
    render_world_overview,
)
from .map_view_models import (
    MapCellInfo,
    MapRenderInfo,
    RouteRenderInfo,
    TerrainCellRenderInfo,
    build_map_info,
)
from .ui_helpers import fit_display_width

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


def _fit(text: str, width: int) -> str:
    """Shorthand for ``fit_display_width`` inside the renderer."""
    return fit_display_width(text, width)


def render_map_ascii(info: MapRenderInfo) -> str:
    """Render a ``MapRenderInfo`` as a stable ASCII grid.

    Cells that contain a site (``info.cells``) are rendered with full
    detail (name, type, safety, danger, traffic, population).  Cells that
    have terrain but no site (``info.terrain_cells``) are rendered with
    their biome glyph and biome name.  Cells with neither are shown as
    ``?`` placeholders.
    """
    cell_width = 20
    inner_width = info.width * cell_width + (info.width - 1)
    border = "  +" + "-" * inner_width + "+"
    header = f" {tr('map_title')}: {info.world_name} | {tr('map_year')}: {info.year}"
    lines: List[str] = [
        border,
        f"  |{_fit(header, inner_width)}|",
        border,
    ]

    for y in range(info.height):
        row_names: List[str] = []
        row_types: List[str] = []
        row_safety: List[str] = []
        row_danger: List[str] = []
        row_traffic: List[str] = []
        row_pops: List[str] = []

        for x in range(info.width):
            cell = info.cells.get((x, y))
            if cell is not None:
                region_name = tr_term(cell.region_type)
                row_names.append(_fit(f" {cell.icon} {cell.canonical_name}", cell_width))
                row_types.append(_fit(f" {tr('map_type')}: {region_name}", cell_width))
                row_safety.append(_fit(f" {tr('map_safety')}: {cell.safety_label}", cell_width))
                row_danger.append(_fit(f" {tr('map_danger')}: {cell.danger:>3}", cell_width))
                row_traffic.append(_fit(f" {tr('map_traffic')}: {cell.traffic_indicator}", cell_width))
                row_pops.append(_fit(f" {tr('map_population')}: {cell.population}", cell_width))
                continue

            tcell = info.terrain_cells.get((x, y))
            if tcell is not None:
                biome_name = tr_term(tcell.biome)
                row_names.append(_fit(f" {tcell.glyph} ({biome_name})", cell_width))
                row_types.append(_fit(f" {tr('map_terrain')}: {biome_name}", cell_width))
                blank = " " * cell_width
                row_safety.append(blank)
                row_danger.append(blank)
                row_traffic.append(blank)
                row_pops.append(blank)
                continue

            blank = " " * cell_width
            row_names.append(_fit(" ? ???", cell_width))
            row_types.append(blank)
            row_safety.append(blank)
            row_danger.append(blank)
            row_traffic.append(blank)
            row_pops.append(blank)

        lines.append("  |" + "|".join(row_names) + "|")
        lines.append("  |" + "|".join(row_types) + "|")
        lines.append("  |" + "|".join(row_safety) + "|")
        lines.append("  |" + "|".join(row_danger) + "|")
        lines.append("  |" + "|".join(row_traffic) + "|")
        lines.append("  |" + "|".join(row_pops) + "|")
        lines.append(border)

    return "\n".join(lines)

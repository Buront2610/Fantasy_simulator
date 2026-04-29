"""Compact world overview map renderer."""

from __future__ import annotations

from typing import Dict, List

from ..i18n import tr, tr_term
from ..terrain import BIOME_GLYPHS
from .map_overlays import _overlay_suffix
from .map_route_helpers import route_endpoint_name
from .map_view_models import MapCellInfo, MapRenderInfo


def render_world_overview(info: MapRenderInfo) -> str:
    """Render a compact terrain-glyph world map with overlay markers."""
    lines: List[str] = []
    header = f"  === {tr('map_overview_title')}: {info.world_name} ({tr('map_year')}: {info.year}) ==="
    lines.append(header)
    lines.append("")

    col_hdr = "    " + "".join(f"{x % 10}" for x in range(info.width))
    lines.append(col_hdr)
    lines.append("   +" + "-" * info.width + "+")

    for y in range(info.height):
        row_chars: List[str] = []
        for x in range(info.width):
            cell = info.cells.get((x, y))
            if cell is not None:
                overlay = _overlay_suffix(cell)
                if cell.highlighted:
                    row_chars.append("*")
                elif overlay:
                    row_chars.append(overlay[0])
                else:
                    row_chars.append(cell.canonical_name[0].upper() if cell.canonical_name else "@")
            else:
                tcell = info.terrain_cells.get((x, y))
                row_chars.append(tcell.glyph if tcell is not None else " ")
        lines.append(f"  {y % 10}|{''.join(row_chars)}|")

    lines.append("   +" + "-" * info.width + "+")

    lines.append("")
    lines.append(f"  {tr('map_overview_sites')}:")
    site_cells = sorted(info.cells.values(), key=lambda c: (c.y, c.x))
    cells_by_id: Dict[str, MapCellInfo] = {
        c.location_id: c for c in info.cells.values()
    }
    for cell in site_cells:
        overlay = _overlay_suffix(cell)
        overlay_str = f" [{overlay}]" if overlay else ""
        pop_str = f" pop:{cell.population}" if cell.population else ""
        lines.append(
            f"    ({cell.x},{cell.y}) {cell.canonical_name}"
            f" - {tr_term(cell.region_type)}{overlay_str}{pop_str}"
        )

    if info.routes:
        lines.append("")
        lines.append(f"  {tr('map_overview_routes')}:")
        for route in info.routes:
            blocked = f" {tr('route_blocked')}" if route.blocked else ""
            from_name = route_endpoint_name(cells_by_id, route.from_site_id)
            to_name = route_endpoint_name(cells_by_id, route.to_site_id)
            lines.append(
                f"    {from_name} <-> {to_name}"
                f" ({tr_term(route.route_type)}){blocked}"
            )

    lines.append("")
    lines.append(f"  {tr('map_legend_title')}:")
    lines.append(f"    {tr('map_legend_terrain')}:")
    for biome, glyph in BIOME_GLYPHS.items():
        lines.append(f"      {glyph} = {tr_term(biome)}")
    lines.append(f"    {tr('map_legend_overlays')}:")
    lines.append(f"      ! = {tr('map_legend_danger_high')}")
    lines.append(f"      $ = {tr('map_legend_traffic_high')}")
    lines.append(f"      ? = {tr('map_legend_rumor_high')}")
    lines.append(f"      m = {tr('map_legend_memorial')}")
    lines.append(f"      a = {tr('map_legend_alias')}")
    lines.append(f"      + = {tr('map_legend_recent_death')}")
    lines.append(f"      * = {tr('map_legend_highlighted')}")

    return "\n".join(lines)

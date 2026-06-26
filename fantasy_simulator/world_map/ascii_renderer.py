"""Stable ASCII map rendering for compatibility callers."""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from .display_width import fit_display_width
from ..i18n import tr, tr_term
from .view_models import MapRenderInfo

if TYPE_CHECKING:
    from ..world import World


def _fit(text: str, width: int) -> str:
    return fit_display_width(text, width)


def render_map_ascii(info: MapRenderInfo) -> str:
    """Render a ``MapRenderInfo`` as a stable ASCII grid."""
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


def render_world_map_ascii(world: "World", highlight_location: str | None = None) -> str:
    """Build and render the stable ASCII map for a world-like object."""
    from .view_models import build_map_info

    return render_map_ascii(build_map_info(world, highlight_location))

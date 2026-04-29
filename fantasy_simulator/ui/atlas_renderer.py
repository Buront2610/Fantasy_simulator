"""
atlas_renderer.py - Atlas-scale world map with continent and terrain.

PR-G2 core: Provides a "world map" experience where the game's
location network (5x5 or variable) is projected onto a larger terrain
canvas.  The atlas shows terrain, named locations, routes, and overlays.
"""

from __future__ import annotations

from typing import List, Tuple, TYPE_CHECKING

from ..i18n import tr, tr_term
from .atlas_canvas import (
    _ATLAS_H,
    _ATLAS_W,
    _BIOME_CHARS,
    _ROUTE_LINE,
    _build_atlas_base_canvas,
    _build_atlas_canvas,
    _bresenham,
    _cluster_sites,
    _overlay_suffix,
    _place_labels,
    _terrain_char,
)

if TYPE_CHECKING:
    from .map_renderer import MapRenderInfo


__all__ = [
    "_ATLAS_H",
    "_ATLAS_W",
    "_BIOME_CHARS",
    "_ROUTE_LINE",
    "_build_atlas_base_canvas",
    "_build_atlas_canvas",
    "_bresenham",
    "_cluster_sites",
    "_overlay_suffix",
    "_terrain_char",
    "atlas_labeled_sites",
    "render_atlas_compact",
    "render_atlas_minimal",
    "render_atlas_overview",
]


# ------------------------------------------------------------------
# Public renderer
# ------------------------------------------------------------------

def render_atlas_overview(info: "MapRenderInfo") -> str:
    """Render the atlas-scale world overview map.

    Returns a formatted string with header, terrain canvas, and
    compact legend.
    """
    canvas = _build_atlas_canvas(info)

    header = (
        f"  === {tr('map_overview_title')}: "
        f"{info.world_name} ({tr('map_year')}: {info.year}) ==="
    )
    lines: List[str] = [header, ""]

    for row in canvas:
        lines.append("  " + "".join(row).rstrip())

    # --- Compact legend ---
    lines.append("")
    lines.append(f"  {tr('map_legend_title')}:")

    # Atlas-specific terrain chars (first char of each palette entry)
    t_items = " ".join(
        f"{chars[0]}={tr_term(b)}" for b, chars in _BIOME_CHARS.items()
    )
    lines.append(f"    {tr('map_legend_terrain')}: {t_items}")

    r_items = " ".join(
        f"{c[0]}={tr_term(rt)}" for rt, c in _ROUTE_LINE.items()
    )
    lines.append(f"    {tr('map_legend_routes')}: {r_items}")

    ov_parts = [
        f"O={tr('map_legend_site_hub')}",
        f"@={tr('map_legend_site_marker')}",
        f"o={tr('map_legend_site_quiet')}",
        f"!={tr('map_legend_danger_high')}",
        f"$={tr('map_legend_traffic_high')}",
        f"?={tr('map_legend_rumor_high')}",
        f"m={tr('map_legend_memorial')}",
        f"a={tr('map_legend_alias')}",
        f"+={tr('map_legend_recent_death')}",
    ]
    lines.append(
        f"    {tr('map_legend_overlays')}: {' '.join(ov_parts)}"
    )

    return "\n".join(lines)


# ------------------------------------------------------------------
# Compact atlas (narrow terminals, ~40 cols)
# ------------------------------------------------------------------

_COMPACT_W = 40
_COMPACT_H = 16


def render_atlas_compact(info: "MapRenderInfo") -> str:
    """Render a compact atlas overview for narrow terminals.

    Half the width of the full atlas.  Shows terrain canvas, site
    markers, and a minimal legend.
    """
    w, h = _COMPACT_W, _COMPACT_H
    canvas, site_atlas = _build_atlas_base_canvas(info, w, h)
    _place_labels(canvas, info, site_atlas, w, h, place_names=False)

    header = f"  {info.world_name} ({tr('map_year')}: {info.year})"
    lines: List[str] = [header, ""]
    for row in canvas:
        lines.append("  " + "".join(row).rstrip())
    return "\n".join(lines)


# ------------------------------------------------------------------
# Minimal text summary (no canvas)
# ------------------------------------------------------------------

def render_atlas_minimal(info: "MapRenderInfo") -> str:
    """Render a minimal text summary of the world (no map canvas).

    Lists sites grouped by importance, with danger/traffic/rumor
    indicators.  Suitable for screen readers and very narrow terminals.
    """
    header = (
        f"  {tr('map_overview_title')}: "
        f"{info.world_name} ({tr('map_year')}: {info.year})"
    )
    lines: List[str] = [header, ""]

    cells_sorted = sorted(
        info.cells.values(),
        key=lambda c: (-c.site_importance, c.canonical_name),
    )

    for idx, cell in enumerate(cells_sorted, 1):
        overlay = _overlay_suffix(cell)
        overlay_str = f" [{overlay}]" if overlay else ""
        lines.append(
            f"  {idx:>2}. {cell.canonical_name}"
            f" ({tr_term(cell.region_type)}){overlay_str}"
        )

    if info.routes:
        lines.append("")
        lines.append(f"  {tr('map_overview_routes')}: {len(info.routes)}")

    return "\n".join(lines)


# ------------------------------------------------------------------
# Atlas labeled sites (for direct selection - item 11)
# ------------------------------------------------------------------

def atlas_labeled_sites(info: "MapRenderInfo") -> List[Tuple[str, str]]:
    """Return ``(location_id, display_name)`` for atlas-labeled sites.

    Sites are returned in importance-descending order, matching the
    label priority used by ``_place_labels``.
    """
    if not info.cells:
        return []

    canvas, site_atlas = _build_atlas_base_canvas(info, _ATLAS_W, _ATLAS_H)
    labeled_ids = _place_labels(canvas, info, site_atlas, _ATLAS_W, _ATLAS_H)
    cells_sorted = sorted(
        info.cells.values(),
        key=lambda c: (-c.site_importance, c.canonical_name),
    )
    return [
        (cell.location_id, cell.canonical_name)
        for cell in cells_sorted
        if cell.location_id in labeled_ids
    ]

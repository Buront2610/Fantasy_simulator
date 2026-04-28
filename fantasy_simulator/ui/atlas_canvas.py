"""Atlas canvas construction helpers."""

from __future__ import annotations

from typing import Dict, List, Tuple, TYPE_CHECKING

from .atlas_data import (
    _ATLAS_H,
    _ATLAS_W,
    _build_biome_seeds,
    _build_site_atlas,
)
from .atlas_geometry import _bresenham
from .atlas_labels import _overlay_suffix, _place_labels
from .atlas_masks import (
    _build_layout_masks,
    _build_legacy_masks,
    _cluster_sites,
    _coast_noise,
    _mark_layout_cells,
    _paint_terrain,
)
from .atlas_palette import _BIOME_CHARS, _ROUTE_LINE, _terrain_char
from .atlas_routes import _draw_routes

if TYPE_CHECKING:
    from .map_renderer import MapRenderInfo

__all__ = [
    "_ATLAS_H",
    "_ATLAS_W",
    "_BIOME_CHARS",
    "_ROUTE_LINE",
    "_build_atlas_base_canvas",
    "_build_atlas_canvas",
    "_build_layout_masks",
    "_build_legacy_masks",
    "_bresenham",
    "_cluster_sites",
    "_coast_noise",
    "_mark_layout_cells",
    "_overlay_suffix",
    "_paint_terrain",
    "_place_labels",
    "_terrain_char",
]


def _build_atlas_base_canvas(
    info: "MapRenderInfo",
    w: int,
    h: int,
) -> Tuple[List[List[str]], Dict[str, Tuple[int, int]]]:
    """Build atlas terrain and routes, before labels/markers."""
    canvas: List[List[str]] = [["~"] * w for _ in range(h)]
    if not info.cells:
        return canvas, {}

    site_atlas = _build_site_atlas(info, w, h)
    biome_seeds = _build_biome_seeds(info, site_atlas, w, h)
    land, mountains = _build_layout_masks(info, site_atlas, w, h)
    _paint_terrain(canvas, land, mountains, biome_seeds, w, h)
    _draw_routes(canvas, info, site_atlas, w, h)
    return canvas, site_atlas


def _build_atlas_canvas(info: "MapRenderInfo") -> List[List[str]]:
    """Generate the full atlas canvas from *MapRenderInfo*."""
    canvas, site_atlas = _build_atlas_base_canvas(info, _ATLAS_W, _ATLAS_H)
    _place_labels(canvas, info, site_atlas, _ATLAS_W, _ATLAS_H)
    return canvas

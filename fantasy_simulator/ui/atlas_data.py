"""Atlas data extraction helpers for map rendering."""

from __future__ import annotations

from typing import Dict, List, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from .map_renderer import MapRenderInfo


_ATLAS_W = 72
_ATLAS_H = 30
_MARGIN_X = 6
_MARGIN_Y = 3


def _scale_canvas_point(
    x: int,
    y: int,
    *,
    src_w: int,
    src_h: int,
    dst_w: int,
    dst_h: int,
) -> Tuple[int, int]:
    """Scale a canvas coordinate from one atlas size to another."""
    scaled_x = int(round(x * max(dst_w - 1, 0) / max(src_w - 1, 1)))
    scaled_y = int(round(y * max(dst_h - 1, 0) / max(src_h - 1, 1)))
    return (
        max(0, min(dst_w - 1, scaled_x)),
        max(0, min(dst_h - 1, scaled_y)),
    )


def _project_grid_to_canvas(
    gx: int,
    gy: int,
    *,
    grid_w: int,
    grid_h: int,
    canvas_w: int,
    canvas_h: int,
) -> Tuple[int, int]:
    """Project grid coordinates via the canonical wide atlas, then scale."""
    avail_w = _ATLAS_W - 2 * _MARGIN_X
    avail_h = _ATLAS_H - 2 * _MARGIN_Y
    step_x = avail_w / max(grid_w - 1, 1)
    step_y = avail_h / max(grid_h - 1, 1)
    wide_x = int(_MARGIN_X + gx * step_x)
    wide_y = int(_MARGIN_Y + gy * step_y)
    return _scale_canvas_point(
        wide_x,
        wide_y,
        src_w=_ATLAS_W,
        src_h=_ATLAS_H,
        dst_w=canvas_w,
        dst_h=canvas_h,
    )


def _build_site_atlas(
    info: "MapRenderInfo",
    w: int,
    h: int,
) -> Dict[str, Tuple[int, int]]:
    """Resolve site anchor points for the target canvas size."""
    site_atlas: Dict[str, Tuple[int, int]] = {}
    src_w = info.atlas_layout.canvas_w if info.atlas_layout else _ATLAS_W
    src_h = info.atlas_layout.canvas_h if info.atlas_layout else _ATLAS_H

    for (gx, gy), cell in info.cells.items():
        if cell.atlas_x >= 0 and cell.atlas_y >= 0:
            ax, ay = _scale_canvas_point(
                cell.atlas_x,
                cell.atlas_y,
                src_w=src_w,
                src_h=src_h,
                dst_w=w,
                dst_h=h,
            )
        else:
            ax, ay = _project_grid_to_canvas(
                gx,
                gy,
                grid_w=info.width,
                grid_h=info.height,
                canvas_w=w,
                canvas_h=h,
            )
        site_atlas[cell.location_id] = (ax, ay)
    return site_atlas


def _build_biome_seeds(
    info: "MapRenderInfo",
    site_atlas: Dict[str, Tuple[int, int]],
    w: int,
    h: int,
) -> List[Tuple[int, int, str]]:
    """Collect biome seed points for atlas terrain painting."""
    biome_seeds: List[Tuple[int, int, str]] = []
    for cell in info.cells.values():
        ax, ay = site_atlas[cell.location_id]
        biome_seeds.append((ax, ay, cell.terrain_biome))

    site_coords = set(site_atlas.values())
    for (gx, gy), tcell in info.terrain_cells.items():
        ax, ay = _project_grid_to_canvas(
            gx,
            gy,
            grid_w=info.width,
            grid_h=info.height,
            canvas_w=w,
            canvas_h=h,
        )
        if (ax, ay) not in site_coords:
            biome_seeds.append((ax, ay, tcell.biome))
    return biome_seeds

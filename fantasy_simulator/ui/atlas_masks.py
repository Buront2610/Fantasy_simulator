"""Land mask and terrain painting helpers for atlas canvases."""

from __future__ import annotations

import math
from typing import Dict, List, Set, Tuple, TYPE_CHECKING

from .atlas_data import _ATLAS_H, _ATLAS_W, _MARGIN_X, _MARGIN_Y, _scale_canvas_point
from .atlas_palette import _terrain_char

if TYPE_CHECKING:
    from .map_renderer import MapRenderInfo


# Island generation parameters
_ISLAND_SPACING_X = 11
_ISLAND_SPACING_Y = 9
_ISLAND_MARGIN = 3


def _coast_noise(x: int, y: int) -> float:
    """Smooth deterministic noise for coastline variation."""
    return (
        0.25 * math.sin(x * 0.15 + 1.0) * math.cos(y * 0.2 + 2.0)
        + 0.15 * math.sin(x * 0.35 + 3.0) * math.sin(y * 0.25 + 1.5)
        + 0.10 * math.cos(x * 0.5 + y * 0.4 + 0.7)
    )


def _cluster_sites(
    sites: List[Tuple[int, int]],
    max_clusters: int = 4,
) -> List[List[Tuple[int, int]]]:
    """Partition *sites* into stable spatial clusters."""
    if len(sites) <= 3:
        return [sites]

    xs = [p[0] for p in sites]
    ys = [p[1] for p in sites]
    spread = max(max(xs) - min(xs), max(ys) - min(ys))
    if spread < 20:
        return [sites]

    k = min(max_clusters, max(2, len(sites) // 5))
    sorted_sites = sorted(sites)
    step = max(1, len(sorted_sites) // k)
    centroids = [sorted_sites[i * step % len(sorted_sites)] for i in range(k)]

    seen: Set[Tuple[int, int]] = set()
    unique: List[Tuple[int, int]] = []
    for centroid in centroids:
        if centroid not in seen:
            seen.add(centroid)
            unique.append(centroid)
    centroids = unique
    if len(centroids) < 2:
        return [sites]

    for _ in range(10):
        clusters: List[List[Tuple[int, int]]] = [[] for _ in range(len(centroids))]
        for pt in sites:
            best_i = 0
            best_d = float("inf")
            for ci, centroid in enumerate(centroids):
                dist = (pt[0] - centroid[0]) ** 2 + (pt[1] - centroid[1]) ** 2
                if dist < best_d:
                    best_d = dist
                    best_i = ci
            clusters[best_i].append(pt)

        new_centroids: List[Tuple[int, int]] = []
        for idx, cluster in enumerate(clusters):
            if cluster:
                new_centroids.append((
                    int(sum(p[0] for p in cluster) / len(cluster)),
                    int(sum(p[1] for p in cluster) / len(cluster)),
                ))
            else:
                new_centroids.append(centroids[idx])
        if new_centroids == centroids:
            break
        centroids = new_centroids

    return [cluster for cluster in clusters if cluster]


def _mark_layout_cells(
    mask: List[List[bool]],
    cells: List[object],
    *,
    src_w: int,
    src_h: int,
    dst_w: int,
    dst_h: int,
    value: bool,
) -> None:
    """Apply stored atlas layout cells onto a boolean mask."""
    for cell in cells:
        if not isinstance(cell, (list, tuple)) or len(cell) != 2:
            continue
        try:
            sx = int(cell[0])
            sy = int(cell[1])
        except (TypeError, ValueError):
            continue
        dx, dy = _scale_canvas_point(
            sx,
            sy,
            src_w=src_w,
            src_h=src_h,
            dst_w=dst_w,
            dst_h=dst_h,
        )
        mask[dy][dx] = value


def _build_legacy_masks(
    site_atlas: Dict[str, Tuple[int, int]],
    w: int,
    h: int,
) -> Tuple[List[List[bool]], List[List[bool]]]:
    """Generate land masks using the legacy site-clustering fallback."""
    land: List[List[bool]] = [[False] * w for _ in range(h)]
    clusters = _cluster_sites(list(site_atlas.values()))

    for cluster in clusters:
        cx = sum(p[0] for p in cluster) / len(cluster)
        cy = sum(p[1] for p in cluster) / len(cluster)
        span_x = (max(p[0] for p in cluster) - min(p[0] for p in cluster)) / 2
        span_y = (max(p[1] for p in cluster) - min(p[1] for p in cluster)) / 2
        rx = span_x + max(1, int(round(_MARGIN_X * w / _ATLAS_W))) + 1
        ry = span_y + max(1, int(round(_MARGIN_Y * h / _ATLAS_H))) + 1
        seed_off = int(cx * 7 + cy * 13)

        for py in range(h):
            for px in range(w):
                dx = (px - cx) / max(rx, 1)
                dy = (py - cy) / max(ry, 1)
                dist = math.sqrt(dx * dx + dy * dy)

                angle = math.atan2(dy, dx)
                angular_noise = (
                    0.15 * math.sin(angle * 3 + 1.0 + seed_off)
                    + 0.10 * math.sin(angle * 7 + 2.0 + seed_off)
                    + 0.06 * math.sin(angle * 13 + 3.0 + seed_off)
                )
                shoreline_noise = _coast_noise(px + seed_off, py + seed_off)

                if dist < 1.0 + angular_noise + shoreline_noise:
                    land[py][px] = True

    island_spacing_x = max(5, int(round(_ISLAND_SPACING_X * w / _ATLAS_W)))
    island_spacing_y = max(4, int(round(_ISLAND_SPACING_Y * h / _ATLAS_H)))
    island_margin_x = max(2, int(round(_ISLAND_MARGIN * w / _ATLAS_W)))
    island_margin_y = max(1, int(round((_ISLAND_MARGIN - 1) * h / _ATLAS_H)))
    for ix in range(island_margin_x, max(w - island_margin_x, island_margin_x + 1), island_spacing_x):
        for iy in range(island_margin_y, max(h - island_margin_y, island_margin_y + 1), island_spacing_y):
            noise_val = _coast_noise(ix * 3, iy * 5)
            if noise_val > 0.15 and not land[iy][ix]:
                for dy2 in range(-1, 2):
                    for dx2 in range(-1, 2):
                        ny, nx = iy + dy2, ix + dx2
                        if 0 <= ny < h and 0 <= nx < w:
                            land[ny][nx] = True

    stamp_x = max(2, int(round(5 * w / _ATLAS_W)))
    stamp_y = max(1, int(round(3 * h / _ATLAS_H)))
    for ax, ay in site_atlas.values():
        for dy2 in range(-stamp_y, stamp_y + 1):
            for dx2 in range(-stamp_x, stamp_x + 1):
                ny, nx = ay + dy2, ax + dx2
                if 0 <= ny < h and 0 <= nx < w:
                    land[ny][nx] = True

    return land, [[False] * w for _ in range(h)]


def _build_layout_masks(
    info: "MapRenderInfo",
    site_atlas: Dict[str, Tuple[int, int]],
    w: int,
    h: int,
) -> Tuple[List[List[bool]], List[List[bool]]]:
    """Build land and mountain masks from stored layout or fallback logic."""
    if info.atlas_layout is None:
        return _build_legacy_masks(site_atlas, w, h)

    land: List[List[bool]] = [[False] * w for _ in range(h)]
    mountains: List[List[bool]] = [[False] * w for _ in range(h)]
    layout = info.atlas_layout

    for continent in layout.continents:
        _mark_layout_cells(
            land,
            continent.get("cells", []),
            src_w=layout.canvas_w,
            src_h=layout.canvas_h,
            dst_w=w,
            dst_h=h,
            value=True,
        )
    for sea in layout.seas:
        _mark_layout_cells(
            land,
            sea.get("cells", []),
            src_w=layout.canvas_w,
            src_h=layout.canvas_h,
            dst_w=w,
            dst_h=h,
            value=False,
        )
    for mountain_range in layout.mountain_ranges:
        cells = mountain_range.get("cells", [])
        _mark_layout_cells(
            mountains,
            cells,
            src_w=layout.canvas_w,
            src_h=layout.canvas_h,
            dst_w=w,
            dst_h=h,
            value=True,
        )
        _mark_layout_cells(
            land,
            cells,
            src_w=layout.canvas_w,
            src_h=layout.canvas_h,
            dst_w=w,
            dst_h=h,
            value=True,
        )

    if not any(any(row) for row in land):
        return _build_legacy_masks(site_atlas, w, h)

    for ax, ay in site_atlas.values():
        for dy2 in range(-1, 2):
            for dx2 in range(-1, 2):
                ny, nx = ay + dy2, ax + dx2
                if 0 <= ny < h and 0 <= nx < w:
                    land[ny][nx] = True

    return land, mountains


def _paint_terrain(
    canvas: List[List[str]],
    land: List[List[bool]],
    mountains: List[List[bool]],
    biome_seeds: List[Tuple[int, int, str]],
    w: int,
    h: int,
) -> None:
    """Paint terrain onto the atlas canvas from masks and biome seeds."""
    for py in range(h):
        for px in range(w):
            if not land[py][px]:
                canvas[py][px] = _terrain_char("ocean", px, py)
                continue

            best_d = float("inf")
            best_biome = "plains"
            for sx, sy, biome in biome_seeds:
                dist = (px - sx) ** 2 + (py - sy) ** 2
                if dist < best_d:
                    best_d = dist
                    best_biome = biome

            if best_biome == "ocean":
                best_biome = "coast"
            if mountains[py][px]:
                best_biome = "mountain"
            canvas[py][px] = _terrain_char(best_biome, px, py)

    for py in range(h):
        for px in range(w):
            if not land[py][px] or mountains[py][px]:
                continue
            for dy2, dx2 in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = py + dy2, px + dx2
                is_edge = not (0 <= ny < h and 0 <= nx < w)
                if is_edge or not land[ny][nx]:
                    canvas[py][px] = _terrain_char("coast", px, py)
                    break

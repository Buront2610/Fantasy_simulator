"""Atlas canvas construction helpers."""

from __future__ import annotations

import math
from typing import Dict, List, Set, Tuple, TYPE_CHECKING

from .atlas_data import (
    _ATLAS_H,
    _ATLAS_W,
    _MARGIN_X,
    _MARGIN_Y,
    _build_biome_seeds,
    _build_site_atlas,
    _scale_canvas_point,
)

if TYPE_CHECKING:
    from .map_renderer import MapCellInfo, MapRenderInfo


# Terrain character palette -- 4 chars per biome for variation.
_BIOME_CHARS: Dict[str, str] = {
    "ocean":    "~~~~",
    "coast":    "..`.",
    "plains":   ".,',",
    "forest":   "TtYf",
    "hills":    "nNnh",
    "mountain": "^^/\\",
    "swamp":    "%~%w",
    "desert":   ":.;:",
    "tundra":   "*.**",
    "river":    "=~=~",
}

# Route line chars: (horizontal, vertical, diag-up, diag-down)
_ROUTE_LINE: Dict[str, Tuple[str, str, str, str]] = {
    "road":           ("-", "|", "/", "\\"),
    "trail":          (".", ":", ".", "."),
    "sea_lane":       ("~", "~", "~", "~"),
    "mountain_pass":  ("^", "^", "^", "^"),
    "river_crossing": ("=", "|", "/", "\\"),
}

# Site marker varies by traffic band:
#   high traffic = 'O' (hub), medium = '@', low = 'o'.
_SITE_MARKERS: Dict[str, str] = {"high": "O", "medium": "@", "low": "o"}
_SITE_MARKER = "@"

# Island generation parameters
_ISLAND_SPACING_X = 11
_ISLAND_SPACING_Y = 9
_ISLAND_MARGIN = 3

# Characters that a route line may overwrite.
_TERRAIN_OVERWRITABLE = set("~.,'.TtYfnNnh^^/\\%w:.;:*=`")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _coast_noise(x: int, y: int) -> float:
    """Smooth deterministic noise for coastline variation."""
    return (
        0.25 * math.sin(x * 0.15 + 1.0) * math.cos(y * 0.2 + 2.0)
        + 0.15 * math.sin(x * 0.35 + 3.0) * math.sin(y * 0.25 + 1.5)
        + 0.10 * math.cos(x * 0.5 + y * 0.4 + 0.7)
    )


def _terrain_char(biome: str, x: int, y: int) -> str:
    """Pick a varied terrain character for *biome* at canvas (x, y)."""
    chars = _BIOME_CHARS.get(biome, ".,',")
    n = (x * 374761393 + y * 668265263) & 0xFFFFFFFF
    n = ((n ^ (n >> 13)) * 1274126177) & 0xFFFFFFFF
    return chars[n % len(chars)]


def _bresenham(
    x0: int, y0: int, x1: int, y1: int,
) -> List[Tuple[int, int]]:
    """Integer points along a line from (x0, y0) to (x1, y1)."""
    pts: List[Tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x1 > x0 else -1
    sy = 1 if y1 > y0 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        pts.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return pts


def _overlay_suffix(cell: "MapCellInfo") -> str:
    """Compact overlay markers for a site cell.

    Markers: ``!`` high danger, ``$`` high traffic, ``?`` high rumor,
    ``m`` memorial, ``a`` alias, ``+`` recent death.
    """
    parts: List[str] = []
    if cell.danger_band == "high":
        parts.append("!")
    if cell.traffic_band == "high":
        parts.append("$")
    if cell.rumor_heat_band == "high":
        parts.append("?")
    if cell.has_memorial:
        parts.append("m")
    if cell.has_alias:
        parts.append("a")
    if cell.recent_death_site:
        parts.append("+")
    return "".join(parts)


# ------------------------------------------------------------------
# Site clustering for multi-continent generation
# ------------------------------------------------------------------

def _cluster_sites(
    sites: List[Tuple[int, int]],
    max_clusters: int = 4,
) -> List[List[Tuple[int, int]]]:
    """Partition *sites* into spatial clusters (simple k-means).

    When sites are few (≤3) or tightly packed, a single cluster is
    returned.  Otherwise up to *max_clusters* groups are created so
    that the atlas renderer can draw separate land masses.

    Initial centroids are picked from a spatially-sorted order
    (sorted by x then y) so the result is stable regardless of the
    input order.
    """
    if len(sites) <= 3:
        return [sites]

    # Determine number of clusters from spread
    xs = [p[0] for p in sites]
    ys = [p[1] for p in sites]
    spread = max(max(xs) - min(xs), max(ys) - min(ys))
    if spread < 20:
        return [sites]

    k = min(max_clusters, max(2, len(sites) // 5))

    # Deterministic initial centroids: pick evenly spaced from
    # spatially-sorted sites so the result is order-independent.
    sorted_sites = sorted(sites)
    step = max(1, len(sorted_sites) // k)
    centroids = [sorted_sites[i * step % len(sorted_sites)] for i in range(k)]
    # Remove duplicate centroids
    seen: Set[Tuple[int, int]] = set()
    unique: List[Tuple[int, int]] = []
    for c in centroids:
        if c not in seen:
            seen.add(c)
            unique.append(c)
    centroids = unique
    k = len(centroids)
    if k < 2:
        return [sites]

    for _ in range(10):
        clusters: List[List[Tuple[int, int]]] = [[] for _ in range(k)]
        for pt in sites:
            best_i = 0
            best_d = float("inf")
            for ci, c in enumerate(centroids):
                d = (pt[0] - c[0]) ** 2 + (pt[1] - c[1]) ** 2
                if d < best_d:
                    best_d = d
                    best_i = ci
            clusters[best_i].append(pt)

        new_centroids: List[Tuple[int, int]] = []
        for cl in clusters:
            if cl:
                new_centroids.append((
                    int(sum(p[0] for p in cl) / len(cl)),
                    int(sum(p[1] for p in cl) / len(cl)),
                ))
            else:
                new_centroids.append(centroids[len(new_centroids)])
        if new_centroids == centroids:
            break
        centroids = new_centroids

    return [cl for cl in clusters if cl]


# ------------------------------------------------------------------
# Atlas canvas generation
# ------------------------------------------------------------------


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
                ang = (
                    0.15 * math.sin(angle * 3 + 1.0 + seed_off)
                    + 0.10 * math.sin(angle * 7 + 2.0 + seed_off)
                    + 0.06 * math.sin(angle * 13 + 3.0 + seed_off)
                )
                sp = _coast_noise(px + seed_off, py + seed_off)

                if dist < 1.0 + ang + sp:
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
                d = (px - sx) ** 2 + (py - sy) ** 2
                if d < best_d:
                    best_d = d
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


def _build_atlas_canvas(  # noqa: C901 — linear but long
    info: "MapRenderInfo",
) -> List[List[str]]:
    """Generate the full atlas canvas from *MapRenderInfo*.

    When cells carry pre-computed ``atlas_x`` / ``atlas_y`` coordinates
    (≥ 0), those are reused instead of re-projecting from the grid.
    This ensures the atlas map is stable across renders and matches
    the coordinates persisted in the save file.
    """
    canvas, site_atlas = _build_atlas_base_canvas(info, _ATLAS_W, _ATLAS_H)
    _place_labels(canvas, info, site_atlas, _ATLAS_W, _ATLAS_H)
    return canvas


# ------------------------------------------------------------------
# Route drawing
# ------------------------------------------------------------------

def _draw_routes(
    canvas: List[List[str]],
    info: "MapRenderInfo",
    site_atlas: Dict[str, Tuple[int, int]],
    w: int,
    h: int,
) -> None:
    """Draw route lines between connected sites.

    High-traffic route endpoints use doubled line chars (``==`` for
    road instead of ``--``) to visually distinguish busy corridors.
    """
    protected: Set[Tuple[int, int]] = set(site_atlas.values())

    # Build a lookup of traffic bands for sites so we can detect
    # "high-traffic corridor" routes.
    site_traffic: Dict[str, str] = {
        c.location_id: c.traffic_band for c in info.cells.values()
    }

    for route in info.routes:
        fp = site_atlas.get(route.from_site_id)
        tp = site_atlas.get(route.to_site_id)
        if not fp or not tp:
            continue

        rtype = route.route_type
        chars = _ROUTE_LINE.get(rtype, ("-", "|", "/", "\\"))
        if route.blocked:
            chars = ("x", "x", "x", "x")
        else:
            # High-traffic corridors: both endpoints high → uppercase
            ft = site_traffic.get(route.from_site_id, "low")
            tt = site_traffic.get(route.to_site_id, "low")
            if ft == "high" and tt == "high" and rtype == "road":
                chars = ("=", "H", "/", "\\")

        path = _bresenham(fp[0], fp[1], tp[0], tp[1])
        for i, (px, py) in enumerate(path):
            if (px, py) in protected:
                continue
            if not (0 <= py < h and 0 <= px < w):
                continue

            # Direction from previous point
            if i > 0:
                ddx = px - path[i - 1][0]
                ddy = py - path[i - 1][1]
            elif i < len(path) - 1:
                ddx = path[i + 1][0] - px
                ddy = path[i + 1][1] - py
            else:
                ddx, ddy = 1, 0

            if ddy == 0:
                ch = chars[0]
            elif ddx == 0:
                ch = chars[1]
            elif (ddx > 0) != (ddy > 0):
                ch = chars[2]
            else:
                ch = chars[3]

            cur = canvas[py][px]
            if cur in _TERRAIN_OVERWRITABLE:
                canvas[py][px] = ch


# ------------------------------------------------------------------
# Label placement
# ------------------------------------------------------------------

def _place_labels(
    canvas: List[List[str]],
    info: "MapRenderInfo",
    site_atlas: Dict[str, Tuple[int, int]],
    w: int,
    h: int,
    *,
    place_names: bool = True,
) -> Set[str]:
    """Place site markers and name labels on the canvas.

    Site marker glyph varies by traffic band: ``O`` hub (high),
    ``@`` normal (medium), ``o`` quiet (low).  High-rumor sites
    get a ``?`` halo in unoccupied adjacent cells.
    """
    occupied: Set[Tuple[int, int]] = {
        (ax, ay)
        for ax, ay in site_atlas.values()
        if 0 <= ay < h and 0 <= ax < w
    }
    labeled_ids: Set[str] = set()

    # Higher-importance sites get label priority.
    cells_sorted = sorted(
        info.cells.values(),
        key=lambda c: -c.site_importance,
    )

    for cell in cells_sorted:
        pos = site_atlas.get(cell.location_id)
        if not pos:
            continue
        ax, ay = pos

        # Site marker — traffic-aware glyph
        marker = _SITE_MARKERS.get(cell.traffic_band, _SITE_MARKER)
        if 0 <= ay < h and 0 <= ax < w:
            canvas[ay][ax] = marker

        if not place_names:
            continue

        # Build label text
        name = cell.canonical_name
        if len(name) > 14:
            name = name[:13] + "."
        ov = _overlay_suffix(cell)
        label = f"{name}[{ov}]" if ov else name

        # Try placement directions: right, left, below, above
        candidates = [
            (ax + 1, ay),
            (ax - len(label), ay),
            (ax + 1, ay + 1),
            (ax + 1, ay - 1),
        ]
        for lx, ly in candidates:
            if lx < 0 or ly < 0 or ly >= h or lx + len(label) > w:
                continue
            if any((lx + i, ly) in occupied for i in range(len(label))):
                continue
            for i, ch in enumerate(label):
                canvas[ly][lx + i] = ch
                occupied.add((lx + i, ly))
            labeled_ids.add(cell.location_id)
            break

    # --- Rumor halo: place '?' around high-rumor sites ---
    for cell in info.cells.values():
        if cell.rumor_heat_band != "high":
            continue
        pos = site_atlas.get(cell.location_id)
        if not pos:
            continue
        ax, ay = pos
        for dy2, dx2 in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nx, ny = ax + dx2, ay + dy2
            if 0 <= ny < h and 0 <= nx < w and (nx, ny) not in occupied:
                canvas[ny][nx] = "?"
                occupied.add((nx, ny))

    return labeled_ids

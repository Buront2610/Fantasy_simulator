"""
atlas_renderer.py - Atlas-scale world map with continent and terrain.

PR-G2 core: Provides a "world map" experience where the game's
location network (5x5 or variable) is projected onto a larger terrain
canvas.  The atlas shows:

* Continent silhouette with organic coastlines
* Terrain zones (mountains, forests, plains ...) as continuous areas
* Named locations as anchor points with labels
* Route paths as visible lines between locations
* Overlay markers for danger, memorials, aliases, deaths

The atlas canvas is *separate* from the game grid -- locations are
anchor points on the map, not the map itself.
"""

from __future__ import annotations

import math
from typing import Dict, List, Set, Tuple, TYPE_CHECKING

from ..i18n import tr, tr_term

if TYPE_CHECKING:
    from .map_renderer import MapCellInfo, MapRenderInfo


# ------------------------------------------------------------------
# Constants
# ------------------------------------------------------------------

_ATLAS_W = 72
_ATLAS_H = 30
_MARGIN_X = 6
_MARGIN_Y = 3

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

def _build_atlas_canvas(  # noqa: C901 — linear but long
    info: "MapRenderInfo",
) -> List[List[str]]:
    """Generate the full atlas canvas from *MapRenderInfo*.

    When cells carry pre-computed ``atlas_x`` / ``atlas_y`` coordinates
    (≥ 0), those are reused instead of re-projecting from the grid.
    This ensures the atlas map is stable across renders and matches
    the coordinates persisted in the save file.
    """
    w, h = _ATLAS_W, _ATLAS_H
    canvas: List[List[str]] = [["~"] * w for _ in range(h)]

    if not info.cells:
        return canvas

    # --- Map grid positions to atlas coordinates ---
    avail_w = w - 2 * _MARGIN_X
    avail_h = h - 2 * _MARGIN_Y
    step_x = avail_w / max(info.width - 1, 1)
    step_y = avail_h / max(info.height - 1, 1)

    site_atlas: Dict[str, Tuple[int, int]] = {}
    biome_seeds: List[Tuple[int, int, str]] = []

    for (gx, gy), cell in info.cells.items():
        if cell.atlas_x >= 0 and cell.atlas_y >= 0:
            ax, ay = cell.atlas_x, cell.atlas_y
        else:
            ax = int(_MARGIN_X + gx * step_x)
            ay = int(_MARGIN_Y + gy * step_y)
        site_atlas[cell.location_id] = (ax, ay)
        biome_seeds.append((ax, ay, cell.terrain_biome))

    # Include terrain-only cells as additional biome seeds.
    site_coords: Set[Tuple[int, int]] = set(site_atlas.values())
    for (gx, gy), tcell in info.terrain_cells.items():
        ax = int(_MARGIN_X + gx * step_x)
        ay = int(_MARGIN_Y + gy * step_y)
        if (ax, ay) not in site_coords:
            biome_seeds.append((ax, ay, tcell.biome))

    # --- 1. Multi-continent land mask ---
    land: List[List[bool]] = [[False] * w for _ in range(h)]
    clusters = _cluster_sites(list(site_atlas.values()))

    for cluster in clusters:
        cx = sum(p[0] for p in cluster) / len(cluster)
        cy = sum(p[1] for p in cluster) / len(cluster)
        span_x = (max(p[0] for p in cluster) - min(p[0] for p in cluster)) / 2
        span_y = (max(p[1] for p in cluster) - min(p[1] for p in cluster)) / 2
        rx = span_x + _MARGIN_X + 1
        ry = span_y + _MARGIN_Y + 1
        # Offset noise seed per cluster so each land mass has unique coastline.
        # (coprime multipliers give good decorrelation across clusters.)
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

    # Small scattered islands for visual richness
    for ix in range(_ISLAND_MARGIN, w - _ISLAND_MARGIN, _ISLAND_SPACING_X):
        for iy in range(_ISLAND_MARGIN - 1, h - (_ISLAND_MARGIN - 1), _ISLAND_SPACING_Y):
            noise_val = _coast_noise(ix * 3, iy * 5)
            if noise_val > 0.15 and not land[iy][ix]:
                for dy2 in range(-1, 2):
                    for dx2 in range(-1, 2):
                        ny, nx = iy + dy2, ix + dx2
                        if 0 <= ny < h and 0 <= nx < w:
                            land[ny][nx] = True

    # Force land around every site (radius 3×5).
    for ax, ay in site_atlas.values():
        for dy2 in range(-3, 4):
            for dx2 in range(-5, 6):
                ny, nx = ay + dy2, ax + dx2
                if 0 <= ny < h and 0 <= nx < w:
                    land[ny][nx] = True

    # --- 2. Assign terrain biomes (nearest seed) ---
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
            canvas[py][px] = _terrain_char(best_biome, px, py)

    # --- 3. Mark coastline cells ---
    for py in range(h):
        for px in range(w):
            if not land[py][px]:
                continue
            for dy2, dx2 in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                ny, nx = py + dy2, px + dx2
                is_edge = not (0 <= ny < h and 0 <= nx < w)
                if is_edge or not land[ny][nx]:
                    canvas[py][px] = _terrain_char("coast", px, py)
                    break

    # --- 4. Draw routes ---
    _draw_routes(canvas, info, site_atlas, w, h)

    # --- 5. Place site markers and labels ---
    _place_labels(canvas, info, site_atlas, w, h)

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
) -> None:
    """Place site markers and name labels on the canvas.

    Site marker glyph varies by traffic band: ``O`` hub (high),
    ``@`` normal (medium), ``o`` quiet (low).  High-rumor sites
    get a ``?`` halo in unoccupied adjacent cells.
    """
    occupied: Set[Tuple[int, int]] = set()

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
            occupied.add((ax, ay))

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
    canvas: List[List[str]] = [["~"] * w for _ in range(h)]

    if not info.cells:
        return "\n".join("  " + "".join(row) for row in canvas)

    avail_w = w - 4
    avail_h = h - 2
    step_x = avail_w / max(info.width - 1, 1)
    step_y = avail_h / max(info.height - 1, 1)

    site_atlas: Dict[str, Tuple[int, int]] = {}
    biome_seeds: List[Tuple[int, int, str]] = []

    for (gx, gy), cell in info.cells.items():
        if cell.atlas_x >= 0 and cell.atlas_y >= 0:
            # Scale pre-computed coords to compact size
            ax = int(cell.atlas_x * w / _ATLAS_W)
            ay = int(cell.atlas_y * h / _ATLAS_H)
        else:
            ax = int(2 + gx * step_x)
            ay = int(1 + gy * step_y)
        ax = max(0, min(w - 1, ax))
        ay = max(0, min(h - 1, ay))
        site_atlas[cell.location_id] = (ax, ay)
        biome_seeds.append((ax, ay, cell.terrain_biome))

    # Simple land mask: radius-2 circle around each site
    land: List[List[bool]] = [[False] * w for _ in range(h)]
    for ax, ay in site_atlas.values():
        for dy2 in range(-2, 3):
            for dx2 in range(-3, 4):
                ny, nx = ay + dy2, ax + dx2
                if 0 <= ny < h and 0 <= nx < w:
                    land[ny][nx] = True

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
            canvas[py][px] = _terrain_char(best_biome, px, py)

    # Place markers
    for cell in sorted(info.cells.values(), key=lambda c: -c.site_importance):
        pos = site_atlas.get(cell.location_id)
        if pos:
            ax, ay = pos
            if 0 <= ay < h and 0 <= ax < w:
                marker = _SITE_MARKERS.get(cell.traffic_band, _SITE_MARKER)
                canvas[ay][ax] = marker

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
    cells_sorted = sorted(
        info.cells.values(),
        key=lambda c: (-c.site_importance, c.canonical_name),
    )
    return [
        (cell.location_id, cell.canonical_name)
        for cell in cells_sorted
    ]

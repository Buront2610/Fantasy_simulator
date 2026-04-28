"""Route-layer drawing for atlas canvases."""

from __future__ import annotations

from typing import Dict, List, Set, Tuple, TYPE_CHECKING

from .atlas_geometry import _bresenham
from .atlas_palette import _ROUTE_LINE, _TERRAIN_OVERWRITABLE

if TYPE_CHECKING:
    from .map_renderer import MapRenderInfo


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

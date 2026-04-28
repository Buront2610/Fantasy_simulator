"""Grid and route-layer helpers for zoomed region maps."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from .atlas_canvas import _ROUTE_LINE, _bresenham
from .map_view_models import MapCellInfo, MapRenderInfo


RegionBounds = Tuple[int, int, int, int]


def find_region_center_cell(info: MapRenderInfo, center_location_id: str) -> Optional[MapCellInfo]:
    for cell in info.cells.values():
        if cell.location_id == center_location_id:
            return cell
    return None


def region_bounds(info: MapRenderInfo, center_cell: MapCellInfo, radius: int) -> RegionBounds:
    cx, cy = center_cell.x, center_cell.y
    return (
        max(0, cx - radius),
        min(info.width - 1, cx + radius),
        max(0, cy - radius),
        min(info.height - 1, cy + radius),
    )


def visible_region_cells(info: MapRenderInfo, bounds: RegionBounds) -> List[MapCellInfo]:
    x_min, x_max, y_min, y_max = bounds
    return [
        cell for cell in sorted(info.cells.values(), key=lambda c: (c.y, c.x))
        if x_min <= cell.x <= x_max and y_min <= cell.y <= y_max
    ]


def build_region_route_layer(info: MapRenderInfo, bounds: RegionBounds) -> Dict[Tuple[int, int], str]:
    x_min, x_max, y_min, y_max = bounds
    rw = x_max - x_min + 1
    rh = y_max - y_min + 1
    route_layer: Dict[Tuple[int, int], str] = {}
    site_positions: Set[Tuple[int, int]] = set()
    for cell in info.cells.values():
        if x_min <= cell.x <= x_max and y_min <= cell.y <= y_max:
            site_positions.add((cell.x - x_min, cell.y - y_min))

    cell_pos: Dict[str, Tuple[int, int]] = {
        c.location_id: (c.x, c.y) for c in info.cells.values()
    }
    for route in info.routes:
        fp = cell_pos.get(route.from_site_id)
        tp = cell_pos.get(route.to_site_id)
        if not fp or not tp:
            continue
        if not (x_min <= fp[0] <= x_max and y_min <= fp[1] <= y_max):
            continue
        if not (x_min <= tp[0] <= x_max and y_min <= tp[1] <= y_max):
            continue
        path = _bresenham(fp[0] - x_min, fp[1] - y_min, tp[0] - x_min, tp[1] - y_min)
        chars = _ROUTE_LINE.get(route.route_type, ("-", "|", "/", "\\"))
        if route.blocked:
            chars = ("x", "x", "x", "x")
        for i, (px, py) in enumerate(path):
            if (px, py) in site_positions or not (0 <= px < rw and 0 <= py < rh):
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
            route_layer[(px, py)] = ch
    return route_layer


def append_region_grid(
    lines: List[str],
    info: MapRenderInfo,
    center_location_id: str,
    bounds: RegionBounds,
    route_layer: Dict[Tuple[int, int], str],
) -> None:
    x_min, x_max, y_min, y_max = bounds
    col_nums = "".join(f"{x % 10}" for x in range(x_min, x_max + 1))
    lines.append(f"      {col_nums}")
    region_border = "     +" + "-" * (x_max - x_min + 1) + "+"
    lines.append(region_border)

    for y in range(y_min, y_max + 1):
        row_chars: List[str] = []
        for x in range(x_min, x_max + 1):
            cell = info.cells.get((x, y))
            if cell is not None:
                if cell.location_id == center_location_id:
                    row_chars.append("@")
                else:
                    row_chars.append(cell.canonical_name[0].upper() if cell.canonical_name else "o")
            elif (x - x_min, y - y_min) in route_layer:
                row_chars.append(route_layer[(x - x_min, y - y_min)])
            else:
                tcell = info.terrain_cells.get((x, y))
                row_chars.append(tcell.glyph if tcell else " ")
        lines.append(f"    {y % 10}|{''.join(row_chars)}|")

    lines.append(region_border)

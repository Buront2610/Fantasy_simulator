"""Grid and route-layer helpers for zoomed region maps."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from ..i18n import tr
from .atlas_canvas import _ROUTE_LINE, _bresenham
from .map_view_models import MapCellInfo, MapRenderInfo


RegionBounds = Tuple[int, int, int, int]
_REGION_SKETCH_X_STEP = 6
_REGION_SKETCH_Y_STEP = 3
_REGION_DETAIL_CELL_W = 5
_REGION_DETAIL_CELL_H = 3


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


def _region_sketch_site_positions(info: MapRenderInfo, bounds: RegionBounds) -> Dict[str, Tuple[int, int]]:
    x_min, _x_max, y_min, _y_max = bounds
    return {
        cell.location_id: (
            (cell.x - x_min) * _REGION_SKETCH_X_STEP + 1,
            (cell.y - y_min) * _REGION_SKETCH_Y_STEP + 1,
        )
        for cell in info.cells.values()
        if bounds[0] <= cell.x <= bounds[1] and bounds[2] <= cell.y <= bounds[3]
    }


def _region_sketch_route_char(route_type: str, blocked: bool, ddx: int, ddy: int) -> str:
    chars = _ROUTE_LINE.get(route_type, ("-", "|", "/", "\\"))
    if blocked:
        chars = ("x", "x", "x", "x")
    if ddy == 0:
        return chars[0]
    if ddx == 0:
        return chars[1]
    if (ddx > 0) != (ddy > 0):
        return chars[2]
    return chars[3]


def _region_sketch_step_delta(path: List[Tuple[int, int]], index: int) -> Tuple[int, int]:
    px, py = path[index]
    if index > 0:
        prev_x, prev_y = path[index - 1]
        return px - prev_x, py - prev_y
    if index < len(path) - 1:
        next_x, next_y = path[index + 1]
        return next_x - px, next_y - py
    return 1, 0


def _route_bend_seed(route_id: str) -> int:
    return sum((index + 1) * ord(ch) for index, ch in enumerate(route_id))


def _clamp_sketch_coord(value: int, lower: int, upper: int) -> int:
    return max(lower, min(upper, value))


def _append_segment_path(
    path: List[Tuple[int, int]],
    start: Tuple[int, int],
    end: Tuple[int, int],
) -> None:
    segment = _bresenham(start[0], start[1], end[0], end[1])
    if path and segment and path[-1] == segment[0]:
        path.extend(segment[1:])
    else:
        path.extend(segment)


def _region_sketch_route_path(
    route_id: str,
    start: Tuple[int, int],
    end: Tuple[int, int],
    width: int,
    height: int,
) -> List[Tuple[int, int]]:
    sx, sy = start
    tx, ty = end
    dx = tx - sx
    dy = ty - sy
    if abs(dx) + abs(dy) < 6:
        return _bresenham(sx, sy, tx, ty)

    seed = _route_bend_seed(route_id)
    bend = (seed % 3) + 1
    bend *= -1 if seed % 2 else 1
    mid_x = _clamp_sketch_coord((sx + tx) // 2, 1, width - 2)
    mid_y = _clamp_sketch_coord((sy + ty) // 2, 1, height - 2)

    if abs(dx) >= abs(dy):
        mid_y = _clamp_sketch_coord(mid_y + bend, 1, height - 2)
    else:
        mid_x = _clamp_sketch_coord(mid_x + bend, 1, width - 2)

    path: List[Tuple[int, int]] = []
    _append_segment_path(path, start, (mid_x, mid_y))
    _append_segment_path(path, (mid_x, mid_y), end)
    return path


def _paint_region_sketch_routes(
    canvas: List[List[str]],
    info: MapRenderInfo,
    site_positions: Dict[str, Tuple[int, int]],
    protected_centers: Set[Tuple[int, int]],
) -> None:
    height = len(canvas)
    width = len(canvas[0]) if canvas else 0
    for route in info.routes:
        fp = site_positions.get(route.from_site_id)
        tp = site_positions.get(route.to_site_id)
        if not fp or not tp:
            continue
        path = _region_sketch_route_path(route.route_id, fp, tp, width, height)
        for index, (px, py) in enumerate(path):
            if (px, py) in protected_centers or not (0 <= px < width and 0 <= py < height):
                continue
            ddx, ddy = _region_sketch_step_delta(path, index)
            canvas[py][px] = _region_sketch_route_char(route.route_type, route.blocked, ddx, ddy)


def _region_sketch_site_marker(cell: MapCellInfo, center_location_id: str) -> str:
    if cell.location_id == center_location_id:
        return "@"
    if cell.site_type == "city":
        return "C"
    if cell.site_type == "dungeon":
        return "D"
    if cell.traffic_band == "high":
        return "O"
    return "o"


def _paint_city_block(
    canvas: List[List[str]],
    x: int,
    y: int,
    marker: str,
) -> None:
    height = len(canvas)
    width = len(canvas[0]) if canvas else 0
    rows = (
        "###",
        f"#{marker}#",
        "#=#",
    )
    for dy, row in enumerate(rows, start=-1):
        py = y + dy
        if not (0 <= py < height):
            continue
        for dx, ch in enumerate(row, start=-1):
            px = x + dx
            if 0 <= px < width:
                canvas[py][px] = ch


def _paint_region_sketch_sites(
    canvas: List[List[str]],
    info: MapRenderInfo,
    site_positions: Dict[str, Tuple[int, int]],
    center_location_id: str,
) -> None:
    for cell in info.cells.values():
        pos = site_positions.get(cell.location_id)
        if not pos:
            continue
        marker = _region_sketch_site_marker(cell, center_location_id)
        if cell.site_type == "city" or cell.region_type == "city":
            _paint_city_block(canvas, pos[0], pos[1], marker)
        else:
            canvas[pos[1]][pos[0]] = marker


def _terrain_detail_tile(info: MapRenderInfo, x: int, y: int) -> List[List[str]]:
    glyph = " "
    tcell = info.terrain_cells.get((x, y))
    if tcell is not None:
        glyph = tcell.glyph
    return [[glyph for _ in range(_REGION_DETAIL_CELL_W)] for _ in range(_REGION_DETAIL_CELL_H)]


def _paint_detail_city(tile: List[List[str]], marker: str) -> None:
    rows = (
        " ### ",
        f" #{marker}# ",
        " #=# ",
    )
    for y, row in enumerate(rows):
        tile[y] = list(row)


def _paint_detail_site(tile: List[List[str]], cell: MapCellInfo, center_location_id: str) -> None:
    marker = _region_sketch_site_marker(cell, center_location_id)
    if cell.site_type == "city" or cell.region_type == "city":
        _paint_detail_city(tile, marker)
        return
    if cell.site_type == "dungeon" or cell.region_type == "dungeon":
        tile[0][2] = "/"
        tile[1][2] = marker
        tile[2][2] = "\\"
        return
    tile[1][2] = marker


def _paint_detail_route(tile: List[List[str]], route_char: str) -> None:
    if route_char in ("-", "=", "x"):
        tile[1][1:4] = [route_char, route_char, route_char]
    elif route_char in ("|", "H"):
        for y in range(_REGION_DETAIL_CELL_H):
            tile[y][2] = route_char
    else:
        tile[1][2] = route_char


def append_region_detail_grid(
    lines: List[str],
    info: MapRenderInfo,
    center_location_id: str,
    bounds: RegionBounds,
    route_layer: Dict[Tuple[int, int], str],
) -> None:
    x_min, x_max, y_min, y_max = bounds
    width = (x_max - x_min + 1) * _REGION_DETAIL_CELL_W

    lines.append("")
    lines.append(f"  {tr('map_region_detail_grid')}:")
    lines.append("    +" + "-" * width + "+")
    for y in range(y_min, y_max + 1):
        rows = ["" for _ in range(_REGION_DETAIL_CELL_H)]
        for x in range(x_min, x_max + 1):
            tile = _terrain_detail_tile(info, x, y)
            cell = info.cells.get((x, y))
            if cell is not None:
                _paint_detail_site(tile, cell, center_location_id)
            else:
                route_char = route_layer.get((x - x_min, y - y_min))
                if route_char is not None:
                    _paint_detail_route(tile, route_char)
            for row_index, tile_row in enumerate(tile):
                rows[row_index] += "".join(tile_row)
        for rendered_row in rows:
            lines.append("    |" + rendered_row + "|")
    lines.append("    +" + "-" * width + "+")


def append_region_route_sketch(
    lines: List[str],
    info: MapRenderInfo,
    center_location_id: str,
    bounds: RegionBounds,
) -> None:
    x_min, x_max, y_min, y_max = bounds
    width = (x_max - x_min) * _REGION_SKETCH_X_STEP + 3
    height = (y_max - y_min) * _REGION_SKETCH_Y_STEP + 3
    if width <= 1 or height <= 1:
        return

    site_positions = _region_sketch_site_positions(info, bounds)
    if not site_positions:
        return

    canvas: List[List[str]] = [[" " for _ in range(width)] for _ in range(height)]
    protected_centers: Set[Tuple[int, int]] = set(site_positions.values())

    _paint_region_sketch_routes(canvas, info, site_positions, protected_centers)
    _paint_region_sketch_sites(canvas, info, site_positions, center_location_id)

    lines.append("")
    lines.append(f"  {tr('map_region_route_sketch')}:")
    lines.append("    +" + "-" * width + "+")
    for row in canvas:
        lines.append("    |" + "".join(row).rstrip().ljust(width) + "|")
    lines.append("    +" + "-" * width + "+")


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
    append_region_detail_grid(lines, info, center_location_id, bounds, route_layer)

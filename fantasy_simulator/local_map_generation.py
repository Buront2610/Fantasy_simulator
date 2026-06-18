"""Deterministic local map generation for location detail views."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any, Iterable


LOCAL_MAP_WIDTH = 37
LOCAL_MAP_HEIGHT = 15


@dataclass(frozen=True)
class GeneratedLocalMap:
    """Small ASCII local map plus a compact legend."""

    lines: list[str]
    legend_keys: tuple[str, ...]


def generate_local_map(cell: Any, connected_cells: Iterable[Any] = ()) -> GeneratedLocalMap:
    """Generate a stable local map for one location.

    The generator is deterministic for the location id and broad state, so the
    same save renders consistently while different towns and dungeons stop
    looking like clones.
    """
    region_type = str(getattr(cell, "region_type", "plains") or "plains")
    rng = random.Random(_seed_for_cell(cell))
    route_directions = _route_directions(cell, connected_cells)
    if region_type == "dungeon":
        return _generate_dungeon_map(rng, route_directions)
    if region_type in {"city", "village"}:
        return _generate_settlement_map(rng, route_directions, dense=region_type == "city")
    if region_type == "forest":
        return _generate_wild_map(rng, route_directions, tree_char="T", feature_char="^")
    if region_type == "mountain":
        return _generate_wild_map(rng, route_directions, tree_char="^", feature_char="*")
    return _generate_wild_map(rng, route_directions, tree_char=",", feature_char="o")


def _seed_for_cell(cell: Any) -> int:
    seed_text = "|".join(
        str(getattr(cell, name, ""))
        for name in (
            "location_id",
            "region_type",
            "x",
            "y",
            "danger",
            "terrain_biome",
            "terrain_elevation",
            "terrain_moisture",
        )
    )
    return int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)


def _blank_canvas(fill: str = " ") -> list[list[str]]:
    return [[fill for _ in range(LOCAL_MAP_WIDTH)] for _ in range(LOCAL_MAP_HEIGHT)]


def _bordered_canvas(fill: str = " ") -> list[list[str]]:
    canvas = _blank_canvas(fill)
    for x in range(LOCAL_MAP_WIDTH):
        canvas[0][x] = "#"
        canvas[LOCAL_MAP_HEIGHT - 1][x] = "#"
    for y in range(LOCAL_MAP_HEIGHT):
        canvas[y][0] = "#"
        canvas[y][LOCAL_MAP_WIDTH - 1] = "#"
    return canvas


def _route_directions(cell: Any, connected_cells: Iterable[Any]) -> set[str]:
    directions: set[str] = set()
    origin_x = int(getattr(cell, "x", 0) or 0)
    origin_y = int(getattr(cell, "y", 0) or 0)
    for other in connected_cells:
        dx = int(getattr(other, "x", origin_x) or origin_x) - origin_x
        dy = int(getattr(other, "y", origin_y) or origin_y) - origin_y
        if abs(dx) >= abs(dy) and dx:
            directions.add("east" if dx > 0 else "west")
        elif dy:
            directions.add("south" if dy > 0 else "north")
    return directions


def _apply_route_gates(canvas: list[list[str]], directions: set[str], *, road_char: str) -> None:
    mid_x = LOCAL_MAP_WIDTH // 2
    mid_y = LOCAL_MAP_HEIGHT // 2
    if "north" in directions:
        canvas[0][mid_x] = "+"
        for y in range(1, mid_y + 1):
            canvas[y][mid_x] = road_char
    if "south" in directions:
        canvas[LOCAL_MAP_HEIGHT - 1][mid_x] = "+"
        for y in range(mid_y, LOCAL_MAP_HEIGHT - 1):
            canvas[y][mid_x] = road_char
    if "west" in directions:
        canvas[mid_y][0] = "+"
        for x in range(1, mid_x + 1):
            canvas[mid_y][x] = road_char
    if "east" in directions:
        canvas[mid_y][LOCAL_MAP_WIDTH - 1] = "+"
        for x in range(mid_x, LOCAL_MAP_WIDTH - 1):
            canvas[mid_y][x] = road_char


def _generate_settlement_map(rng: random.Random, route_directions: set[str], *, dense: bool) -> GeneratedLocalMap:
    canvas = _bordered_canvas(" ")
    mid_x = LOCAL_MAP_WIDTH // 2
    mid_y = LOCAL_MAP_HEIGHT // 2
    for x in range(1, LOCAL_MAP_WIDTH - 1):
        canvas[mid_y][x] = "="
    for y in range(1, LOCAL_MAP_HEIGHT - 1):
        canvas[y][mid_x] = "|"
    _apply_route_gates(canvas, route_directions or {"north", "south", "east", "west"}, road_char="=")
    canvas[mid_y][mid_x] = "@"

    building_count = 18 if dense else 10
    for _ in range(building_count):
        w = rng.randint(2, 4)
        h = rng.randint(1, 2)
        x = rng.randint(2, LOCAL_MAP_WIDTH - w - 3)
        y = rng.randint(2, LOCAL_MAP_HEIGHT - h - 3)
        if abs(x - mid_x) <= 2 or abs(y - mid_y) <= 1:
            continue
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                canvas[yy][xx] = "#"
        canvas[y][x + rng.randrange(w)] = "+"

    for _ in range(6 if dense else 10):
        x = rng.randint(2, LOCAL_MAP_WIDTH - 3)
        y = rng.randint(2, LOCAL_MAP_HEIGHT - 3)
        if canvas[y][x] == " ":
            canvas[y][x] = "T" if not dense else "."
    canvas[mid_y - 1][mid_x - 1] = "o"
    return GeneratedLocalMap(_stringify(canvas), ("local_map_legend_settlement", "local_map_legend_route_gate"))


def _generate_dungeon_map(rng: random.Random, route_directions: set[str]) -> GeneratedLocalMap:
    canvas = _bordered_canvas("#")
    rooms: list[tuple[int, int, int, int]] = []
    for _ in range(9):
        w = rng.randint(4, 8)
        h = rng.randint(3, 5)
        x = rng.randint(1, LOCAL_MAP_WIDTH - w - 2)
        y = rng.randint(1, LOCAL_MAP_HEIGHT - h - 2)
        candidate = (x, y, w, h)
        if any(_rooms_overlap(candidate, room) for room in rooms):
            continue
        rooms.append(candidate)
        _carve_room(canvas, candidate)

    if not rooms:
        fallback = (LOCAL_MAP_WIDTH // 2 - 3, LOCAL_MAP_HEIGHT // 2 - 2, 7, 5)
        rooms.append(fallback)
        _carve_room(canvas, fallback)

    centers = [_room_center(room) for room in rooms]
    for start, end in zip(centers, centers[1:]):
        if rng.random() < 0.5:
            _carve_h_corridor(canvas, start[0], end[0], start[1])
            _carve_v_corridor(canvas, start[1], end[1], end[0])
        else:
            _carve_v_corridor(canvas, start[1], end[1], start[0])
            _carve_h_corridor(canvas, start[0], end[0], end[1])

    entrance = centers[0]
    exit_pos = centers[-1]
    canvas[entrance[1]][entrance[0]] = "@"
    canvas[exit_pos[1]][exit_pos[0]] = ">"
    for marker in ("?", "!", "!"):
        room = rng.choice(rooms)
        x, y = _random_floor_in_room(rng, room)
        if canvas[y][x] == ".":
            canvas[y][x] = marker
    _apply_route_gates(canvas, route_directions or {"south"}, road_char=".")
    return GeneratedLocalMap(_stringify(canvas), ("local_map_legend_dungeon", "local_map_legend_route_gate"))


def _generate_wild_map(
    rng: random.Random,
    route_directions: set[str],
    *,
    tree_char: str,
    feature_char: str,
) -> GeneratedLocalMap:
    canvas = _bordered_canvas(" ")
    _apply_route_gates(canvas, route_directions or {"west", "east"}, road_char=".")
    canvas[LOCAL_MAP_HEIGHT // 2][LOCAL_MAP_WIDTH // 2] = "@"
    for _ in range(85):
        x = rng.randint(1, LOCAL_MAP_WIDTH - 2)
        y = rng.randint(1, LOCAL_MAP_HEIGHT - 2)
        if canvas[y][x] == " ":
            canvas[y][x] = tree_char if rng.random() < 0.75 else feature_char
    for _ in range(2):
        y = rng.randint(2, LOCAL_MAP_HEIGHT - 3)
        for x in range(1, LOCAL_MAP_WIDTH - 1):
            if canvas[y][x] in {" ", tree_char} and rng.random() < 0.75:
                canvas[y][x] = "."
    return GeneratedLocalMap(_stringify(canvas), ("local_map_legend_wild", "local_map_legend_route_gate"))


def _rooms_overlap(first: tuple[int, int, int, int], second: tuple[int, int, int, int]) -> bool:
    ax, ay, aw, ah = first
    bx, by, bw, bh = second
    return ax <= bx + bw and bx <= ax + aw and ay <= by + bh and by <= ay + ah


def _carve_room(canvas: list[list[str]], room: tuple[int, int, int, int]) -> None:
    x, y, w, h = room
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            canvas[yy][xx] = "."


def _room_center(room: tuple[int, int, int, int]) -> tuple[int, int]:
    x, y, w, h = room
    return x + w // 2, y + h // 2


def _random_floor_in_room(rng: random.Random, room: tuple[int, int, int, int]) -> tuple[int, int]:
    x, y, w, h = room
    return rng.randint(x, x + w - 1), rng.randint(y, y + h - 1)


def _carve_h_corridor(canvas: list[list[str]], start_x: int, end_x: int, y: int) -> None:
    for x in range(min(start_x, end_x), max(start_x, end_x) + 1):
        canvas[y][x] = "."


def _carve_v_corridor(canvas: list[list[str]], start_y: int, end_y: int, x: int) -> None:
    for y in range(min(start_y, end_y), max(start_y, end_y) + 1):
        canvas[y][x] = "."


def _stringify(canvas: list[list[str]]) -> list[str]:
    return ["".join(row).rstrip().ljust(LOCAL_MAP_WIDTH) for row in canvas]

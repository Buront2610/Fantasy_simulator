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
    scene_keys: tuple[str, ...] = ()
    exterior_lines: tuple[str, ...] = ()


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
    if region_type == "city":
        return _generate_city_map(rng, route_directions)
    if region_type == "village":
        return _generate_settlement_map(rng, route_directions, dense=False)
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


def _generate_city_map(rng: random.Random, route_directions: set[str]) -> GeneratedLocalMap:
    variant = rng.randrange(3)
    if variant == 0:
        canvas = _blank_canvas(" ")
        _paint_city_plaza_plan(canvas, route_directions or {"north", "south", "east", "west"})
        scene_keys = ("local_map_scene_city_open_market",)
        exterior_lines = _market_town_exterior_lines()
    elif variant == 1:
        canvas = _blank_canvas(" ")
        _paint_city_avenue_plan(canvas, route_directions or {"north", "south", "east", "west"})
        scene_keys = ("local_map_scene_city_riverport",)
        exterior_lines = _riverport_exterior_lines()
    else:
        canvas = _bordered_canvas(" ")
        _paint_city_citadel_plan(canvas, route_directions or {"north", "south", "east", "west"})
        scene_keys = ("local_map_scene_city_citadel",)
        exterior_lines = _city_exterior_lines()
    return GeneratedLocalMap(
        _stringify(canvas),
        ("local_map_legend_city", "local_map_legend_route_gate"),
        scene_keys,
        exterior_lines,
    )


def _paint_city_plaza_plan(canvas: list[list[str]], directions: set[str]) -> None:
    mid_x = LOCAL_MAP_WIDTH // 2
    mid_y = LOCAL_MAP_HEIGHT // 2
    for x in range(1, LOCAL_MAP_WIDTH - 1):
        canvas[mid_y][x] = "="
    for y in range(1, LOCAL_MAP_HEIGHT - 1):
        canvas[y][mid_x] = "|"
    _apply_route_gates(canvas, directions, road_char="=")
    canvas[mid_y][mid_x] = "@"
    _paint_text(canvas, mid_x - 6, mid_y - 1, "Plaza")
    _paint_text(canvas, 3, 2, "[Homes]")
    _paint_text(canvas, 3, 3, "row houses")
    _paint_text(canvas, 22, 2, "[Market]")
    _paint_text(canvas, 22, 3, "stalls")
    _paint_text(canvas, 3, 5, "[Guild]")
    _paint_text(canvas, 22, 5, "[Notice]")
    _paint_text(canvas, 3, 9, "[Inn]")
    _paint_text(canvas, 3, 10, "stables")
    _paint_text(canvas, 22, 9, "[Shrine]")
    _paint_text(canvas, 22, 10, "garden")
    _paint_text(canvas, 3, 12, "[Craft]")
    _paint_text(canvas, 22, 12, "[Homes]")
    _paint_text(canvas, 22, 13, "lanes")


def _paint_city_avenue_plan(canvas: list[list[str]], directions: set[str]) -> None:
    avenue_y = 8
    side_street_x = 12
    for x in range(1, LOCAL_MAP_WIDTH - 1):
        canvas[avenue_y][x] = "="
    for y in range(1, LOCAL_MAP_HEIGHT - 1):
        canvas[y][side_street_x] = "|"
    _paint_city_gate_stubs(canvas, directions, avenue_y=avenue_y, street_x=side_street_x)
    canvas[avenue_y][24] = "@"
    _paint_text(canvas, 3, 2, "[Gate]")
    _paint_text(canvas, 3, 3, "north")
    _paint_text(canvas, 17, 2, "[Temple]")
    _paint_text(canvas, 27, 2, "garden")
    _paint_text(canvas, 3, 5, "[Homes]")
    _paint_text(canvas, 17, 5, "arcade")
    _paint_text(canvas, 25, 5, "[Market]")
    _paint_text(canvas, 16, 7, "Grand Avenue")
    _paint_text(canvas, 3, 10, "[Inn]")
    _paint_text(canvas, 17, 10, "[Guild]")
    _paint_text(canvas, 27, 10, "[Docks]")
    _paint_text(canvas, 3, 13, "lanes")
    _paint_text(canvas, 17, 13, "[Craft]")
    _paint_text(canvas, 27, 13, "warehouse")


def _paint_city_citadel_plan(canvas: list[list[str]], directions: set[str]) -> None:
    for x in range(7, 30):
        canvas[4][x] = "="
        canvas[10][x] = "="
    for y in range(4, 11):
        canvas[y][7] = "|"
        canvas[y][29] = "|"
    _paint_city_gate_stubs(canvas, directions, avenue_y=10, street_x=18)
    canvas[10][18] = "@"
    _paint_text(canvas, 13, 6, "Keep")
    _paint_text(canvas, 13, 7, "court")
    _paint_text(canvas, 2, 2, "Homes")
    _paint_text(canvas, 24, 2, "Shrine")
    _paint_text(canvas, 1, 6, "Market")
    _paint_text(canvas, 23, 6, "Guild")
    _paint_text(canvas, 2, 12, "Inn")
    _paint_text(canvas, 13, 12, "Craft")
    _paint_text(canvas, 25, 12, "Homes")


def _paint_city_gate_stubs(canvas: list[list[str]], directions: set[str], *, avenue_y: int, street_x: int) -> None:
    if "north" in directions:
        canvas[0][street_x] = "+"
        for y in range(1, min(avenue_y + 1, LOCAL_MAP_HEIGHT - 1)):
            canvas[y][street_x] = "|"
    if "south" in directions:
        canvas[LOCAL_MAP_HEIGHT - 1][street_x] = "+"
        for y in range(max(1, avenue_y), LOCAL_MAP_HEIGHT - 1):
            canvas[y][street_x] = "|"
    if "west" in directions:
        canvas[avenue_y][0] = "+"
        for x in range(1, min(street_x + 1, LOCAL_MAP_WIDTH - 1)):
            canvas[avenue_y][x] = "="
    if "east" in directions:
        canvas[avenue_y][LOCAL_MAP_WIDTH - 1] = "+"
        for x in range(max(1, street_x), LOCAL_MAP_WIDTH - 1):
            canvas[avenue_y][x] = "="


def _paint_text(canvas: list[list[str]], x: int, y: int, text: str) -> None:
    if not (0 <= y < LOCAL_MAP_HEIGHT):
        return
    for offset, char in enumerate(text):
        px = x + offset
        if 0 <= px < LOCAL_MAP_WIDTH - 1 and canvas[y][px] == " ":
            canvas[y][px] = char


def _generate_settlement_map(rng: random.Random, route_directions: set[str], *, dense: bool) -> GeneratedLocalMap:
    canvas = _bordered_canvas(" ") if dense else _blank_canvas(" ")
    mid_x = LOCAL_MAP_WIDTH // 2
    mid_y = LOCAL_MAP_HEIGHT // 2
    _paint_settlement_roads(canvas, route_directions or {"north", "south", "east", "west"}, dense=dense)
    canvas[mid_y - 1][mid_x - 1] = "o"
    canvas[mid_y][mid_x] = "@"
    _paint_settlement_scenery(canvas, rng, dense=dense)

    slots = _settlement_building_slots(dense)
    rng.shuffle(slots)
    for x, y, w, h, fill in slots[: 14 if dense else 8]:
        _place_building(canvas, x, y, w, h, fill, rng)

    for _ in range(6 if dense else 12):
        x = rng.randint(2, LOCAL_MAP_WIDTH - 3)
        y = rng.randint(2, LOCAL_MAP_HEIGHT - 3)
        if canvas[y][x] == " ":
            canvas[y][x] = "." if dense else "T"
    return GeneratedLocalMap(
        _stringify(canvas),
        ("local_map_legend_settlement", "local_map_legend_route_gate"),
        ("local_map_scene_village",),
        _village_exterior_lines(),
    )


def _paint_settlement_roads(canvas: list[list[str]], directions: set[str], *, dense: bool) -> None:
    mid_x = LOCAL_MAP_WIDTH // 2
    mid_y = LOCAL_MAP_HEIGHT // 2
    horizontal = "=" if dense else "-"
    vertical = "|" if dense else ":"
    for x in range(1, LOCAL_MAP_WIDTH - 1):
        canvas[mid_y][x] = horizontal
    for y in range(1, LOCAL_MAP_HEIGHT - 1):
        canvas[y][mid_x] = vertical
    _apply_route_gates(canvas, directions, road_char=horizontal)


def _paint_settlement_scenery(canvas: list[list[str]], rng: random.Random, *, dense: bool) -> None:
    mid_x = LOCAL_MAP_WIDTH // 2
    mid_y = LOCAL_MAP_HEIGHT // 2
    if dense:
        _paint_rect(canvas, mid_x + 3, mid_y - 2, 4, 1, "$")
        _paint_rect(canvas, mid_x - 6, mid_y + 2, 3, 2, "S")
        canvas[mid_y - 1][mid_x + 5] = "B"
        for x, y in ((5, 5), (31, 5), (8, 12), (28, 12)):
            canvas[y][x] = "T"
        return

    for x, y, w, h in ((2, 2, 6, 2), (24, 3, 7, 2), (3, 11, 8, 2), (25, 10, 7, 2)):
        _paint_rect(canvas, x, y, w, h, '"')
    stream_y = 5 if rng.randrange(2) == 0 else 12
    for x in range(1, LOCAL_MAP_WIDTH - 1):
        if canvas[stream_y][x] == " ":
            canvas[stream_y][x] = "~"
    canvas[stream_y][mid_x] = "="
    canvas[mid_y - 1][mid_x + 3] = "B"


def _paint_rect(canvas: list[list[str]], x: int, y: int, w: int, h: int, fill: str) -> None:
    for yy in range(y, min(y + h, LOCAL_MAP_HEIGHT)):
        for xx in range(x, min(x + w, LOCAL_MAP_WIDTH)):
            if canvas[yy][xx] == " ":
                canvas[yy][xx] = fill


def _settlement_building_slots(dense: bool) -> list[tuple[int, int, int, int, str]]:
    if dense:
        return [
            (3, 2, 5, 2, "H"), (10, 2, 5, 2, "H"), (22, 2, 5, 2, "H"), (29, 2, 5, 2, "H"),
            (4, 5, 4, 2, "$"), (11, 5, 4, 2, "H"), (23, 5, 4, 2, "$"), (30, 5, 4, 2, "H"),
            (3, 9, 5, 2, "I"), (10, 10, 5, 2, "H"), (22, 9, 5, 2, "H"), (29, 10, 5, 2, "I"),
            (5, 12, 4, 2, "H"), (24, 12, 4, 2, "H"), (31, 12, 3, 2, "H"),
        ]
    return [
        (4, 3, 4, 2, "h"), (11, 2, 4, 2, "h"), (24, 2, 4, 2, "h"), (30, 4, 4, 2, "h"),
        (5, 10, 4, 2, "b"), (12, 11, 4, 2, "h"), (23, 10, 4, 2, "b"), (30, 11, 4, 2, "h"),
        (2, 6, 3, 2, "h"), (31, 7, 3, 2, "h"),
    ]


def _place_building(canvas: list[list[str]], x: int, y: int, w: int, h: int, fill: str, rng: random.Random) -> None:
    if not _building_space_is_clear(canvas, x, y, w, h):
        return
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            canvas[yy][xx] = fill
    door_candidates = [(x + rng.randrange(w), y + h - 1), (x + rng.randrange(w), y)]
    door_x, door_y = door_candidates[rng.randrange(len(door_candidates))]
    canvas[door_y][door_x] = "+"


def _building_space_is_clear(canvas: list[list[str]], x: int, y: int, w: int, h: int) -> bool:
    for yy in range(max(0, y - 1), min(LOCAL_MAP_HEIGHT, y + h + 1)):
        for xx in range(max(0, x - 1), min(LOCAL_MAP_WIDTH, x + w + 1)):
            if canvas[yy][xx] not in {" ", ".", '"'}:
                return False
    return True


def _generate_dungeon_map(rng: random.Random, route_directions: set[str]) -> GeneratedLocalMap:
    canvas = _blank_canvas(" ")
    rooms: list[tuple[int, int, int, int]] = []
    for _ in range(12):
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
    _place_dungeon_features(canvas, rooms, rng)
    _apply_route_gates(canvas, route_directions or {"south"}, road_char=".")
    _outline_dungeon_walls(canvas)
    return GeneratedLocalMap(
        _stringify(canvas),
        ("local_map_legend_dungeon", "local_map_legend_route_gate"),
        ("local_map_scene_dungeon",),
        _dungeon_exterior_lines(),
    )


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
    return GeneratedLocalMap(
        _stringify(canvas),
        ("local_map_legend_wild", "local_map_legend_route_gate"),
        ("local_map_scene_wild",),
        _wild_exterior_lines(tree_char),
    )


def _art_lines(*lines: str) -> tuple[str, ...]:
    return tuple(line[:LOCAL_MAP_WIDTH].ljust(LOCAL_MAP_WIDTH) for line in lines)


def _city_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        "        /\\        /\\        /\\      ",
        "   ____/  \\______/  \\______/  \\____",
        "  | gate towers |  banners | watch |",
        "  | [] [] [] [] |  market smoke    |",
        "==|______/==\\______________________|",
    )


def _market_town_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        "        open square and cloth awnings ",
        "   __/\\__     __/\\__      carts     ",
        "  / market\\___/ inn \\___ stalls     ",
        " road ======= @ ======= road        ",
        "        bells, smoke, crowded lanes  ",
    )


def _riverport_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        "        temple roofs over the quay    ",
        "   ___/\\___    arcade    cranes      ",
        "  | docks |==== avenue ==== market   ",
        " ~~ boats ~~ @ ~~ warehouse lights   ",
        "        river road and busy bridges   ",
    )


def _village_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        ' """" fields        ~~ stream ~~     ',
        "       /\\       /\\          T T      ",
        "  ____/__\\_____/__\\____   hhh hhh   ",
        "     barn and low roofs      [B]     ",
        "  road --------- @ --------- road    ",
    )


def _dungeon_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        "        broken arch and wet stone    ",
        "      ___/^^^^^^^^^^^^^^\\___        ",
        "     /  r  fallen blocks   \\        ",
        " ___/____      @      ____>_\\___    ",
        "       mist ~~~   altar shadow       ",
    )


def _wild_exterior_lines(tree_char: str) -> tuple[str, ...]:
    return _art_lines(
        f"      {tree_char} {tree_char} ridge line and brush     ",
        "   ___ path bends through cover ___   ",
        "      \\__  @  __/      stones       ",
        "          \\__/     wind and tracks   ",
        "        distant road fades away       ",
    )


def _outline_dungeon_walls(canvas: list[list[str]]) -> None:
    floor_chars = {".", "@", ">", "!", "?", "+", "A", "~", "r"}
    wall_points: set[tuple[int, int]] = set()
    for y, row in enumerate(canvas):
        for x, char in enumerate(row):
            if char not in floor_chars:
                continue
            for yy in range(max(0, y - 1), min(LOCAL_MAP_HEIGHT, y + 2)):
                for xx in range(max(0, x - 1), min(LOCAL_MAP_WIDTH, x + 2)):
                    if canvas[yy][xx] == " ":
                        wall_points.add((xx, yy))
    for x, y in wall_points:
        canvas[y][x] = "#"


def _place_dungeon_features(
    canvas: list[list[str]],
    rooms: list[tuple[int, int, int, int]],
    rng: random.Random,
) -> None:
    feature_marks = ("A", "~", "r")
    for index, marker in enumerate(feature_marks):
        if not rooms:
            return
        room = rooms[(index + rng.randrange(len(rooms))) % len(rooms)]
        x, y = _random_floor_in_room(rng, room)
        if canvas[y][x] == ".":
            canvas[y][x] = marker


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

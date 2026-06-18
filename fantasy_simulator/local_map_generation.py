"""Deterministic local map generation for location detail views."""

from __future__ import annotations

import hashlib
import heapq
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


@dataclass(frozen=True)
class TerrainBias:
    """Micro-terrain weight hints for one local place."""

    water: int = 0
    forest: int = 0
    field: int = 0
    hill: int = 0
    roughness: int = 0


@dataclass(frozen=True)
class FeatureRule:
    """A feature placement rule, not a fixed stamp location."""

    tag: str
    weight: int = 1
    required: bool = False
    near: str = ""
    avoid: str = ""


@dataclass(frozen=True)
class PlaceVisualProfile:
    """Visual constraints for a local map archetype."""

    archetype: str
    terrain_bias: TerrainBias
    feature_rules: tuple[FeatureRule, ...]
    road_style: str
    density: int
    local_scene_keys: tuple[str, ...]
    legend_key: str


@dataclass(frozen=True)
class LocalMapSpec:
    """Fully resolved local map generation inputs."""

    profile: PlaceVisualProfile
    region_type: str
    biome: str
    elevation: int
    moisture: int
    temperature: int
    topography_seed: int
    settlement_seed: int


def generate_local_map(cell: Any, connected_cells: Iterable[Any] = ()) -> GeneratedLocalMap:
    """Generate a stable local map for one location.

    The generator keeps land/layout seeds separate from state overlays, so
    danger or rumor changes can scar the map without moving rivers, roads, or
    buildings between visits.
    """
    region_type = str(getattr(cell, "region_type", "plains") or "plains")
    spec = _local_map_spec(cell)
    topography_rng = random.Random(spec.topography_seed)
    settlement_rng = random.Random(spec.settlement_seed)
    state_rng = random.Random(_state_overlay_seed(cell))
    route_directions = _route_directions(cell, connected_cells)
    if region_type == "dungeon":
        return _generate_dungeon_map(settlement_rng, route_directions, cell, state_rng)
    return _generate_profile_map(spec, topography_rng, settlement_rng, route_directions, cell, state_rng)


def _hash_seed(*parts: object) -> int:
    seed_text = "|".join(str(part) for part in parts)
    return int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)


def _topography_seed(cell: Any) -> int:
    return _hash_seed(
        "topography",
        getattr(cell, "location_id", ""),
        getattr(cell, "x", ""),
        getattr(cell, "y", ""),
        getattr(cell, "terrain_biome", ""),
        getattr(cell, "terrain_elevation", ""),
        getattr(cell, "terrain_moisture", ""),
        getattr(cell, "terrain_temperature", ""),
    )


def _settlement_seed(cell: Any) -> int:
    return _hash_seed(
        "settlement-layout",
        getattr(cell, "location_id", ""),
        getattr(cell, "region_type", ""),
        getattr(cell, "x", ""),
        getattr(cell, "y", ""),
    )


def _state_overlay_seed(cell: Any) -> int:
    return _hash_seed(
        "state-overlay",
        getattr(cell, "location_id", ""),
        _value_band(getattr(cell, "danger", 50)),
        getattr(cell, "danger_band", ""),
        _value_band(getattr(cell, "rumor_heat", 0)),
        getattr(cell, "rumor_heat_band", ""),
        _value_band(getattr(cell, "prosperity", 50)),
        _value_band(getattr(cell, "mood", 50)),
        getattr(cell, "controlling_faction_id", ""),
    )


def _value_band(value: Any) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = 50
    if number < 34:
        return "low"
    if number >= 67:
        return "high"
    return "medium"


def _cell_band(cell: Any, band_name: str, value_name: str, default: Any) -> str:
    band = str(getattr(cell, band_name, "") or "")
    if band in {"low", "medium", "high"}:
        return band
    return _value_band(getattr(cell, value_name, default))


def _local_map_spec(cell: Any) -> LocalMapSpec:
    region_type = str(getattr(cell, "region_type", "plains") or "plains")
    biome = str(getattr(cell, "terrain_biome", "plains") or "plains")
    elevation = _clamp_byte(getattr(cell, "terrain_elevation", 128))
    moisture = _clamp_byte(getattr(cell, "terrain_moisture", 128))
    temperature = _clamp_byte(getattr(cell, "terrain_temperature", 128))
    return LocalMapSpec(
        profile=_profile_for_cell(cell, region_type, biome, elevation, moisture),
        region_type=region_type,
        biome=biome,
        elevation=elevation,
        moisture=moisture,
        temperature=temperature,
        topography_seed=_topography_seed(cell),
        settlement_seed=_settlement_seed(cell),
    )


def _clamp_byte(value: Any) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 128
    return max(0, min(255, number))


def _profile_for_cell(
    cell: Any,
    region_type: str,
    biome: str,
    elevation: int,
    moisture: int,
) -> PlaceVisualProfile:
    if region_type == "city":
        return _city_profile(cell, biome, elevation, moisture)
    if region_type == "village":
        return _village_profile(biome, elevation, moisture)
    if region_type == "forest":
        return PlaceVisualProfile(
            archetype="forest_paths",
            terrain_bias=TerrainBias(forest=60, roughness=20),
            feature_rules=(
                FeatureRule("trees", weight=6),
                FeatureRule("standing_stones", weight=1, near="high_ground"),
            ),
            road_style="trail",
            density=15,
            local_scene_keys=("local_map_scene_wild",),
            legend_key="local_map_legend_wild",
        )
    if region_type == "mountain":
        return PlaceVisualProfile(
            archetype="mountain_pass",
            terrain_bias=TerrainBias(hill=60, roughness=45, forest=10),
            feature_rules=(
                FeatureRule("rocks", weight=5),
                FeatureRule("lookout", weight=1, near="high_ground"),
            ),
            road_style="trail",
            density=10,
            local_scene_keys=("local_map_scene_wild",),
            legend_key="local_map_legend_wild",
        )
    return PlaceVisualProfile(
        archetype="open_wilds",
        terrain_bias=TerrainBias(field=10, forest=10, roughness=10),
        feature_rules=(FeatureRule("brush", weight=4),),
        road_style="trail",
        density=8,
        local_scene_keys=("local_map_scene_wild",),
        legend_key="local_map_legend_wild",
    )


def _city_profile(cell: Any, biome: str, elevation: int, moisture: int) -> PlaceVisualProfile:
    seed_variant = _settlement_seed(cell) % 3
    if biome == "river" or moisture >= 165 or seed_variant == 1:
        return PlaceVisualProfile(
            archetype="riverport_city",
            terrain_bias=TerrainBias(water=45, roughness=8),
            feature_rules=(
                FeatureRule("guild", required=True, near="gate"),
                FeatureRule("shrine", required=True, near="center"),
                FeatureRule("market", required=True, near="road"),
                FeatureRule("homes", weight=4, near="road"),
                FeatureRule("docks", required=True, near="water"),
                FeatureRule("warehouse", weight=2, near="water"),
                FeatureRule("craft", weight=2, near="road"),
            ),
            road_style="riverport",
            density=72,
            local_scene_keys=("local_map_scene_city_riverport",),
            legend_key="local_map_legend_city",
        )
    if elevation >= 160 or seed_variant == 2:
        return PlaceVisualProfile(
            archetype="citadel_city",
            terrain_bias=TerrainBias(hill=30, roughness=18),
            feature_rules=(
                FeatureRule("walls", required=True),
                FeatureRule("keep", required=True, near="high_ground"),
                FeatureRule("gate", required=True, near="gate"),
                FeatureRule("market", weight=2, near="road"),
                FeatureRule("shrine", weight=1, near="center"),
                FeatureRule("homes", weight=4, near="road"),
                FeatureRule("inn", weight=1, near="road"),
                FeatureRule("craft", weight=2, near="road"),
            ),
            road_style="controlled_roads",
            density=76,
            local_scene_keys=("local_map_scene_city_citadel",),
            legend_key="local_map_legend_city",
        )
    return PlaceVisualProfile(
        archetype="open_market_city",
        terrain_bias=TerrainBias(forest=4, roughness=6),
        feature_rules=(
            FeatureRule("market", required=True, near="center"),
            FeatureRule("homes", weight=5, near="road"),
            FeatureRule("guild", weight=1, near="road"),
            FeatureRule("notice", weight=1, near="center"),
            FeatureRule("inn", weight=2, near="road"),
            FeatureRule("shrine", weight=1, near="center"),
            FeatureRule("craft", weight=2, near="road"),
        ),
        road_style="market_roads",
        density=64,
        local_scene_keys=("local_map_scene_city_open_market",),
        legend_key="local_map_legend_city",
    )


def _village_profile(biome: str, elevation: int, moisture: int) -> PlaceVisualProfile:
    if biome == "river" or moisture >= 160:
        return PlaceVisualProfile(
            archetype="riverside_village",
            terrain_bias=TerrainBias(water=55, field=30, forest=8, roughness=8),
            feature_rules=(
                FeatureRule("bridge", required=True, near="water"),
                FeatureRule("watermill", required=True, near="water"),
                FeatureRule("fields", weight=5),
                FeatureRule("homes", weight=4, near="road"),
                FeatureRule("barn", weight=2, near="field"),
                FeatureRule("notice", weight=1, near="center"),
            ),
            road_style="ford_or_bridge",
            density=38,
            local_scene_keys=("local_map_scene_village_riverside",),
            legend_key="local_map_legend_settlement",
        )
    if biome == "forest":
        return PlaceVisualProfile(
            archetype="woodland_village",
            terrain_bias=TerrainBias(forest=45, field=12, roughness=18),
            feature_rules=(
                FeatureRule("trees", weight=4),
                FeatureRule("homes", weight=4, near="road"),
                FeatureRule("barn", weight=1, near="field"),
                FeatureRule("shrine", weight=1, near="center"),
                FeatureRule("notice", weight=1, near="center"),
            ),
            road_style="trail",
            density=32,
            local_scene_keys=("local_map_scene_village_woodland",),
            legend_key="local_map_legend_settlement",
        )
    if elevation >= 165:
        return PlaceVisualProfile(
            archetype="highland_hamlet",
            terrain_bias=TerrainBias(hill=35, field=12, forest=12, roughness=35),
            feature_rules=(
                FeatureRule("rocks", weight=3),
                FeatureRule("homes", weight=3, near="road"),
                FeatureRule("barn", weight=1, near="road"),
                FeatureRule("shrine", weight=1, near="high_ground"),
            ),
            road_style="trail",
            density=28,
            local_scene_keys=("local_map_scene_village_highland",),
            legend_key="local_map_legend_settlement",
        )
    return PlaceVisualProfile(
        archetype="field_village",
        terrain_bias=TerrainBias(field=45, forest=10, water=10, roughness=8),
        feature_rules=(
            FeatureRule("fields", weight=5),
            FeatureRule("homes", weight=4, near="road"),
            FeatureRule("barn", weight=2, near="field"),
            FeatureRule("market", weight=1, near="center"),
            FeatureRule("notice", weight=1, near="center"),
        ),
        road_style="country_lane",
        density=34,
        local_scene_keys=("local_map_scene_village_field",),
        legend_key="local_map_legend_settlement",
    )


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


def _generate_profile_map(
    spec: LocalMapSpec,
    topography_rng: random.Random,
    settlement_rng: random.Random,
    route_directions: set[str],
    cell: Any,
    state_rng: random.Random,
) -> GeneratedLocalMap:
    canvas = _generate_micro_terrain(spec, topography_rng)
    if spec.profile.archetype == "citadel_city":
        _paint_rect_border(canvas, 1, 1, LOCAL_MAP_WIDTH - 2, LOCAL_MAP_HEIGHT - 2, "#")
    center = _choose_center(canvas, spec, settlement_rng)
    directions = route_directions or _default_route_directions(spec.profile)
    _paint_profile_roads(canvas, directions, center, spec.profile, settlement_rng)
    canvas[center[1]][center[0]] = "@"
    _place_profile_features(canvas, spec.profile, center, settlement_rng)
    if spec.profile.archetype == "citadel_city":
        _reinforce_city_gates(canvas)
    return _finalize_local_map(
        canvas,
        (spec.profile.legend_key, "local_map_legend_route_gate"),
        spec.profile.local_scene_keys,
        _profile_exterior_lines(spec.profile.archetype),
        cell,
        state_rng,
    )


def _generate_micro_terrain(spec: LocalMapSpec, rng: random.Random) -> list[list[str]]:
    height = _noise_field(
        LOCAL_MAP_WIDTH,
        LOCAL_MAP_HEIGHT,
        spec.topography_seed,
        spec.elevation + spec.profile.terrain_bias.hill,
        24 + spec.profile.terrain_bias.roughness,
    )
    moisture = _noise_field(
        LOCAL_MAP_WIDTH,
        LOCAL_MAP_HEIGHT,
        spec.topography_seed ^ 0xA53A,
        spec.moisture + spec.profile.terrain_bias.water,
        34,
    )
    forest = _noise_field(
        LOCAL_MAP_WIDTH,
        LOCAL_MAP_HEIGHT,
        spec.topography_seed ^ 0x7F11,
        spec.profile.terrain_bias.forest,
        48,
    )
    canvas = _blank_canvas(".")
    for y in range(LOCAL_MAP_HEIGHT):
        for x in range(LOCAL_MAP_WIDTH):
            h = height[y][x]
            m = moisture[y][x]
            f = forest[y][x]
            if m > 246 and h < 176:
                canvas[y][x] = "~"
            elif h > 216:
                canvas[y][x] = "^"
            elif h > 178:
                canvas[y][x] = "n"
            elif spec.biome == "forest" or f > 170:
                canvas[y][x] = "T"
            elif (
                spec.profile.terrain_bias.field
                and m > 112
                and rng.random() < min(0.35, spec.profile.terrain_bias.field / 160)
            ):
                canvas[y][x] = '"'
            elif rng.random() < 0.05:
                canvas[y][x] = ","
            else:
                canvas[y][x] = "."
    if spec.profile.terrain_bias.water >= 35:
        _paint_meandering_water(canvas, rng)
        _thin_excess_water(canvas, rng)
    return canvas


def _noise_field(width: int, height: int, seed: int, base: int, variance: int) -> list[list[int]]:
    base = max(0, min(255, base))
    field: list[list[int]] = []
    for y in range(height):
        row: list[int] = []
        for x in range(width):
            raw = _hash_seed(seed, x // 2, y // 2, x, y) % 255
            row.append(max(0, min(255, base + ((raw - 127) * variance // 127))))
        field.append(row)
    return field


def _paint_meandering_water(canvas: list[list[str]], rng: random.Random) -> None:
    horizontal = rng.randrange(2) == 0
    if horizontal:
        y = rng.randint(3, LOCAL_MAP_HEIGHT - 4)
        for x in range(LOCAL_MAP_WIDTH):
            y = max(1, min(LOCAL_MAP_HEIGHT - 2, y + rng.choice((-1, 0, 0, 1))))
            canvas[y][x] = "~"
            if rng.random() < 0.35 and y + 1 < LOCAL_MAP_HEIGHT:
                canvas[y + 1][x] = "~"
    else:
        x = rng.randint(6, LOCAL_MAP_WIDTH - 7)
        for y in range(LOCAL_MAP_HEIGHT):
            x = max(1, min(LOCAL_MAP_WIDTH - 2, x + rng.choice((-1, 0, 0, 1))))
            canvas[y][x] = "~"
            if rng.random() < 0.35 and x + 1 < LOCAL_MAP_WIDTH:
                canvas[y][x + 1] = "~"


def _thin_excess_water(canvas: list[list[str]], rng: random.Random) -> None:
    water_points = [
        (x, y)
        for y, row in enumerate(canvas)
        for x, char in enumerate(row)
        if char == "~"
    ]
    max_water = LOCAL_MAP_WIDTH * LOCAL_MAP_HEIGHT // 5
    if len(water_points) <= max_water:
        return
    rng.shuffle(water_points)
    for x, y in water_points[max_water:]:
        canvas[y][x] = "." if rng.random() < 0.7 else '"'


def _choose_center(canvas: list[list[str]], spec: LocalMapSpec, rng: random.Random) -> tuple[int, int]:
    base_x = LOCAL_MAP_WIDTH // 2
    base_y = LOCAL_MAP_HEIGHT // 2
    if spec.profile.road_style in {"riverport", "ford_or_bridge"}:
        water_columns = [
            x for x in range(4, LOCAL_MAP_WIDTH - 4)
            if sum(1 for y in range(2, LOCAL_MAP_HEIGHT - 2) if canvas[y][x] == "~") >= 3
        ]
        if water_columns:
            base_x = min(water_columns, key=lambda x: abs(x - LOCAL_MAP_WIDTH // 2))
    for _ in range(16):
        x = max(4, min(LOCAL_MAP_WIDTH - 5, base_x + rng.randint(-3, 3)))
        y = max(3, min(LOCAL_MAP_HEIGHT - 4, base_y + rng.randint(-2, 2)))
        if canvas[y][x] != "^":
            return x, y
    return base_x, base_y


def _default_route_directions(profile: PlaceVisualProfile) -> set[str]:
    if profile.road_style in {"riverport", "market_roads"}:
        return {"west", "east", "north"}
    if profile.road_style == "controlled_roads":
        return {"west", "east", "south"}
    if profile.road_style == "ford_or_bridge":
        return {"west", "east"}
    return {"west", "east"}


def _paint_profile_roads(
    canvas: list[list[str]],
    directions: set[str],
    center: tuple[int, int],
    profile: PlaceVisualProfile,
    rng: random.Random,
) -> None:
    road_char = _road_char(profile)
    for direction in _ordered_directions(directions):
        endpoint = _route_endpoint(direction, center, rng)
        _carve_weighted_path(canvas, endpoint, center, road_char)
        canvas[endpoint[1]][endpoint[0]] = "+"
    if profile.road_style in {"market_roads", "riverport"}:
        _paint_cross_streets(canvas, center, road_char)


def _ordered_directions(directions: set[str]) -> tuple[str, ...]:
    order = ("north", "east", "south", "west")
    return tuple(direction for direction in order if direction in directions)


def _road_char(profile: PlaceVisualProfile) -> str:
    if profile.archetype.endswith("_city"):
        return "="
    if profile.road_style == "trail":
        return "."
    return "-"


def _route_endpoint(direction: str, center: tuple[int, int], rng: random.Random) -> tuple[int, int]:
    cx, cy = center
    if direction == "north":
        return max(1, min(LOCAL_MAP_WIDTH - 2, cx + rng.randint(-5, 5))), 0
    if direction == "south":
        return max(1, min(LOCAL_MAP_WIDTH - 2, cx + rng.randint(-5, 5))), LOCAL_MAP_HEIGHT - 1
    if direction == "west":
        return 0, max(1, min(LOCAL_MAP_HEIGHT - 2, cy + rng.randint(-3, 3)))
    return LOCAL_MAP_WIDTH - 1, max(1, min(LOCAL_MAP_HEIGHT - 2, cy + rng.randint(-3, 3)))


def _carve_weighted_path(
    canvas: list[list[str]],
    start: tuple[int, int],
    end: tuple[int, int],
    road_char: str,
) -> None:
    frontier: list[tuple[int, tuple[int, int]]] = [(0, start)]
    came_from: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    cost_so_far: dict[tuple[int, int], int] = {start: 0}
    while frontier:
        _priority, current = heapq.heappop(frontier)
        if current == end:
            break
        for neighbor in _neighbors(current):
            new_cost = cost_so_far[current] + _terrain_cost(canvas[neighbor[1]][neighbor[0]])
            if neighbor not in cost_so_far or new_cost < cost_so_far[neighbor]:
                cost_so_far[neighbor] = new_cost
                priority = new_cost + _manhattan(neighbor, end)
                heapq.heappush(frontier, (priority, neighbor))
                came_from[neighbor] = current
    path_point: tuple[int, int] | None = end
    if path_point not in came_from:
        return
    while path_point is not None:
        x, y = path_point
        if canvas[y][x] == "~":
            canvas[y][x] = "="
        elif canvas[y][x] not in {"@", "+", "#"}:
            canvas[y][x] = road_char
        path_point = came_from[path_point]


def _neighbors(point: tuple[int, int]) -> list[tuple[int, int]]:
    x, y = point
    result: list[tuple[int, int]] = []
    for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
        if 0 <= nx < LOCAL_MAP_WIDTH and 0 <= ny < LOCAL_MAP_HEIGHT:
            result.append((nx, ny))
    return result


def _terrain_cost(char: str) -> int:
    return {
        ".": 1,
        ",": 1,
        '"': 2,
        "-": 1,
        "=": 1,
        ":": 1,
        "~": 12,
        "T": 8,
        "n": 6,
        "^": 18,
        "#": 30,
    }.get(char, 4)


def _manhattan(first: tuple[int, int], second: tuple[int, int]) -> int:
    return abs(first[0] - second[0]) + abs(first[1] - second[1])


def _paint_cross_streets(canvas: list[list[str]], center: tuple[int, int], road_char: str) -> None:
    cx, cy = center
    for x in range(max(1, cx - 10), min(LOCAL_MAP_WIDTH - 1, cx + 11)):
        if canvas[cy][x] not in {"@", "+", "#"}:
            canvas[cy][x] = road_char
    for y in range(max(1, cy - 5), min(LOCAL_MAP_HEIGHT - 1, cy + 6)):
        if canvas[y][cx] not in {"@", "+", "#"}:
            canvas[y][cx] = "|"


def _place_profile_features(
    canvas: list[list[str]],
    profile: PlaceVisualProfile,
    center: tuple[int, int],
    rng: random.Random,
) -> None:
    rules = list(profile.feature_rules)
    for rule in rules:
        count = _feature_count(rule, profile)
        for _ in range(count):
            _place_feature(canvas, profile, rule, center, rng)


def _feature_count(rule: FeatureRule, profile: PlaceVisualProfile) -> int:
    if rule.required:
        return 1
    if rule.tag == "homes":
        return max(2, profile.density // 18 + rule.weight // 2)
    if rule.tag in {"fields", "trees", "rocks", "brush"}:
        return max(2, rule.weight)
    return max(1, rule.weight // 2)


def _place_feature(
    canvas: list[list[str]],
    profile: PlaceVisualProfile,
    rule: FeatureRule,
    center: tuple[int, int],
    rng: random.Random,
) -> None:
    candidates = _feature_candidates(canvas, center, rule.near, rule.avoid)
    if not candidates:
        return
    rng.shuffle(candidates)
    for x, y in candidates[:24]:
        if _paint_feature(canvas, profile, rule.tag, x, y, rng):
            return


def _feature_candidates(
    canvas: list[list[str]],
    center: tuple[int, int],
    near: str,
    avoid: str,
) -> list[tuple[int, int]]:
    candidates = _base_feature_candidates(canvas)
    candidates = _apply_near_filter(canvas, center, candidates, near)
    return _apply_avoid_filter(canvas, candidates, avoid)


def _base_feature_candidates(canvas: list[list[str]]) -> list[tuple[int, int]]:
    return [
        (x, y)
        for y in range(1, LOCAL_MAP_HEIGHT - 2)
        for x in range(1, LOCAL_MAP_WIDTH - 3)
        if canvas[y][x] not in {"#", "@", "+"}
    ]


def _apply_near_filter(
    canvas: list[list[str]],
    center: tuple[int, int],
    candidates: list[tuple[int, int]],
    near: str,
) -> list[tuple[int, int]]:
    if near in {"", "any"}:
        return candidates
    if near == "center":
        return sorted(candidates, key=lambda point: _manhattan(point, center))
    if near == "gate":
        return sorted(candidates, key=_distance_to_edge)
    near_chars = {
        "road": {"=", "-", ".", "|"},
        "water": {"~", "="},
        "field": {'"'},
        "high_ground": {"^", "n"},
    }.get(near)
    if near_chars is None:
        return candidates
    return [point for point in candidates if _near_any(canvas, point, near_chars)]


def _apply_avoid_filter(
    canvas: list[list[str]],
    candidates: list[tuple[int, int]],
    avoid: str,
) -> list[tuple[int, int]]:
    avoid_chars = {
        "water": {"~"},
    }.get(avoid)
    if avoid_chars is None:
        return candidates
    return [point for point in candidates if not _near_any(canvas, point, avoid_chars)]


def _near_any(canvas: list[list[str]], point: tuple[int, int], chars: set[str]) -> bool:
    x, y = point
    for yy in range(max(0, y - 2), min(LOCAL_MAP_HEIGHT, y + 3)):
        for xx in range(max(0, x - 2), min(LOCAL_MAP_WIDTH, x + 3)):
            if canvas[yy][xx] in chars:
                return True
    return False


def _distance_to_edge(point: tuple[int, int]) -> int:
    x, y = point
    return min(x, y, LOCAL_MAP_WIDTH - 1 - x, LOCAL_MAP_HEIGHT - 1 - y)


def _paint_feature(
    canvas: list[list[str]],
    profile: PlaceVisualProfile,
    tag: str,
    x: int,
    y: int,
    rng: random.Random,
) -> bool:
    if tag == "walls":
        _paint_rect_border(canvas, 1, 1, LOCAL_MAP_WIDTH - 2, LOCAL_MAP_HEIGHT - 2, "#")
        return True
    if tag == "bridge":
        return _paint_bridge(canvas, x, y)
    if tag in {"homes", "market", "shrine", "inn", "guild", "craft", "docks", "warehouse", "keep", "gate", "notice"}:
        marker = _feature_marker(tag)
        if profile.archetype.endswith("_city"):
            return _paint_city_block_at(canvas, x, y, marker)
        return _paint_small_feature(canvas, x, y, marker.lower() if marker == "H" else marker)
    if tag == "fields":
        return _paint_patch(canvas, x, y, 5, 2, '"')
    if tag == "barn":
        return _paint_patch(canvas, x, y, 3, 2, "b")
    if tag == "watermill":
        return _paint_small_feature(canvas, x, y, "w")
    if tag in {"trees", "brush"}:
        return _paint_patch(canvas, x, y, rng.randint(2, 4), 1, "T" if tag == "trees" else ",")
    if tag == "rocks":
        return _paint_patch(canvas, x, y, rng.randint(2, 4), 1, "^")
    if tag in {"lookout", "standing_stones"}:
        return _paint_small_feature(canvas, x, y, "o")
    return False


def _feature_marker(tag: str) -> str:
    return {
        "homes": "H",
        "market": "M",
        "shrine": "S",
        "inn": "I",
        "guild": "G",
        "craft": "C",
        "docks": "D",
        "warehouse": "W",
        "keep": "K",
        "gate": "G",
        "notice": "N",
    }.get(tag, "?")


def _paint_city_block_at(canvas: list[list[str]], x: int, y: int, marker: str) -> bool:
    if x + 2 >= LOCAL_MAP_WIDTH or y + 1 >= LOCAL_MAP_HEIGHT:
        return False
    cells = ((x, y), (x + 1, y), (x + 2, y), (x, y + 1), (x + 1, y + 1), (x + 2, y + 1))
    if any(canvas[py][px] in {"#", "@", "+", "/", "\\", marker} for px, py in cells):
        return False
    _paint_text_force(canvas, x, y, f"/{marker}\\")
    _paint_text_force(canvas, x, y + 1, "###")
    return True


def _paint_small_feature(canvas: list[list[str]], x: int, y: int, marker: str) -> bool:
    if canvas[y][x] in {"#", "@", "+", "/", "\\"}:
        return False
    canvas[y][x] = marker
    return True


def _paint_patch(canvas: list[list[str]], x: int, y: int, w: int, h: int, fill: str) -> bool:
    if x + w >= LOCAL_MAP_WIDTH or y + h >= LOCAL_MAP_HEIGHT:
        return False
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            if canvas[yy][xx] in {"#", "@", "+", "/", "\\"}:
                return False
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            canvas[yy][xx] = fill
    return True


def _paint_bridge(canvas: list[list[str]], x: int, y: int) -> bool:
    for yy in range(max(1, y - 1), min(LOCAL_MAP_HEIGHT - 1, y + 2)):
        for xx in range(max(1, x - 2), min(LOCAL_MAP_WIDTH - 1, x + 3)):
            if canvas[yy][xx] == "~":
                canvas[yy][xx] = "="
                return True
    return False


def _paint_rect_border(canvas: list[list[str]], x: int, y: int, w: int, h: int, fill: str) -> None:
    for xx in range(x, min(x + w, LOCAL_MAP_WIDTH)):
        canvas[y][xx] = fill
        canvas[min(y + h - 1, LOCAL_MAP_HEIGHT - 1)][xx] = fill
    for yy in range(y, min(y + h, LOCAL_MAP_HEIGHT)):
        canvas[yy][x] = fill
        canvas[yy][min(x + w - 1, LOCAL_MAP_WIDTH - 1)] = fill


def _paint_text_force(canvas: list[list[str]], x: int, y: int, text: str) -> None:
    if not (0 <= y < LOCAL_MAP_HEIGHT):
        return
    for offset, char in enumerate(text):
        px = x + offset
        if 0 <= px < LOCAL_MAP_WIDTH:
            canvas[y][px] = char


def _reinforce_city_gates(canvas: list[list[str]]) -> None:
    for y, row in enumerate(canvas):
        for x, char in enumerate(row):
            if char == "+":
                for nx, ny in _neighbors((x, y)):
                    if canvas[ny][nx] == "#":
                        canvas[ny][nx] = "="


def _generate_dungeon_map(
    rng: random.Random,
    route_directions: set[str],
    cell: Any,
    state_rng: random.Random,
) -> GeneratedLocalMap:
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
    return _finalize_local_map(
        canvas,
        ("local_map_legend_dungeon", "local_map_legend_route_gate"),
        ("local_map_scene_dungeon",),
        _dungeon_exterior_lines(),
        cell,
        state_rng,
    )


def _finalize_local_map(
    canvas: list[list[str]],
    legend_keys: tuple[str, ...],
    scene_keys: tuple[str, ...],
    exterior_lines: tuple[str, ...],
    cell: Any,
    state_rng: random.Random,
) -> GeneratedLocalMap:
    overlay_markers = _apply_state_overlay(canvas, cell, state_rng)
    if overlay_markers:
        legend_keys = legend_keys + ("local_map_legend_state_overlay",)
    return GeneratedLocalMap(_stringify(canvas), legend_keys, scene_keys, exterior_lines)


def _apply_state_overlay(canvas: list[list[str]], cell: Any, rng: random.Random) -> tuple[str, ...]:
    markers: list[str] = []
    if str(getattr(cell, "controlling_faction_id", "") or ""):
        markers.extend(_place_overlay_markers(canvas, rng, "X", 2))
    if _cell_band(cell, "danger_band", "danger", 50) == "high":
        markers.extend(_place_overlay_markers(canvas, rng, "!", 3))
    if _cell_band(cell, "rumor_heat_band", "rumor_heat", 0) == "high":
        markers.extend(_place_overlay_markers(canvas, rng, "?", 2))
    if (
        _cell_band(cell, "prosperity_band", "prosperity", 50) == "low"
        or _cell_band(cell, "mood_band", "mood", 50) == "low"
    ):
        markers.extend(_place_overlay_markers(canvas, rng, "r", 2))
    return tuple(dict.fromkeys(markers))


def _place_overlay_markers(
    canvas: list[list[str]],
    rng: random.Random,
    marker: str,
    count: int,
) -> list[str]:
    candidates = [
        (x, y)
        for y, row in enumerate(canvas)
        for x, char in enumerate(row)
        if char in {" ", ".", ",", '"', "T", "^", "n", ":", "~"}
    ]
    if not candidates:
        return []
    rng.shuffle(candidates)
    placed = 0
    for x, y in candidates[:count]:
        canvas[y][x] = marker
        placed += 1
    return [marker] if placed else []


def _art_lines(*lines: str) -> tuple[str, ...]:
    return tuple(line[:LOCAL_MAP_WIDTH].ljust(LOCAL_MAP_WIDTH) for line in lines)


def _profile_exterior_lines(archetype: str) -> tuple[str, ...]:
    if archetype == "riverport_city":
        return _riverport_exterior_lines()
    if archetype == "citadel_city":
        return _city_exterior_lines()
    if archetype == "open_market_city":
        return _market_town_exterior_lines()
    if archetype == "riverside_village":
        return _riverside_village_exterior_lines()
    if archetype == "woodland_village":
        return _woodland_village_exterior_lines()
    if archetype == "highland_hamlet":
        return _highland_village_exterior_lines()
    if archetype == "field_village":
        return _village_exterior_lines()
    if archetype == "mountain_pass":
        return _wild_exterior_lines("^")
    if archetype == "forest_paths":
        return _wild_exterior_lines("T")
    return _wild_exterior_lines(",")


def _city_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        "        /\\        /\\        /\\      ",
        "   ____/  \\______/  \\______/  \\____",
        "  | [] [] [] |  /\\  | [] [] []    |",
        "  |__==______|_/  \\_|______==_____|",
        "======@==============[]=[]=========",
    )


def _market_town_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        "        /\\      /\\       /\\         ",
        "   ____/  \\____/  \\_____/  \\____   ",
        "  | [] [] |  o o o  | [] [] |      ",
        "======[]====== @ ======[]==========",
        "      ~~~        |        ~~~       ",
    )


def _riverport_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        "        /\\        /\\       ||       ",
        "   ____/  \\______/  \\______||___   ",
        "  | [] [] |====@====| [] [] || |   ",
        " ~~~_/_~~~~~~_|_~~~~~~_/_~~~~~~~   ",
        "      \\          |          /       ",
    )


def _village_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        ' """" """"        ~~~~~~~~          ',
        "       /\\       /\\          T T      ",
        "  ____/__\\_____/__\\____   hhh hhh   ",
        "      ___       ___           B      ",
        "--------------- @ -----------------",
    )


def _riverside_village_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        ' """"       ~~====~~        """"    ',
        "       /\\        w        /\\        ",
        "  ____/__\\______/ \\______/__\\___   ",
        " ~~~~~~~_/_~~~~~~~@~~~~~~~_/_~~~~  ",
        "----------\\--------------/---------",
    )


def _woodland_village_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        " T T T      /\\      /\\      T T T  ",
        "   T   ____/__\\____/__\\____   T    ",
        "      T   hhh     @     hhh   T    ",
        "  ......./........|........\\....   ",
        " T T        T     S     T       T  ",
    )


def _highland_village_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        "        ^^^       /\\       ^^^     ",
        "   ____/   \\_____/__\\_____/   \\   ",
        "  /  hhh       @       hhh      \\  ",
        " /____n____----|----____n________\\ ",
        "      ^^^      o       ^^^        ",
    )


def _dungeon_exterior_lines() -> tuple[str, ...]:
    return _art_lines(
        "              ___^^^^^^___          ",
        "         ____/  r    r   \\____      ",
        "        /  ##   ____   ##    \\      ",
        " ___/__/____      @      ____\\__\\___",
        "       ~~~        A        ~~~       ",
    )


def _wild_exterior_lines(tree_char: str) -> tuple[str, ...]:
    return _art_lines(
        f"      {tree_char} {tree_char} {tree_char}      ^^^      {tree_char}       ",
        "   ___/ \\___        ___/ \\___       ",
        "      \\__  @  ____/        o       ",
        "          \\__/     o    ^          ",
        "     .........             ....     ",
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

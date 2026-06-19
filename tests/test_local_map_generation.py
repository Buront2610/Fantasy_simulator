"""Tests for procedural local maps used by location detail views."""

from __future__ import annotations

from types import SimpleNamespace

from fantasy_simulator.local_map_generation import generate_local_map


def _cell(
    location_id: str,
    region_type: str,
    *,
    x: int = 0,
    y: int = 0,
    terrain_biome: str = "plains",
    terrain_elevation: int = 128,
    terrain_moisture: int = 128,
):
    return SimpleNamespace(
        location_id=location_id,
        region_type=region_type,
        x=x,
        y=y,
        danger=40,
        terrain_biome=terrain_biome,
        terrain_elevation=terrain_elevation,
        terrain_moisture=terrain_moisture,
        terrain_temperature=128,
        rumor_heat=0,
        prosperity=50,
        mood=50,
        controlling_faction_id="",
    )


def test_local_map_generation_is_deterministic_for_same_location() -> None:
    cell = _cell("loc_same_town", "city", x=2, y=3)

    first = generate_local_map(cell)
    second = generate_local_map(cell)

    assert first.lines == second.lines
    assert first.legend_keys == second.legend_keys


def test_village_maps_vary_by_location_seed() -> None:
    first = generate_local_map(_cell("loc_first_village", "village", x=1, y=1))
    second = generate_local_map(_cell("loc_second_village", "village", x=4, y=3))

    assert first.lines != second.lines


def test_city_map_uses_readable_district_labels() -> None:
    generated = generate_local_map(_cell("loc_capital", "city", x=2, y=2))
    joined = "\n".join(generated.lines)

    assert any(marker in joined for marker in ("/H\\", "/K\\"))
    assert "/M\\" in joined
    assert "/S\\" in joined
    assert all(label not in joined for label in ("[Homes]", "[Market]", "[Shrine]", "Grand Avenue"))
    assert any(key.startswith("local_map_scene_city_") for key in generated.scene_keys)


def test_city_maps_have_multiple_stable_urban_forms() -> None:
    generated_maps = [
        generate_local_map(_cell(f"loc_city_{index}", "city", x=index, y=2))
        for index in range(12)
    ]
    maps = {tuple(generated.lines) for generated in generated_maps}
    scene_keys = {generated.scene_keys[0] for generated in generated_maps}

    assert len(maps) >= 2
    assert "local_map_scene_city_citadel" in scene_keys
    assert scene_keys & {"local_map_scene_city_open_market", "local_map_scene_city_riverport"}


def test_dungeon_map_has_rooms_corridors_and_depth_marker() -> None:
    generated = generate_local_map(_cell("loc_deep_dungeon", "dungeon", x=3, y=2))
    joined = "\n".join(generated.lines)

    assert "@" in joined
    assert ">" in joined
    assert "." in joined
    assert "#" in joined
    assert "local_map_legend_dungeon" in generated.legend_keys
    assert generated.scene_keys == ("local_map_scene_dungeon_vault",)


def test_dungeon_profile_responds_to_terrain_not_fixed_template() -> None:
    flooded = generate_local_map(_cell(
        "loc_flooded_dungeon",
        "dungeon",
        terrain_biome="river",
        terrain_moisture=220,
    ))
    cavern = generate_local_map(_cell(
        "loc_cavern_dungeon",
        "dungeon",
        terrain_elevation=210,
    ))

    assert flooded.scene_keys == ("local_map_scene_dungeon_flooded",)
    assert cavern.scene_keys == ("local_map_scene_dungeon_cavern",)
    assert "~" in "\n".join(flooded.lines)
    assert "#" in "\n".join(cavern.lines)


def test_dungeon_route_direction_adds_gate_to_entrance_path() -> None:
    origin = _cell("loc_gate_dungeon", "dungeon", x=1, y=1)
    east = _cell("loc_east", "forest", x=2, y=1)

    generated = generate_local_map(origin, [east])

    assert any(line.endswith("+") for line in generated.lines)


def test_route_direction_adds_gate_to_local_map() -> None:
    origin = _cell("loc_gate_town", "village", x=1, y=1)
    east = _cell("loc_east", "forest", x=2, y=1)

    generated = generate_local_map(origin, [east])

    assert any(line.endswith("+") for line in generated.lines)


def test_state_changes_overlay_without_rerolling_city_layout() -> None:
    calm = _cell("loc_same_city", "city", x=2, y=2)
    dangerous = _cell("loc_same_city", "city", x=2, y=2)
    dangerous.danger = 90
    dangerous.danger_band = "high"

    calm_lines = _structure_signature(generate_local_map(calm).lines)
    dangerous_map = generate_local_map(dangerous)
    dangerous_lines = _structure_signature(dangerous_map.lines)

    assert calm_lines == dangerous_lines
    assert "local_map_legend_state_overlay" in dangerous_map.legend_keys


def test_village_profile_responds_to_terrain_not_fixed_template() -> None:
    river = generate_local_map(_cell(
        "loc_river_village",
        "village",
        terrain_biome="river",
        terrain_moisture=220,
    ))
    highland = generate_local_map(_cell(
        "loc_highland_village",
        "village",
        terrain_elevation=210,
    ))

    assert river.scene_keys == ("local_map_scene_village_riverside",)
    assert highland.scene_keys == ("local_map_scene_village_highland",)
    assert "~" in "\n".join(river.lines)
    assert "^" in "\n".join(highland.lines) or "n" in "\n".join(highland.lines)


def test_control_state_adds_overlay_without_changing_city_structure() -> None:
    free = _cell("loc_controlled_city", "city", x=2, y=2)
    controlled = _cell("loc_controlled_city", "city", x=2, y=2)
    controlled.controlling_faction_id = "faction_watch"

    free_signature = _structure_signature(generate_local_map(free).lines)
    controlled_map = generate_local_map(controlled)

    assert "X" in "\n".join(controlled_map.lines)
    assert "local_map_legend_state_overlay" in controlled_map.legend_keys
    assert free_signature == _structure_signature(controlled_map.lines)


def test_local_memory_cues_are_drawn_on_the_map() -> None:
    cell = _cell("loc_memory_city", "city", x=2, y=2)
    cell.rumor_heat = 90
    cell.rumor_heat_band = "high"
    cell.has_alias = True
    cell.has_memorial = True
    cell.recent_death_site = True
    cell.recent_world_change_count = 1
    cell.local_feature_tags = ("notice_board", "trace", "blocked_route")

    generated = generate_local_map(cell)
    joined = "\n".join(generated.lines)

    for marker in ("B", "a", "P", "*", "t", "x"):
        assert marker in joined
    assert "local_map_legend_local_cues" in generated.legend_keys


def _structure_signature(lines: list[str]) -> str:
    structural_chars = set("@+|-=/\\#HMSGNICKDWwhb")
    return "".join(char for line in lines for char in line if char in structural_chars)

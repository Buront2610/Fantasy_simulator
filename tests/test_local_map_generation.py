"""Tests for procedural local maps used by location detail views."""

from __future__ import annotations

from types import SimpleNamespace

from fantasy_simulator.local_map_generation import generate_local_map


def _cell(location_id: str, region_type: str, *, x: int = 0, y: int = 0):
    return SimpleNamespace(
        location_id=location_id,
        region_type=region_type,
        x=x,
        y=y,
        danger=40,
        terrain_biome="plains",
        terrain_elevation=128,
        terrain_moisture=128,
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

    calm_lines = _scrub_state_overlays(generate_local_map(calm).lines)
    dangerous_map = generate_local_map(dangerous)
    dangerous_lines = _scrub_state_overlays(dangerous_map.lines)

    assert calm_lines == dangerous_lines
    assert "local_map_legend_state_overlay" in dangerous_map.legend_keys


def _scrub_state_overlays(lines: list[str]) -> list[str]:
    return [line.replace("!", " ").replace("?", " ").replace("r", " ") for line in lines]

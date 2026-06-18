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

    assert "Homes" in joined
    assert "Market" in joined
    assert "Shrine" in joined
    assert "Plaza" in joined or "Keep" in joined
    assert "local_map_scene_city" in generated.scene_keys


def test_city_maps_have_multiple_stable_urban_forms() -> None:
    maps = {
        tuple(generate_local_map(_cell(f"loc_city_{index}", "city", x=index, y=2)).lines)
        for index in range(8)
    }

    assert len(maps) >= 2


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

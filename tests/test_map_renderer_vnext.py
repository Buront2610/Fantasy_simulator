"""Tests for vNext map render info extensions."""

from fantasy_simulator.ui.map_renderer import build_map_info, render_location_detail
from fantasy_simulator.ui.atlas_renderer import render_atlas_minimal
from fantasy_simulator.ui.map_region_focus import region_focus_lines
from fantasy_simulator.world import World


def test_build_map_info_populates_vnext_overlay_fields():
    world = World()
    loc = world.get_location_by_id("loc_thornwood")
    assert loc is not None
    loc.aliases.append("Whispering Wood")
    loc.memorial_ids.append("m1")
    loc.danger = 80
    loc.traffic = 20
    loc.rumor_heat = 90

    info = build_map_info(world)
    cell = next(c for c in info.cells.values() if c.location_id == "loc_thornwood")
    assert cell.danger_band == "high"
    assert cell.traffic_band == "low"
    assert cell.rumor_heat_band == "high"
    assert cell.has_alias is True
    assert cell.has_memorial is True


def test_build_map_info_marks_authored_tower_sites():
    world = World()

    info = build_map_info(world)
    tower = next(c for c in info.cells.values() if c.location_id == "loc_eastwatch_tower")
    keep = next(c for c in info.cells.values() if c.location_id == "loc_stormwatch_keep")

    assert "tower" in tower.local_feature_tags
    assert "tower" in keep.local_feature_tags
    assert any(cue.tag == "tower" and cue.label == "Tower / keep" for cue in tower.local_feature_cues)


def test_build_map_info_exposes_authored_building_cues():
    world = World()

    info = build_map_info(world)
    tags = {tag for cell in info.cells.values() for tag in cell.local_feature_tags}

    assert {
        "bridge",
        "shrine",
        "inn",
        "guild",
        "mill",
        "dock",
        "forge",
        "warehouse",
        "stable",
        "barracks",
        "graveyard",
        "library",
        "ruined_house",
        "workshop",
        "farmstead",
        "watch_camp",
        "arena",
    }.issubset(tags)


def test_build_map_info_attaches_building_cues_to_culture():
    world = World()

    info = build_map_info(world)
    frostpeak = next(c for c in info.cells.values() if c.location_id == "loc_frostpeak_summit")
    culture_cues = {
        cue.tag: cue
        for cue in frostpeak.local_feature_cues
        if "culture" in cue.causes
    }

    assert {"forge", "warehouse", "barracks", "workshop"}.issubset(culture_cues)
    assert culture_cues["forge"].culture_key == "khazic"
    assert culture_cues["forge"].culture_label == "Northern Holds"


def test_build_map_info_attaches_shared_place_visual_profile():
    world = World()
    capital = world.get_location_by_id("loc_aethoria_capital")
    assert capital is not None
    capital.traffic = 90
    capital.prosperity = 90

    info = build_map_info(world)
    cell = next(c for c in info.cells.values() if c.location_id == "loc_aethoria_capital")

    assert cell.visual_profile.archetype == "market_city"
    assert cell.visual_profile.world_marker_primary == "C"
    assert cell.visual_profile.world_marker_suffix == "$"
    assert cell.visual_profile.short_label_key == "map_profile_market_city_short"


def test_atlas_minimal_lists_place_profile_summary():
    world = World()
    capital = world.get_location_by_id("loc_aethoria_capital")
    assert capital is not None
    capital.traffic = 90
    capital.prosperity = 90
    info = build_map_info(world)

    output = render_atlas_minimal(info)

    assert "Aethoria Capital" in output
    assert "C$" in output
    assert "market city" in output


def test_region_focus_starts_with_place_profile_summary():
    world = World()
    capital = world.get_location_by_id("loc_aethoria_capital")
    assert capital is not None
    capital.traffic = 90
    capital.prosperity = 90
    info = build_map_info(world)
    center = next(c for c in info.cells.values() if c.location_id == "loc_aethoria_capital")

    lines = region_focus_lines(
        list(info.cells.values()),
        center,
        info.routes,
        {cell.location_id: cell for cell in info.cells.values()},
        set(),
        set(),
        {},
        {},
        {},
        {},
    )

    assert "Profile: Aethoria Capital - market city" in lines


def test_location_detail_uses_shared_profile_scene():
    world = World()
    capital = world.get_location_by_id("loc_aethoria_capital")
    assert capital is not None
    capital.traffic = 90
    capital.prosperity = 90
    info = build_map_info(world)

    output = render_location_detail(info, "loc_aethoria_capital")

    assert "Profile: open market / plaza / lanes" in output


def test_location_detail_shows_cultural_building_causes():
    world = World()

    info = build_map_info(world)
    output = render_location_detail(info, "loc_frostpeak_summit")

    assert "Culture-built: Northern Holds: Forge, +3" in output

"""Tests for vNext map render info extensions."""

from fantasy_simulator.ui.map_renderer import build_map_info, render_location_detail
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


def test_location_detail_shows_cultural_building_causes():
    world = World()

    info = build_map_info(world)
    output = render_location_detail(info, "loc_frostpeak_summit")

    assert "Culture-built: Northern Holds: Forge, +3" in output

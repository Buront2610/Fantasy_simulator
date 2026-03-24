"""Tests for vNext map render info extensions."""

from fantasy_simulator.ui.map_renderer import build_map_info
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

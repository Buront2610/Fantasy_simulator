"""
Tests for PR-G1 terrain integration into World and migration v5→v6.

Key invariants verified:
- All terrain cells are within declared width × height bounds.
- All sites sit on valid terrain cells within bounds.
- World.from_dict() does NOT pollute with default 5×5 map.
- Variable-size worlds contain only in-bounds data.
- render_map_ascii shows terrain-only cells with biome glyphs.
"""

import json

import pytest

from fantasy_simulator.i18n import set_locale, get_locale
from fantasy_simulator.persistence.migrations import (
    CURRENT_VERSION,
    _migrate_v5_to_v6,
    migrate,
)
from fantasy_simulator.world import World


@pytest.fixture(autouse=True)
def _ensure_english_locale():
    """Set locale to English for tests and restore previous locale afterward."""
    prev = get_locale()
    set_locale("en")
    yield
    set_locale(prev)


def _assert_world_bounds_invariants(world: World) -> None:
    """Assert the three critical PR-G1 invariants on a world."""
    w, h = world.width, world.height

    # 1. All terrain cells within declared bounds
    if world.terrain_map is not None:
        for (x, y) in world.terrain_map.cells:
            assert 0 <= x < w, f"Terrain cell x={x} outside width={w}"
            assert 0 <= y < h, f"Terrain cell y={y} outside height={h}"

    # 2. All sites on valid terrain cells within bounds
    for site in world.sites:
        assert 0 <= site.x < w, f"Site {site.location_id} x={site.x} outside width={w}"
        assert 0 <= site.y < h, f"Site {site.location_id} y={site.y} outside height={h}"
        if world.terrain_map is not None:
            cell = world.terrain_map.get(site.x, site.y)
            assert cell is not None, f"Site {site.location_id} at ({site.x},{site.y}) has no terrain"

    # 3. All grid locations within bounds
    for (x, y) in world.grid:
        assert 0 <= x < w, f"Grid location at ({x},{y}) outside width={w}"
        assert 0 <= y < h, f"Grid location at ({x},{y}) outside height={h}"


# ------------------------------------------------------------------
# World terrain layer integration
# ------------------------------------------------------------------

class TestWorldTerrainLayer:
    def test_new_world_has_terrain(self):
        world = World()
        assert world.terrain_map is not None
        assert world.terrain_map.width == 5
        assert world.terrain_map.height == 5
        assert len(world.terrain_map.cells) == 25

    def test_new_world_has_sites(self):
        world = World()
        assert len(world.sites) == 25
        for site in world.sites:
            assert site.location_id in world._location_id_index

    def test_new_world_has_routes(self):
        world = World()
        assert len(world.routes) > 0
        site_ids = {s.location_id for s in world.sites}
        for route in world.routes:
            assert route.from_site_id in site_ids
            assert route.to_site_id in site_ids

    def test_new_world_satisfies_bounds_invariants(self):
        world = World()
        _assert_world_bounds_invariants(world)

    def test_get_site_by_id(self):
        world = World()
        site = world.get_site_by_id("loc_aethoria_capital")
        assert site is not None
        assert site.x == 2
        assert site.y == 2

    def test_get_routes_for_site(self):
        world = World()
        routes = world.get_routes_for_site("loc_aethoria_capital")
        assert len(routes) > 0
        for route in routes:
            assert route.connects("loc_aethoria_capital")

    def test_get_connected_site_ids(self):
        world = World()
        connected = world.get_connected_site_ids("loc_aethoria_capital")
        assert len(connected) > 0
        expected = sorted(
            route.other_end("loc_aethoria_capital")
            for route in world.get_routes_for_site("loc_aethoria_capital")
            if route.other_end("loc_aethoria_capital") is not None and not route.blocked
        )
        assert connected == expected

    def test_sites_on_valid_terrain(self):
        """Every site should sit on a valid terrain cell."""
        world = World()
        for site in world.sites:
            cell = world.terrain_map.get(site.x, site.y)
            assert cell is not None, f"Site {site.location_id} has no terrain"

    def test_blocked_route_excludes_from_connected(self):
        world = World()
        if not world.routes:
            return
        route = world.routes[0]
        route.blocked = True
        connected = world.get_connected_site_ids(route.from_site_id)
        assert route.to_site_id not in connected


# ------------------------------------------------------------------
# World round-trip with terrain
# ------------------------------------------------------------------

class TestWorldTerrainRoundTrip:
    def test_to_dict_omits_derived_terrain_for_bundle_backed_worlds(self):
        world = World()
        d = world.to_dict()
        assert "terrain_map" not in d
        assert "sites" not in d
        assert "routes" in d

    def test_round_trip_preserves_terrain(self):
        world = World()
        d = world.to_dict()
        json_str = json.dumps(d)
        restored_data = json.loads(json_str)
        restored = World.from_dict(restored_data)

        assert restored.terrain_map is not None
        assert restored.terrain_map.width == world.terrain_map.width
        assert restored.terrain_map.height == world.terrain_map.height
        assert len(restored.terrain_map.cells) == len(world.terrain_map.cells)
        assert len(restored.sites) == len(world.sites)
        assert len(restored.routes) == len(world.routes)
        _assert_world_bounds_invariants(restored)

    def test_round_trip_preserves_site_data(self):
        world = World()
        d = world.to_dict()
        restored = World.from_dict(d)

        for orig_site in world.sites:
            restored_site = restored.get_site_by_id(orig_site.location_id)
            assert restored_site is not None
            assert restored_site.x == orig_site.x
            assert restored_site.y == orig_site.y
            assert restored_site.site_type == orig_site.site_type

    def test_from_dict_without_terrain_generates_from_grid(self):
        """Loading save data without terrain should derive it from the grid."""
        world = World()
        d = world.to_dict()
        d.pop("terrain_map", None)
        d.pop("sites", None)
        d.pop("routes", None)

        restored = World.from_dict(d)
        assert restored.terrain_map is not None
        assert len(restored.sites) == 25
        assert len(restored.routes) > 0
        _assert_world_bounds_invariants(restored)

    def test_from_dict_does_not_inject_default_locations(self):
        """from_dict must NOT pollute with default Aethoria map entries.

        A world saved with only 2 locations must restore with exactly 2.
        """
        world = World(_skip_defaults=True, width=5, height=5)
        from fantasy_simulator.world import LocationState
        loc_a = LocationState(
            id="loc_custom_a", canonical_name="Custom Town",
            description="A custom town", region_type="city",
            x=0, y=0, prosperity=50, safety=50, mood=50,
            danger=20, traffic=30, rumor_heat=10, road_condition=60,
        )
        loc_b = LocationState(
            id="loc_custom_b", canonical_name="Custom Forest",
            description="A custom forest", region_type="forest",
            x=1, y=0, prosperity=10, safety=30, mood=40,
            danger=55, traffic=15, rumor_heat=10, road_condition=35,
        )
        world._register_location(loc_a)
        world._register_location(loc_b)
        world._build_terrain_from_grid()

        d = world.to_dict()
        restored = World.from_dict(d)

        assert len(restored.grid) == 2
        assert restored.get_location_by_id("loc_custom_a") is not None
        assert restored.get_location_by_id("loc_custom_b") is not None
        # No default Aethoria locations leaked in
        assert restored.get_location_by_id("loc_aethoria_capital") is None
        assert restored.get_location_by_id("loc_thornwood") is None
        _assert_world_bounds_invariants(restored)


# ------------------------------------------------------------------
# Variable world size — invariant enforcement
# ------------------------------------------------------------------

class TestVariableWorldSize:
    def test_3x3_world_contains_only_in_bounds_locations(self):
        """A 3×3 world must NOT contain any locations outside 3×3 bounds."""
        world = World(width=3, height=3)
        assert world.width == 3
        assert world.height == 3
        assert world.terrain_map is not None
        assert world.terrain_map.width == 3
        assert world.terrain_map.height == 3
        assert len(world.terrain_map.cells) == 9

        # All locations must be in-bounds
        for (x, y) in world.grid:
            assert 0 <= x < 3, f"Grid location at x={x} outside 3×3"
            assert 0 <= y < 3, f"Grid location at y={y} outside 3×3"

        # No legacy 5×5 locations should leak
        assert len(world.grid) < 25
        _assert_world_bounds_invariants(world)

    def test_3x3_world_no_5x5_leakage(self):
        """A 3×3 world must not contain locations at coords (3,*), (4,*), etc."""
        world = World(width=3, height=3)
        for loc in world.grid.values():
            assert loc.x < 3, f"Location {loc.id} has x={loc.x} >= 3"
            assert loc.y < 3, f"Location {loc.id} has y={loc.y} >= 3"
        for site in world.sites:
            assert site.x < 3, f"Site {site.location_id} has x={site.x} >= 3"
            assert site.y < 3, f"Site {site.location_id} has y={site.y} >= 3"

    def test_render_map_variable_size(self):
        """render_map should not crash with non-5x5 worlds."""
        world = World(width=3, height=3)
        result = world.render_map()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_8x8_world_round_trip_no_default_contamination(self):
        """An 8×8 world round-tripped must not have default 5×5 map residue."""
        world = World(width=8, height=8)
        d = world.to_dict()
        restored = World.from_dict(d)
        assert restored.width == 8
        assert restored.height == 8
        # Should have same number of locations as original
        assert len(restored.grid) == len(world.grid)
        assert len(restored.sites) == len(world.sites)
        _assert_world_bounds_invariants(restored)

    def test_1x1_world(self):
        """A 1×1 world should contain at most 1 location."""
        world = World(width=1, height=1)
        assert len(world.terrain_map.cells) == 1
        assert len(world.grid) <= 1
        _assert_world_bounds_invariants(world)


# ------------------------------------------------------------------
# Terrain-only cell rendering
# ------------------------------------------------------------------

class TestTerrainOnlyCellRendering:
    def test_terrain_only_cells_show_biome_glyph(self):
        """Terrain cells without sites should show biome info, not '???'."""
        from fantasy_simulator.ui.map_renderer import build_map_info, render_map_ascii
        # Create 2x1 world with a site at (0,0) but nothing at (1,0)
        world = World(_skip_defaults=True, width=2, height=1)
        from fantasy_simulator.world import LocationState
        loc = LocationState(
            id="loc_only", canonical_name="Only Town",
            description="The only town", region_type="city",
            x=0, y=0, prosperity=50, safety=50, mood=50,
            danger=20, traffic=30, rumor_heat=10, road_condition=60,
        )
        world._register_location(loc)
        world._build_terrain_from_grid()

        info = build_map_info(world)
        output = render_map_ascii(info)

        # The site cell should show "Only Town"
        assert "Only Town" in output
        # The terrain-only cell at (1,0) should show its biome, not "???"
        assert "???" not in output


# ------------------------------------------------------------------
# Migration v5 → v6
# ------------------------------------------------------------------

class TestMigrationV5ToV6:
    def _make_v5_data(self):
        """Create minimal v5 save data."""
        return {
            "schema_version": 5,
            "characters": [],
            "world": {
                "name": "TestWorld",
                "width": 3,
                "height": 2,
                "year": 1000,
                "grid": [
                    {
                        "id": "loc_a", "canonical_name": "Town A",
                        "description": "A town", "region_type": "city",
                        "x": 0, "y": 0,
                        "prosperity": 70, "safety": 65, "mood": 55,
                        "danger": 25, "traffic": 70, "rumor_heat": 45,
                        "road_condition": 75, "visited": False,
                        "controlling_faction_id": None,
                        "recent_event_ids": [], "aliases": [],
                        "memorial_ids": [], "live_traces": [],
                    },
                    {
                        "id": "loc_b", "canonical_name": "Village B",
                        "description": "A village", "region_type": "village",
                        "x": 1, "y": 0,
                        "prosperity": 50, "safety": 55, "mood": 55,
                        "danger": 30, "traffic": 35, "rumor_heat": 20,
                        "road_condition": 55, "visited": False,
                        "controlling_faction_id": None,
                        "recent_event_ids": [], "aliases": [],
                        "memorial_ids": [], "live_traces": [],
                    },
                    {
                        "id": "loc_c", "canonical_name": "Mountain C",
                        "description": "A mountain", "region_type": "mountain",
                        "x": 0, "y": 1,
                        "prosperity": 5, "safety": 25, "mood": 35,
                        "danger": 65, "traffic": 10, "rumor_heat": 10,
                        "road_condition": 30, "visited": False,
                        "controlling_faction_id": None,
                        "recent_event_ids": [], "aliases": [],
                        "memorial_ids": [], "live_traces": [],
                    },
                ],
                "event_log": [],
                "event_records": [],
                "rumors": [],
                "rumor_archive": [],
                "active_adventures": [],
                "completed_adventures": [],
                "memorials": {},
            },
        }

    def test_current_version_is_8(self):
        assert CURRENT_VERSION == 8

    def test_migration_adds_terrain(self):
        data = self._make_v5_data()
        result = _migrate_v5_to_v6(data)
        assert result["schema_version"] == 6
        world = result["world"]
        assert "terrain_map" in world
        assert "sites" in world
        assert "routes" in world

    def test_migration_terrain_dimensions(self):
        data = self._make_v5_data()
        result = _migrate_v5_to_v6(data)
        terrain = result["world"]["terrain_map"]
        assert terrain["width"] == 3
        assert terrain["height"] == 2
        assert len(terrain["cells"]) == 6  # 3 * 2

    def test_migration_sites_match_grid(self):
        data = self._make_v5_data()
        result = _migrate_v5_to_v6(data)
        sites = result["world"]["sites"]
        assert len(sites) == 3
        site_ids = {s["location_id"] for s in sites}
        assert site_ids == {"loc_a", "loc_b", "loc_c"}

    def test_migration_biomes_from_region_type(self):
        data = self._make_v5_data()
        result = _migrate_v5_to_v6(data)
        cells = result["world"]["terrain_map"]["cells"]
        cell_lookup = {(c["x"], c["y"]): c for c in cells}
        # city -> plains
        assert cell_lookup[(0, 0)]["biome"] == "plains"
        # village -> plains
        assert cell_lookup[(1, 0)]["biome"] == "plains"
        # mountain -> mountain
        assert cell_lookup[(0, 1)]["biome"] == "mountain"

    def test_migration_routes_generated(self):
        data = self._make_v5_data()
        result = _migrate_v5_to_v6(data)
        routes = result["world"]["routes"]
        assert len(routes) >= 2  # at least a-b and a-c

    def test_migration_mountain_route_type(self):
        data = self._make_v5_data()
        result = _migrate_v5_to_v6(data)
        routes = result["world"]["routes"]
        # Route between loc_a(city/plains) and loc_c(mountain) should be mountain_pass
        mountain_routes = [
            r for r in routes
            if set([r["from_site_id"], r["to_site_id"]]) == {"loc_a", "loc_c"}
        ]
        assert len(mountain_routes) == 1
        assert mountain_routes[0]["route_type"] == "mountain_pass"

    def test_full_migration_chain(self):
        """A v5 save should migrate to the current schema through the full chain."""
        data = self._make_v5_data()
        result = migrate(data)
        assert result["schema_version"] == CURRENT_VERSION
        assert "terrain_map" in result["world"]

    def test_migrated_data_loads_as_world(self):
        """Data migrated from v5 should successfully load as a World."""
        data = self._make_v5_data()
        result = migrate(data)
        world = World.from_dict(result["world"])
        assert world.terrain_map is not None
        assert len(world.sites) == 3
        assert len(world.routes) >= 2
        _assert_world_bounds_invariants(world)

    def test_migration_skips_out_of_bounds_sites(self):
        """v5→v6 migration must skip grid locations outside declared bounds."""
        data = self._make_v5_data()
        # Add an out-of-bounds location (x=10 in a 3-wide world)
        data["world"]["grid"].append({
            "id": "loc_oob", "canonical_name": "OOB Town",
            "description": "Out of bounds", "region_type": "city",
            "x": 10, "y": 0,
            "prosperity": 50, "safety": 50, "mood": 50,
            "danger": 20, "traffic": 30, "rumor_heat": 10,
            "road_condition": 60, "visited": False,
            "controlling_faction_id": None,
            "recent_event_ids": [], "aliases": [],
            "memorial_ids": [], "live_traces": [],
        })
        result = _migrate_v5_to_v6(data)
        sites = result["world"]["sites"]
        site_ids = {s["location_id"] for s in sites}
        # The OOB location must not appear as a site
        assert "loc_oob" not in site_ids
        # Original 3 in-bounds locations remain
        assert len(sites) == 3

"""
Tests for PR-G1 terrain integration into World and migration v5→v6.
"""

import json

from fantasy_simulator.i18n import set_locale
from fantasy_simulator.persistence.migrations import (
    CURRENT_VERSION,
    _migrate_v5_to_v6,
    migrate,
)
from fantasy_simulator.world import World


set_locale("en")


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
        # Capital at (2,2) should connect to 4 neighbors
        assert len(connected) == 4

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
    def test_to_dict_includes_terrain(self):
        world = World()
        d = world.to_dict()
        assert "terrain_map" in d
        assert "sites" in d
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

    def test_from_dict_without_terrain_generates_default(self):
        """Loading old save data without terrain should auto-generate it."""
        world = World()
        d = world.to_dict()
        del d["terrain_map"]
        del d["sites"]
        del d["routes"]

        restored = World.from_dict(d)
        assert restored.terrain_map is not None
        assert len(restored.sites) == 25
        assert len(restored.routes) > 0


# ------------------------------------------------------------------
# Variable world size
# ------------------------------------------------------------------

class TestVariableWorldSize:
    def test_3x3_world(self):
        """A 3x3 world should work without issues."""
        world = World(width=3, height=3)
        # The default map still creates 25 locations at 5x5 coords,
        # but only those within bounds should be in the terrain map
        assert world.width == 3
        assert world.height == 3
        # Terrain should cover the full 3x3 grid
        assert world.terrain_map is not None
        assert world.terrain_map.width == 3
        assert world.terrain_map.height == 3

    def test_render_map_variable_size(self):
        """render_map should not crash with non-5x5 worlds."""
        world = World(width=3, height=3)
        result = world.render_map()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_8x8_world_from_dict(self):
        """Round-trip an 8x8 world."""
        world = World(width=8, height=8)
        d = world.to_dict()
        d["width"] = 8
        d["height"] = 8
        restored = World.from_dict(d)
        assert restored.width == 8
        assert restored.height == 8


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

    def test_current_version_is_6(self):
        assert CURRENT_VERSION == 6

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
        """A v5 save should migrate to v6 through the full chain."""
        data = self._make_v5_data()
        result = migrate(data)
        assert result["schema_version"] == 6
        assert "terrain_map" in result["world"]

    def test_migrated_data_loads_as_world(self):
        """Data migrated from v5 should successfully load as a World."""
        data = self._make_v5_data()
        result = migrate(data)
        world = World.from_dict(result["world"])
        assert world.terrain_map is not None
        assert len(world.sites) == 3
        assert len(world.routes) >= 2

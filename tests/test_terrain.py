"""
Tests for fantasy_simulator.terrain — TerrainCell, Site, RouteEdge,
TerrainMap, and the default terrain builder.
"""

import json
import pytest

from fantasy_simulator.terrain import (
    BIOME_GLYPHS,
    BIOME_MOVE_COST,
    BIOME_TYPES,
    ROUTE_TYPES,
    RouteEdge,
    Site,
    TerrainCell,
    TerrainMap,
    build_default_terrain,
)


# ------------------------------------------------------------------
# TerrainCell
# ------------------------------------------------------------------

class TestTerrainCell:
    def test_defaults(self):
        cell = TerrainCell(x=0, y=0)
        assert cell.biome == "plains"
        assert cell.elevation == 128
        assert cell.moisture == 128
        assert cell.temperature == 128

    def test_glyph(self):
        for biome in BIOME_TYPES:
            cell = TerrainCell(x=0, y=0, biome=biome)
            assert cell.glyph == BIOME_GLYPHS[biome]

    def test_move_cost(self):
        cell = TerrainCell(x=0, y=0, biome="mountain")
        assert cell.move_cost == BIOME_MOVE_COST["mountain"]

    def test_is_passable(self):
        assert TerrainCell(x=0, y=0, biome="plains").is_passable
        assert TerrainCell(x=0, y=0, biome="forest").is_passable
        assert not TerrainCell(x=0, y=0, biome="ocean").is_passable

    def test_round_trip(self):
        cell = TerrainCell(x=3, y=7, biome="swamp", elevation=50, moisture=200, temperature=80)
        restored = TerrainCell.from_dict(cell.to_dict())
        assert restored.x == cell.x
        assert restored.y == cell.y
        assert restored.biome == cell.biome
        assert restored.elevation == cell.elevation
        assert restored.moisture == cell.moisture
        assert restored.temperature == cell.temperature

    def test_json_serializable(self):
        cell = TerrainCell(x=1, y=2, biome="forest")
        json.dumps(cell.to_dict())  # should not raise


# ------------------------------------------------------------------
# Site
# ------------------------------------------------------------------

class TestSite:
    def test_defaults(self):
        site = Site(location_id="loc_test", x=2, y=3)
        assert site.site_type == "city"
        assert site.importance == 50

    def test_round_trip(self):
        site = Site(location_id="loc_abc", x=1, y=4, site_type="dungeon", importance=75)
        restored = Site.from_dict(site.to_dict())
        assert restored.location_id == site.location_id
        assert restored.x == site.x
        assert restored.y == site.y
        assert restored.site_type == site.site_type
        assert restored.importance == site.importance


# ------------------------------------------------------------------
# RouteEdge
# ------------------------------------------------------------------

class TestRouteEdge:
    def test_connects(self):
        route = RouteEdge(
            route_id="r1", from_site_id="loc_a", to_site_id="loc_b",
        )
        assert route.connects("loc_a")
        assert route.connects("loc_b")
        assert not route.connects("loc_c")

    def test_other_end(self):
        route = RouteEdge(
            route_id="r1", from_site_id="loc_a", to_site_id="loc_b",
        )
        assert route.other_end("loc_a") == "loc_b"
        assert route.other_end("loc_b") == "loc_a"
        assert route.other_end("loc_c") is None

    def test_base_cost(self):
        for rt in ROUTE_TYPES:
            route = RouteEdge(route_id="r", from_site_id="a", to_site_id="b", route_type=rt)
            assert route.base_cost > 0

    def test_round_trip(self):
        route = RouteEdge(
            route_id="r99", from_site_id="loc_x", to_site_id="loc_y",
            route_type="mountain_pass", distance=3, blocked=True,
        )
        restored = RouteEdge.from_dict(route.to_dict())
        assert restored.route_id == route.route_id
        assert restored.from_site_id == route.from_site_id
        assert restored.to_site_id == route.to_site_id
        assert restored.route_type == route.route_type
        assert restored.distance == route.distance
        assert restored.blocked == route.blocked


# ------------------------------------------------------------------
# TerrainMap
# ------------------------------------------------------------------

class TestTerrainMap:
    def test_basic_operations(self):
        tmap = TerrainMap(width=3, height=3)
        cell = TerrainCell(x=1, y=2, biome="forest")
        tmap.set_cell(cell)
        assert tmap.get(1, 2) is cell
        assert tmap.get(0, 0) is None

    def test_in_bounds(self):
        tmap = TerrainMap(width=5, height=5)
        assert tmap.in_bounds(0, 0)
        assert tmap.in_bounds(4, 4)
        assert not tmap.in_bounds(5, 0)
        assert not tmap.in_bounds(-1, 0)

    def test_neighbors(self):
        tmap = TerrainMap(width=3, height=3)
        for y in range(3):
            for x in range(3):
                tmap.set_cell(TerrainCell(x=x, y=y))
        # Center cell has 4 neighbors
        assert len(tmap.neighbors(1, 1)) == 4
        # Corner cell has 2 neighbors
        assert len(tmap.neighbors(0, 0)) == 2

    def test_round_trip(self):
        tmap = TerrainMap(width=2, height=2)
        for y in range(2):
            for x in range(2):
                tmap.set_cell(TerrainCell(x=x, y=y, biome="forest"))
        restored = TerrainMap.from_dict(tmap.to_dict())
        assert restored.width == tmap.width
        assert restored.height == tmap.height
        assert len(restored.cells) == len(tmap.cells)
        for key, cell in tmap.cells.items():
            assert key in restored.cells
            assert restored.cells[key].biome == cell.biome


# ------------------------------------------------------------------
# build_default_terrain
# ------------------------------------------------------------------

class TestBuildDefaultTerrain:
    def test_default_5x5(self):
        tmap, sites, routes = build_default_terrain()
        assert tmap.width == 5
        assert tmap.height == 5
        assert len(tmap.cells) == 25
        assert len(sites) == 25
        assert len(routes) > 0

    def test_all_sites_on_valid_terrain(self):
        tmap, sites, _ = build_default_terrain()
        for site in sites:
            cell = tmap.get(site.x, site.y)
            assert cell is not None, f"Site {site.location_id} at ({site.x},{site.y}) has no terrain cell"

    def test_routes_connect_existing_sites(self):
        _, sites, routes = build_default_terrain()
        site_ids = {s.location_id for s in sites}
        for route in routes:
            assert route.from_site_id in site_ids, f"Route {route.route_id} from unknown site"
            assert route.to_site_id in site_ids, f"Route {route.route_id} to unknown site"

    def test_routes_are_bidirectional(self):
        """Each route should appear only once per pair."""
        _, _, routes = build_default_terrain()
        pairs = set()
        for route in routes:
            pair = tuple(sorted([route.from_site_id, route.to_site_id]))
            assert pair not in pairs, f"Duplicate route for {pair}"
            pairs.add(pair)

    def test_variable_size(self):
        """Terrain builder works with non-5x5 sizes."""
        locations = [
            ("loc_a", "Town A", "A town", "city", 0, 0),
            ("loc_b", "Town B", "A town", "village", 1, 0),
            ("loc_c", "Forest C", "A forest", "forest", 0, 1),
        ]
        tmap, sites, routes = build_default_terrain(width=2, height=2, locations=locations)
        assert tmap.width == 2
        assert tmap.height == 2
        assert len(tmap.cells) == 4  # all grid cells populated
        assert len(sites) == 3
        # At least some routes between adjacent sites
        assert len(routes) >= 2

    def test_mountain_route_type(self):
        """Routes involving mountain terrain should be mountain_pass."""
        locations = [
            ("loc_m", "Peak", "A peak", "mountain", 0, 0),
            ("loc_p", "Town", "A town", "city", 1, 0),
        ]
        _, _, routes = build_default_terrain(width=2, height=1, locations=locations)
        assert len(routes) == 1
        assert routes[0].route_type == "mountain_pass"

    def test_out_of_bounds_locations_skipped(self):
        """Locations outside the declared dimensions are silently dropped."""
        locations = [
            ("loc_a", "A", "A", "city", 0, 0),
            ("loc_b", "B", "B", "village", 5, 5),  # out of bounds for 3x3
            ("loc_c", "C", "C", "forest", 2, 2),
        ]
        tmap, sites, routes = build_default_terrain(width=3, height=3, locations=locations)
        assert len(sites) == 2
        site_ids = {s.location_id for s in sites}
        assert "loc_a" in site_ids
        assert "loc_c" in site_ids
        assert "loc_b" not in site_ids

    def test_invalid_route_specs_fail_fast_for_unknown_sites(self):
        locations = [
            ("loc_a", "A", "A", "city", 0, 0),
            ("loc_b", "B", "B", "village", 1, 0),
        ]
        route_specs = [
            {
                "route_id": "route_invalid",
                "from_site_id": "loc_a",
                "to_site_id": "loc_missing",
                "route_type": "road",
                "distance": 1,
                "blocked": False,
            }
        ]

        with pytest.raises(ValueError):
            build_default_terrain(width=2, height=1, locations=locations, route_specs=route_specs)

    def test_default_locations_filtered_by_size(self):
        """Using DEFAULT_LOCATIONS with a small grid drops out-of-bounds entries."""
        tmap, sites, _ = build_default_terrain(width=3, height=3)
        for site in sites:
            assert 0 <= site.x < 3, f"Site {site.location_id} x={site.x} out of bounds"
            assert 0 <= site.y < 3, f"Site {site.location_id} y={site.y} out of bounds"
        for (x, y) in tmap.cells:
            assert 0 <= x < 3, f"Terrain cell x={x} out of bounds"
            assert 0 <= y < 3, f"Terrain cell y={y} out of bounds"
        # 3x3 grid = 9 terrain cells
        assert len(tmap.cells) == 9
        # Fewer than 25 sites since most DEFAULT_LOCATIONS are outside 3x3
        assert len(sites) < 25


class TestTerrainMapBoundsEnforcement:
    def test_set_cell_rejects_out_of_bounds(self):
        import pytest
        tmap = TerrainMap(width=3, height=3)
        with pytest.raises(ValueError, match="outside terrain bounds"):
            tmap.set_cell(TerrainCell(x=5, y=0))

    def test_set_cell_rejects_negative(self):
        import pytest
        tmap = TerrainMap(width=3, height=3)
        with pytest.raises(ValueError, match="outside terrain bounds"):
            tmap.set_cell(TerrainCell(x=-1, y=0))

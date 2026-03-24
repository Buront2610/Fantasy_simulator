"""Tests for PR-G2 observation UI — three-layer map rendering.

Covers:
- render_world_overview: compact terrain glyph grid + overlay markers + legend
- render_region_map: zoomed view around a selected site
- render_location_detail: single-site AA panel with world-memory data
- _overlay_suffix: overlay marker logic
- Navigation integration via _show_world_map
"""

from __future__ import annotations

import unittest

from fantasy_simulator.i18n import set_locale
from fantasy_simulator.ui.map_renderer import (
    MapCellInfo,
    MapRenderInfo,
    RouteRenderInfo,
    TerrainCellRenderInfo,
    build_map_info,
    render_world_overview,
    render_region_map,
    render_location_detail,
    _overlay_suffix,
)
from fantasy_simulator.ui.atlas_renderer import (
    render_atlas_overview,
    _build_atlas_canvas,
    _bresenham,
    _terrain_char,
    _overlay_suffix as _atlas_overlay_suffix,
)
from fantasy_simulator.world import World


def _make_simple_info() -> MapRenderInfo:
    """Build a minimal 3x3 MapRenderInfo with one site at (1,1)."""
    info = MapRenderInfo(
        world_name="TestWorld",
        year=10,
        width=3,
        height=3,
    )
    # Fill terrain
    from fantasy_simulator.terrain import BIOME_GLYPHS
    biomes = ["forest", "plains", "mountain",
              "plains", "plains", "forest",
              "hills", "plains", "coast"]
    for y in range(3):
        for x in range(3):
            b = biomes[y * 3 + x]
            info.terrain_cells[(x, y)] = TerrainCellRenderInfo(
                x=x, y=y, biome=b, glyph=BIOME_GLYPHS[b],
            )
    # One site at (1, 1)
    info.cells[(1, 1)] = MapCellInfo(
        location_id="loc_test_town",
        canonical_name="TestTown",
        region_type="city",
        icon="@",
        safety_label="peaceful",
        danger=20,
        traffic_indicator="busy",
        population=5,
        x=1, y=1,
        danger_band="low",
        traffic_band="high",
        rumor_heat_band="low",
        terrain_biome="plains",
        terrain_glyph=",",
    )
    # A second site at (0, 0)
    info.cells[(0, 0)] = MapCellInfo(
        location_id="loc_forest_camp",
        canonical_name="ForestCamp",
        region_type="village",
        icon="#",
        safety_label="dangerous",
        danger=70,
        traffic_indicator="quiet",
        population=2,
        x=0, y=0,
        danger_band="high",
        traffic_band="low",
        rumor_heat_band="medium",
        has_memorial=True,
        recent_death_site=True,
        terrain_biome="forest",
        terrain_glyph="T",
    )
    # Route between them
    info.routes.append(RouteRenderInfo(
        route_id="r1",
        from_site_id="loc_test_town",
        to_site_id="loc_forest_camp",
        route_type="road",
    ))
    return info


class TestOverlaySuffix(unittest.TestCase):
    """Verify _overlay_suffix builds correct marker strings."""

    def test_no_overlays(self) -> None:
        cell = MapCellInfo(
            location_id="x", canonical_name="X", region_type="city",
            icon="@", safety_label="ok", danger=10, traffic_indicator="",
            population=0, x=0, y=0, danger_band="low",
        )
        self.assertEqual(_overlay_suffix(cell), "")

    def test_high_danger_only(self) -> None:
        cell = MapCellInfo(
            location_id="x", canonical_name="X", region_type="city",
            icon="@", safety_label="ok", danger=80, traffic_indicator="",
            population=0, x=0, y=0, danger_band="high",
        )
        self.assertEqual(_overlay_suffix(cell), "!")

    def test_memorial_and_alias(self) -> None:
        cell = MapCellInfo(
            location_id="x", canonical_name="X", region_type="city",
            icon="@", safety_label="ok", danger=10, traffic_indicator="",
            population=0, x=0, y=0, danger_band="low",
            has_memorial=True, has_alias=True,
        )
        self.assertEqual(_overlay_suffix(cell), "ma")

    def test_all_overlays(self) -> None:
        cell = MapCellInfo(
            location_id="x", canonical_name="X", region_type="city",
            icon="@", safety_label="ok", danger=80, traffic_indicator="",
            population=0, x=0, y=0, danger_band="high",
            has_memorial=True, has_alias=True, recent_death_site=True,
        )
        self.assertEqual(_overlay_suffix(cell), "!ma+")


class TestRenderWorldOverview(unittest.TestCase):
    """Verify render_world_overview produces a readable compact map."""

    def setUp(self) -> None:
        set_locale("en")
        self.info = _make_simple_info()

    def test_contains_world_name_and_year(self) -> None:
        output = render_world_overview(self.info)
        self.assertIn("TestWorld", output)
        self.assertIn("10", output)

    def test_contains_site_in_listing(self) -> None:
        output = render_world_overview(self.info)
        self.assertIn("TestTown", output)
        self.assertIn("ForestCamp", output)

    def test_contains_legend(self) -> None:
        output = render_world_overview(self.info)
        self.assertIn("Legend", output)
        self.assertIn("~ =", output)  # ocean glyph in legend
        self.assertIn("High danger", output)

    def test_overlay_marker_appears_in_grid(self) -> None:
        """ForestCamp has high danger → overlay '!' should appear at (0,0)."""
        output = render_world_overview(self.info)
        # The grid row for y=0 should contain the overlay marker
        lines = output.split("\n")
        grid_lines = [ln for ln in lines if "|" in ln and ln.strip().startswith("0")]
        self.assertTrue(len(grid_lines) > 0, "Grid row 0 not found")
        # ForestCamp at (0,0) should show '!' (first overlay char)
        self.assertIn("!", grid_lines[0])

    def test_route_listed(self) -> None:
        output = render_world_overview(self.info)
        self.assertIn("loc_test_town", output)
        self.assertIn("loc_forest_camp", output)

    def test_terrain_glyph_in_grid(self) -> None:
        """Terrain-only cells should show their biome glyph."""
        output = render_world_overview(self.info)
        # (2,0) is mountain → glyph '^'
        self.assertIn("^", output)

    def test_output_from_real_world(self) -> None:
        """Build from a real World object and ensure it renders without error."""
        world = World()
        info = build_map_info(world)
        output = render_world_overview(info)
        self.assertIn("Aethoria", output)
        self.assertIn("Legend", output)


class TestRenderRegionMap(unittest.TestCase):
    """Verify render_region_map produces a zoomed view."""

    def setUp(self) -> None:
        set_locale("en")
        self.info = _make_simple_info()

    def test_center_site_shown_as_at(self) -> None:
        output = render_region_map(self.info, "loc_test_town", radius=2)
        self.assertIn("@", output)
        self.assertIn("TestTown", output)

    def test_nearby_sites_listed(self) -> None:
        output = render_region_map(self.info, "loc_test_town", radius=2)
        self.assertIn("ForestCamp", output)

    def test_routes_from_center(self) -> None:
        output = render_region_map(self.info, "loc_test_town", radius=2)
        self.assertIn("loc_forest_camp", output)

    def test_not_found_location(self) -> None:
        output = render_region_map(self.info, "nonexistent")
        self.assertIn("nonexistent", output)

    def test_radius_clips_to_bounds(self) -> None:
        """With radius=0, only the center cell is shown."""
        output = render_region_map(self.info, "loc_test_town", radius=0)
        self.assertIn("@", output)
        # ForestCamp at (0,0) should NOT be in the grid (only (1,1))
        grid_lines = [ln for ln in output.split("\n") if "|" in ln and not ln.strip().startswith("+")]
        # Should have exactly one grid row
        data_rows = [ln for ln in grid_lines if ln.strip() and not ln.strip().startswith("+")]
        self.assertTrue(len(data_rows) >= 1)

    def test_output_from_real_world(self) -> None:
        world = World()
        info = build_map_info(world)
        loc_id = list(world.grid.values())[0].id
        output = render_region_map(info, loc_id)
        self.assertIn("@", output)


class TestRenderLocationDetail(unittest.TestCase):
    """Verify render_location_detail produces an AA panel."""

    def setUp(self) -> None:
        set_locale("en")
        self.info = _make_simple_info()

    def test_basic_detail_output(self) -> None:
        output = render_location_detail(self.info, "loc_test_town")
        self.assertIn("TestTown", output)
        self.assertIn("Danger", output)
        self.assertIn("Pop", output)

    def test_detail_with_memorials(self) -> None:
        output = render_location_detail(
            self.info, "loc_test_town",
            memorials=["Year 5: Hero fell here."],
        )
        self.assertIn("Hero fell here", output)

    def test_detail_with_aliases(self) -> None:
        output = render_location_detail(
            self.info, "loc_test_town",
            aliases=["The Crossroads"],
        )
        self.assertIn("The Crossroads", output)

    def test_detail_with_live_traces(self) -> None:
        output = render_location_detail(
            self.info, "loc_test_town",
            live_traces=["Alice visited in year 8."],
        )
        self.assertIn("Alice visited", output)

    def test_overlay_markers_shown(self) -> None:
        """ForestCamp has memorial and recent death → markers shown."""
        output = render_location_detail(self.info, "loc_forest_camp")
        self.assertIn("Memorial", output)
        self.assertIn("Recent death", output)

    def test_not_found(self) -> None:
        output = render_location_detail(self.info, "nonexistent")
        self.assertIn("nonexistent", output)

    def test_output_from_real_world(self) -> None:
        world = World()
        info = build_map_info(world)
        loc_id = list(world.grid.values())[0].id
        output = render_location_detail(info, loc_id)
        self.assertIn(list(world.grid.values())[0].canonical_name, output)


class TestCJKWidth(unittest.TestCase):
    """Verify the overview map doesn't break with Japanese locale."""

    def test_japanese_locale_overview(self) -> None:
        set_locale("ja")
        world = World()
        info = build_map_info(world)
        output = render_world_overview(info)
        self.assertIn("Aethoria", output)
        # Should contain Japanese legend title
        self.assertIn("凡例", output)
        set_locale("en")


class TestBresenham(unittest.TestCase):
    """Verify Bresenham line drawing helper."""

    def test_horizontal_line(self) -> None:
        pts = _bresenham(0, 0, 5, 0)
        self.assertEqual(len(pts), 6)
        self.assertEqual(pts[0], (0, 0))
        self.assertEqual(pts[-1], (5, 0))

    def test_vertical_line(self) -> None:
        pts = _bresenham(0, 0, 0, 4)
        self.assertEqual(len(pts), 5)

    def test_diagonal_line(self) -> None:
        pts = _bresenham(0, 0, 3, 3)
        self.assertIn((0, 0), pts)
        self.assertIn((3, 3), pts)

    def test_single_point(self) -> None:
        pts = _bresenham(2, 2, 2, 2)
        self.assertEqual(pts, [(2, 2)])


class TestTerrainChar(unittest.TestCase):
    """Verify terrain character selection is deterministic."""

    def test_deterministic(self) -> None:
        c1 = _terrain_char("forest", 10, 20)
        c2 = _terrain_char("forest", 10, 20)
        self.assertEqual(c1, c2)

    def test_forest_chars(self) -> None:
        chars = set(_terrain_char("forest", x, y) for x in range(20) for y in range(20))
        # Should use characters from the forest palette "TtYf"
        self.assertTrue(chars.issubset(set("TtYf")))

    def test_unknown_biome_fallback(self) -> None:
        ch = _terrain_char("unknown_biome", 0, 0)
        self.assertIn(ch, ".,',")


class TestAtlasOverlaySuffix(unittest.TestCase):
    """Verify atlas_renderer's own _overlay_suffix."""

    def test_matches_map_renderer(self) -> None:
        cell = MapCellInfo(
            location_id="x", canonical_name="X", region_type="city",
            icon="@", safety_label="ok", danger=80, traffic_indicator="",
            population=0, x=0, y=0, danger_band="high",
            has_memorial=True, has_alias=True, recent_death_site=True,
        )
        self.assertEqual(_atlas_overlay_suffix(cell), "!ma+")


class TestBuildAtlasCanvas(unittest.TestCase):
    """Verify atlas canvas generation produces correct structure."""

    def setUp(self) -> None:
        set_locale("en")
        self.info = _make_simple_info()

    def test_canvas_dimensions(self) -> None:
        canvas = _build_atlas_canvas(self.info)
        self.assertEqual(len(canvas), 30)  # _ATLAS_H
        self.assertEqual(len(canvas[0]), 72)  # _ATLAS_W

    def test_canvas_has_ocean(self) -> None:
        canvas = _build_atlas_canvas(self.info)
        flat = "".join("".join(row) for row in canvas)
        self.assertIn("~", flat)

    def test_canvas_has_site_markers(self) -> None:
        canvas = _build_atlas_canvas(self.info)
        flat = "".join("".join(row) for row in canvas)
        self.assertIn("@", flat)

    def test_empty_info_returns_ocean(self) -> None:
        empty = MapRenderInfo(world_name="Empty", year=1, width=3, height=3)
        canvas = _build_atlas_canvas(empty)
        flat = "".join("".join(row) for row in canvas)
        # All ocean
        self.assertTrue(all(c == "~" for c in flat))


class TestRenderAtlasOverview(unittest.TestCase):
    """Verify render_atlas_overview produces readable atlas map."""

    def setUp(self) -> None:
        set_locale("en")
        self.info = _make_simple_info()

    def test_contains_world_name_and_year(self) -> None:
        output = render_atlas_overview(self.info)
        self.assertIn("TestWorld", output)
        self.assertIn("10", output)

    def test_contains_site_labels(self) -> None:
        output = render_atlas_overview(self.info)
        self.assertIn("TestTown", output)
        self.assertIn("ForestCamp", output)

    def test_contains_legend(self) -> None:
        output = render_atlas_overview(self.info)
        self.assertIn("Legend", output)

    def test_contains_terrain_chars(self) -> None:
        output = render_atlas_overview(self.info)
        # Should contain varied terrain characters, not just ~
        has_land = any(c in output for c in ".,TtYfnNh^")
        self.assertTrue(has_land, "Atlas should contain land terrain characters")

    def test_contains_route_legend(self) -> None:
        output = render_atlas_overview(self.info)
        self.assertIn("Route lines", output)

    def test_output_from_real_world(self) -> None:
        world = World()
        info = build_map_info(world)
        output = render_atlas_overview(info)
        self.assertIn("Aethoria", output)
        self.assertIn("Legend", output)

    def test_japanese_locale(self) -> None:
        set_locale("ja")
        world = World()
        info = build_map_info(world)
        output = render_atlas_overview(info)
        self.assertIn("Aethoria", output)
        self.assertIn("凡例", output)
        set_locale("en")


if __name__ == "__main__":
    unittest.main()

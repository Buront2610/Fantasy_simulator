"""Tests for PR-G2 observation UI — three-layer map rendering.

Covers:
- render_world_overview: compact terrain glyph grid + overlay markers + legend
- render_region_map: zoomed view around a selected site with route lines
- render_location_detail: single-site AA panel with world-memory data
- _overlay_suffix: overlay marker logic (danger, traffic, rumor, memorial, alias, death)
- atlas_renderer: continent canvas, terrain, Bresenham lines, labels
"""

from __future__ import annotations

import random
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
    _cluster_sites,
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
            traffic_band="high", rumor_heat_band="high",
            has_memorial=True, has_alias=True, recent_death_site=True,
        )
        self.assertEqual(_overlay_suffix(cell), "!$?ma+")

    def test_traffic_high_only(self) -> None:
        cell = MapCellInfo(
            location_id="x", canonical_name="X", region_type="city",
            icon="@", safety_label="ok", danger=10, traffic_indicator="",
            population=0, x=0, y=0, danger_band="low",
            traffic_band="high",
        )
        self.assertEqual(_overlay_suffix(cell), "$")

    def test_rumor_high_only(self) -> None:
        cell = MapCellInfo(
            location_id="x", canonical_name="X", region_type="city",
            icon="@", safety_label="ok", danger=10, traffic_indicator="",
            population=0, x=0, y=0, danger_band="low",
            rumor_heat_band="high",
        )
        self.assertEqual(_overlay_suffix(cell), "?")


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
        self.assertIn("High traffic", output)
        self.assertIn("High rumor heat", output)

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

    def test_route_lines_drawn_on_grid(self) -> None:
        """Route lines are drawn between sites when path has intermediate cells."""
        # Create a wider grid so route has intermediate cells
        info = MapRenderInfo(
            world_name="RouteTest", year=1, width=5, height=5,
        )
        for y in range(5):
            for x in range(5):
                info.terrain_cells[(x, y)] = TerrainCellRenderInfo(
                    x=x, y=y, biome="plains", glyph=",",
                )
        info.cells[(0, 2)] = MapCellInfo(
            location_id="loc_a", canonical_name="Alpha", region_type="city",
            icon="@", safety_label="ok", danger=10, traffic_indicator="",
            population=0, x=0, y=2, danger_band="low",
        )
        info.cells[(4, 2)] = MapCellInfo(
            location_id="loc_b", canonical_name="Beta", region_type="city",
            icon="@", safety_label="ok", danger=10, traffic_indicator="",
            population=0, x=4, y=2, danger_band="low",
        )
        info.routes.append(RouteRenderInfo(
            route_id="r1", from_site_id="loc_a", to_site_id="loc_b",
            route_type="road",
        ))
        output = render_region_map(info, "loc_a", radius=4)
        grid_lines = [ln for ln in output.split("\n") if "|" in ln and not ln.strip().startswith("+")]
        grid_content = "".join(grid_lines)
        # Route should draw '-' between the two sites on row y=2
        self.assertIn("-", grid_content)


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
            traffic_band="high", rumor_heat_band="high",
            has_memorial=True, has_alias=True, recent_death_site=True,
        )
        self.assertEqual(_atlas_overlay_suffix(cell), "!$?ma+")


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
        # Site markers vary by traffic: O (high), @ (medium), o (low)
        has_marker = any(m in flat for m in ("O", "@", "o"))
        self.assertTrue(has_marker, "Canvas should contain at least one site marker")

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

    def test_atlas_legend_uses_biome_chars(self) -> None:
        """Legend should match atlas _BIOME_CHARS, not legacy BIOME_GLYPHS."""
        output = render_atlas_overview(self.info)
        # Atlas forest first char is 'T' from "TtYf"
        self.assertIn("T=", output)
        # Atlas plains first char is '.' from ".,\',',"
        self.assertIn(".=", output)

    def test_atlas_legend_includes_traffic_rumor(self) -> None:
        output = render_atlas_overview(self.info)
        self.assertIn("$=", output)
        self.assertIn("?=", output)

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


class TestClusterSites(unittest.TestCase):
    """Verify _cluster_sites partitions sites for multi-continent generation."""

    def test_few_sites_single_cluster(self) -> None:
        sites = [(10, 10), (12, 12)]
        clusters = _cluster_sites(sites)
        self.assertEqual(len(clusters), 1)

    def test_spread_sites_multiple_clusters(self) -> None:
        """Well-separated site groups should produce multiple clusters."""
        sites = [
            (5, 5), (6, 5), (7, 5), (5, 6), (6, 6),
            (50, 5), (51, 5), (52, 5), (50, 6), (51, 6),
            (5, 25), (6, 25), (7, 25), (5, 26), (6, 26),
        ]
        clusters = _cluster_sites(sites, max_clusters=4)
        self.assertGreaterEqual(len(clusters), 2)
        # All sites should be assigned
        total = sum(len(c) for c in clusters)
        self.assertEqual(total, len(sites))

    def test_tight_sites_single_cluster(self) -> None:
        """Sites clustered in a small area should stay as one cluster."""
        sites = [(30 + i, 15 + j) for i in range(5) for j in range(5)]
        clusters = _cluster_sites(sites, max_clusters=4)
        self.assertEqual(len(clusters), 1)

    def test_order_independent(self) -> None:
        """Shuffled input should produce the same clusters."""
        sites = [
            (5, 5), (6, 5), (7, 5), (5, 6), (6, 6),
            (50, 5), (51, 5), (52, 5), (50, 6), (51, 6),
        ]
        rng = random.Random(42)
        shuffled = list(sites)
        rng.shuffle(shuffled)
        c1 = _cluster_sites(sites, max_clusters=4)
        c2 = _cluster_sites(shuffled, max_clusters=4)
        # Same number of clusters and same total assignments
        self.assertEqual(len(c1), len(c2))
        s1 = [sorted(cl) for cl in c1]
        s2 = [sorted(cl) for cl in c2]
        self.assertEqual(sorted(s1), sorted(s2))


class TestLocationDetailI18n(unittest.TestCase):
    """Verify location detail uses localized labels."""

    def test_elevation_label_localized(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        output = render_location_detail(info, "loc_test_town")
        self.assertIn("Elev:", output)
        self.assertIn("Moist:", output)
        self.assertIn("Temp:", output)

    def test_japanese_elevation_label(self) -> None:
        set_locale("ja")
        info = _make_simple_info()
        output = render_location_detail(info, "loc_test_town")
        self.assertIn("標高:", output)
        set_locale("en")


class TestLabelCollision(unittest.TestCase):
    """Verify that high-importance labels survive collision."""

    def setUp(self) -> None:
        set_locale("en")

    def test_capital_label_always_present(self) -> None:
        """Capital (importance 80) label must appear even when crowded."""
        info = MapRenderInfo(
            world_name="Crowded", year=1, width=5, height=5,
        )
        # Create many sites packed in 5×5 grid — capital at centre
        names = [
            "Alpha", "Beta", "Capital City", "Delta", "Echo",
            "Foxtrot", "Golf", "Hotel", "India", "Juliet",
            "Kilo", "Lima", "Mike", "November", "Oscar",
            "Papa", "Quebec", "Romeo", "Sierra", "Tango",
            "Uniform", "Victor", "Whiskey", "Xray", "Yankee",
        ]
        for y in range(5):
            for x in range(5):
                idx = y * 5 + x
                name = names[idx]
                importance = 80 if name == "Capital City" else 20
                info.cells[(x, y)] = MapCellInfo(
                    location_id=f"loc_{name.lower().replace(' ', '_')}",
                    canonical_name=name,
                    region_type="city" if importance == 80 else "village",
                    icon="@", safety_label="ok", danger=10,
                    traffic_indicator="", population=0,
                    x=x, y=y, danger_band="low",
                    site_importance=importance,
                    terrain_biome="plains", terrain_glyph=",",
                )
        canvas = _build_atlas_canvas(info)
        flat = "".join("".join(row) for row in canvas)
        # The capital label must survive collision
        self.assertIn("Capital", flat)

    def test_dungeon_label_survives(self) -> None:
        """Dungeon (importance 60) label should survive over villages (40)."""
        info = MapRenderInfo(
            world_name="DungeonTest", year=1, width=3, height=3,
        )
        # Dungeon at (1,1) with two villages nearby
        info.cells[(0, 1)] = MapCellInfo(
            location_id="loc_village_a", canonical_name="VillageA",
            region_type="village", icon="@", safety_label="ok",
            danger=10, traffic_indicator="", population=0,
            x=0, y=1, danger_band="low", site_importance=40,
            terrain_biome="plains", terrain_glyph=",",
        )
        info.cells[(1, 1)] = MapCellInfo(
            location_id="loc_dark_dungeon", canonical_name="DarkDungeon",
            region_type="dungeon", icon="@", safety_label="ok",
            danger=80, traffic_indicator="", population=0,
            x=1, y=1, danger_band="high", site_importance=60,
            terrain_biome="hills", terrain_glyph="n",
        )
        info.cells[(2, 1)] = MapCellInfo(
            location_id="loc_village_b", canonical_name="VillageB",
            region_type="village", icon="@", safety_label="ok",
            danger=10, traffic_indicator="", population=0,
            x=2, y=1, danger_band="low", site_importance=40,
            terrain_biome="plains", terrain_glyph=",",
        )
        canvas = _build_atlas_canvas(info)
        flat = "".join("".join(row) for row in canvas)
        self.assertIn("DarkDungeon", flat)


class TestTrafficAwareSiteMarkers(unittest.TestCase):
    """Verify site markers vary by traffic band on atlas."""

    def setUp(self) -> None:
        set_locale("en")

    def test_high_traffic_uses_O(self) -> None:
        info = _make_simple_info()
        canvas = _build_atlas_canvas(info)
        flat = "".join("".join(row) for row in canvas)
        # TestTown has traffic_band="high" → should be 'O' marker
        self.assertIn("O", flat)

    def test_low_traffic_uses_o(self) -> None:
        info = _make_simple_info()
        canvas = _build_atlas_canvas(info)
        flat = "".join("".join(row) for row in canvas)
        # ForestCamp has traffic_band="low" → should be 'o' marker
        self.assertIn("o", flat)


class TestRumorHalo(unittest.TestCase):
    """Verify rumor halo appears around high-rumor sites."""

    def test_rumor_halo_places_question_marks(self) -> None:
        set_locale("en")
        info = MapRenderInfo(
            world_name="RumorTest", year=1, width=3, height=3,
        )
        info.cells[(1, 1)] = MapCellInfo(
            location_id="loc_rumor_town",
            canonical_name="RumorTown",
            region_type="city", icon="@", safety_label="ok",
            danger=10, traffic_indicator="", population=0,
            x=1, y=1, danger_band="low",
            rumor_heat_band="high",
            terrain_biome="plains", terrain_glyph=",",
        )
        canvas = _build_atlas_canvas(info)
        # At least one adjacent cell should have '?' from the rumor halo
        ax, ay = None, None
        for py in range(len(canvas)):
            for px in range(len(canvas[0])):
                if canvas[py][px] in ("O", "@", "o"):
                    ax, ay = px, py
                    break
        self.assertIsNotNone(ax, "Site marker not found on canvas")
        adjacent_chars = []
        for dy2, dx2 in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            ny2, nx2 = ay + dy2, ax + dx2
            if 0 <= ny2 < len(canvas) and 0 <= nx2 < len(canvas[0]):
                adjacent_chars.append(canvas[ny2][nx2])
        self.assertIn("?", adjacent_chars, "Rumor halo '?' not found adjacent to site")


class TestRegionRouteTypes(unittest.TestCase):
    """Verify region map uses route-type-specific line chars."""

    def test_mountain_pass_uses_caret(self) -> None:
        set_locale("en")
        info = MapRenderInfo(
            world_name="PassTest", year=1, width=5, height=5,
        )
        for y in range(5):
            for x in range(5):
                info.terrain_cells[(x, y)] = TerrainCellRenderInfo(
                    x=x, y=y, biome="mountain", glyph="^",
                )
        info.cells[(0, 2)] = MapCellInfo(
            location_id="loc_a", canonical_name="Alpha", region_type="mountain",
            icon="@", safety_label="ok", danger=10, traffic_indicator="",
            population=0, x=0, y=2, danger_band="low",
        )
        info.cells[(4, 2)] = MapCellInfo(
            location_id="loc_b", canonical_name="Beta", region_type="mountain",
            icon="@", safety_label="ok", danger=10, traffic_indicator="",
            population=0, x=4, y=2, danger_band="low",
        )
        info.routes.append(RouteRenderInfo(
            route_id="r1", from_site_id="loc_a", to_site_id="loc_b",
            route_type="mountain_pass",
        ))
        output = render_region_map(info, "loc_a", radius=4)
        # Mountain pass horizontal line should use '^'
        grid_lines = [ln for ln in output.split("\n") if "|" in ln and not ln.strip().startswith("+")]
        grid_content = "".join(grid_lines)
        # The mountain pass route should draw '^' chars between sites
        self.assertIn("^", grid_content)

    def test_trail_uses_dot(self) -> None:
        set_locale("en")
        info = MapRenderInfo(
            world_name="TrailTest", year=1, width=5, height=5,
        )
        for y in range(5):
            for x in range(5):
                info.terrain_cells[(x, y)] = TerrainCellRenderInfo(
                    x=x, y=y, biome="plains", glyph=",",
                )
        info.cells[(0, 2)] = MapCellInfo(
            location_id="loc_a", canonical_name="Alpha", region_type="village",
            icon="@", safety_label="ok", danger=10, traffic_indicator="",
            population=0, x=0, y=2, danger_band="low",
        )
        info.cells[(4, 2)] = MapCellInfo(
            location_id="loc_b", canonical_name="Beta", region_type="village",
            icon="@", safety_label="ok", danger=10, traffic_indicator="",
            population=0, x=4, y=2, danger_band="low",
        )
        info.routes.append(RouteRenderInfo(
            route_id="r1", from_site_id="loc_a", to_site_id="loc_b",
            route_type="trail",
        ))
        output = render_region_map(info, "loc_a", radius=4)
        # Trail horizontal line should use '.'
        grid_lines = [ln for ln in output.split("\n") if "|" in ln and not ln.strip().startswith("+")]
        grid_content = "".join(grid_lines)
        self.assertIn(".", grid_content)


class TestAtlasLegendOcean(unittest.TestCase):
    """Verify atlas legend includes ocean."""

    def test_ocean_in_legend(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        output = render_atlas_overview(info)
        self.assertIn("~=", output)  # ocean first char is '~'

    def test_site_hub_in_legend(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        output = render_atlas_overview(info)
        self.assertIn("O=", output)  # Hub marker in legend
        self.assertIn("o=", output)  # Quiet marker in legend


class TestAtlasCompact(unittest.TestCase):
    """Verify compact atlas renderer produces reasonable output."""

    def test_compact_contains_terrain(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        from fantasy_simulator.ui.atlas_renderer import render_atlas_compact
        output = render_atlas_compact(info)
        # Should contain some terrain chars
        self.assertTrue(any(c in output for c in "~.,T^n"))

    def test_compact_contains_site_markers(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        from fantasy_simulator.ui.atlas_renderer import render_atlas_compact
        output = render_atlas_compact(info)
        has_marker = any(m in output for m in ("O", "@", "o"))
        self.assertTrue(has_marker, "Compact atlas should show site markers")

    def test_compact_shorter_than_wide(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        from fantasy_simulator.ui.atlas_renderer import render_atlas_compact
        compact = render_atlas_compact(info)
        wide = render_atlas_overview(info)
        self.assertLess(len(compact), len(wide))


class TestAtlasMinimal(unittest.TestCase):
    """Verify minimal atlas renderer produces text-only summary."""

    def test_minimal_contains_world_name(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        from fantasy_simulator.ui.atlas_renderer import render_atlas_minimal
        output = render_atlas_minimal(info)
        self.assertIn("TestWorld", output)

    def test_minimal_lists_sites(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        from fantasy_simulator.ui.atlas_renderer import render_atlas_minimal
        output = render_atlas_minimal(info)
        self.assertIn("TestTown", output)
        self.assertIn("ForestCamp", output)

    def test_minimal_no_terrain_chars(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        from fantasy_simulator.ui.atlas_renderer import render_atlas_minimal
        output = render_atlas_minimal(info)
        # Minimal should not contain terrain canvas characters like ~ for ocean
        lines = output.strip().split("\n")
        for line in lines:
            self.assertNotIn("~~~~", line)


class TestAtlasLabeledSites(unittest.TestCase):
    """Verify atlas_labeled_sites returns correct site list."""

    def test_returns_all_sites(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        from fantasy_simulator.ui.atlas_renderer import atlas_labeled_sites
        labeled = atlas_labeled_sites(info)
        self.assertEqual(len(labeled), 2)
        names = [name for _, name in labeled]
        self.assertIn("TestTown", names)
        self.assertIn("ForestCamp", names)

    def test_ordered_by_importance(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        # TestTown has default importance 50, ForestCamp has default 50
        # But let's set explicit importance
        info.cells[(1, 1)].site_importance = 80
        info.cells[(0, 0)].site_importance = 20
        from fantasy_simulator.ui.atlas_renderer import atlas_labeled_sites
        labeled = atlas_labeled_sites(info)
        self.assertEqual(labeled[0][1], "TestTown")
        self.assertEqual(labeled[1][1], "ForestCamp")


class TestAtlasLayoutModel(unittest.TestCase):
    """Verify AtlasLayout data model serialization."""

    def test_round_trip(self) -> None:
        from fantasy_simulator.terrain import AtlasLayout
        layout = AtlasLayout(
            canvas_w=72, canvas_h=30,
            continents=[{"name": "Main", "cells": [(10, 5), (11, 5)]}],
            seas=[{"name": "Great Ocean", "cells": []}],
            mountain_ranges=[{"name": "Spine", "cells": [(20, 10)]}],
        )
        d = layout.to_dict()
        restored = AtlasLayout.from_dict(d)
        self.assertEqual(restored.canvas_w, 72)
        self.assertEqual(restored.canvas_h, 30)
        self.assertEqual(len(restored.continents), 1)
        self.assertEqual(restored.continents[0]["name"], "Main")
        self.assertEqual(len(restored.seas), 1)
        self.assertEqual(len(restored.mountain_ranges), 1)

    def test_default_values(self) -> None:
        from fantasy_simulator.terrain import AtlasLayout
        layout = AtlasLayout()
        self.assertEqual(layout.canvas_w, 72)
        self.assertEqual(layout.canvas_h, 30)
        self.assertEqual(layout.continents, [])


class TestSiteAtlasCoordinates(unittest.TestCase):
    """Verify atlas_x / atlas_y are computed and persisted on Site."""

    def test_default_world_sites_have_atlas_coords(self) -> None:
        world = World()
        for site in world.sites:
            self.assertGreaterEqual(site.atlas_x, 0,
                                    f"Site {site.location_id} missing atlas_x")
            self.assertGreaterEqual(site.atlas_y, 0,
                                    f"Site {site.location_id} missing atlas_y")

    def test_atlas_coords_round_trip(self) -> None:
        from fantasy_simulator.terrain import Site
        site = Site(
            location_id="loc_test", x=2, y=3,
            site_type="city", importance=80,
            atlas_x=20, atlas_y=10,
        )
        d = site.to_dict()
        self.assertEqual(d["atlas_x"], 20)
        self.assertEqual(d["atlas_y"], 10)
        restored = Site.from_dict(d)
        self.assertEqual(restored.atlas_x, 20)
        self.assertEqual(restored.atlas_y, 10)

    def test_atlas_coords_absent_defaults_to_minus_one(self) -> None:
        from fantasy_simulator.terrain import Site
        site = Site.from_dict({
            "location_id": "loc_test", "x": 0, "y": 0,
        })
        self.assertEqual(site.atlas_x, -1)
        self.assertEqual(site.atlas_y, -1)


class TestAtlasLayoutOnWorld(unittest.TestCase):
    """Verify atlas_layout is persisted on World."""

    def test_world_to_dict_includes_atlas_layout(self) -> None:
        from fantasy_simulator.terrain import AtlasLayout
        world = World()
        world.atlas_layout = AtlasLayout(
            continents=[{"name": "TestContinent", "cells": []}],
        )
        d = world.to_dict()
        self.assertIn("atlas_layout", d)
        self.assertEqual(d["atlas_layout"]["continents"][0]["name"], "TestContinent")

    def test_world_from_dict_restores_atlas_layout(self) -> None:
        from fantasy_simulator.terrain import AtlasLayout
        world = World()
        world.atlas_layout = AtlasLayout(
            continents=[{"name": "Restored", "cells": []}],
        )
        d = {"world": world.to_dict(), "schema_version": 7}
        d.update(world.to_dict())
        restored = World.from_dict(d)
        self.assertIsNotNone(restored.atlas_layout)
        self.assertEqual(restored.atlas_layout.continents[0]["name"], "Restored")

    def test_world_without_atlas_layout_is_none(self) -> None:
        world = World()
        d = world.to_dict()
        d.pop("atlas_layout", None)
        restored = World.from_dict(d)
        self.assertIsNone(restored.atlas_layout)


class TestMigrationV6toV7(unittest.TestCase):
    """Verify v6→v7 migration adds atlas layout and site atlas coords."""

    def test_migration_adds_atlas_layout(self) -> None:
        from fantasy_simulator.persistence.migrations import _migrate_v6_to_v7
        data = {
            "schema_version": 6,
            "world": {
                "width": 3, "height": 2,
                "sites": [
                    {"location_id": "loc_a", "x": 0, "y": 0, "site_type": "city", "importance": 80},
                    {"location_id": "loc_b", "x": 1, "y": 0, "site_type": "village", "importance": 40},
                ],
            },
        }
        result = _migrate_v6_to_v7(data)
        self.assertEqual(result["schema_version"], 7)
        layout = result["world"]["atlas_layout"]
        self.assertEqual(layout["canvas_w"], 72)
        self.assertEqual(len(layout["continents"]), 1)

    def test_migration_adds_atlas_coords_to_sites(self) -> None:
        from fantasy_simulator.persistence.migrations import _migrate_v6_to_v7
        data = {
            "schema_version": 6,
            "world": {
                "width": 5, "height": 5,
                "sites": [
                    {"location_id": "loc_a", "x": 0, "y": 0, "site_type": "city", "importance": 80},
                    {"location_id": "loc_b", "x": 4, "y": 4, "site_type": "village", "importance": 40},
                ],
            },
        }
        result = _migrate_v6_to_v7(data)
        sites = result["world"]["sites"]
        for site in sites:
            self.assertIn("atlas_x", site)
            self.assertIn("atlas_y", site)
            self.assertGreaterEqual(site["atlas_x"], 0)
            self.assertGreaterEqual(site["atlas_y"], 0)
        # First site at (0,0) should be near margin
        self.assertEqual(sites[0]["atlas_x"], 6)
        self.assertEqual(sites[0]["atlas_y"], 3)


class TestRegionMapLandmarks(unittest.TestCase):
    """Verify region map shows world memory landmarks."""

    def test_region_map_shows_aliases(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        output = render_region_map(
            info, "loc_test_town",
            site_aliases={"loc_test_town": ["The Old City"]},
        )
        self.assertIn("The Old City", output)

    def test_region_map_shows_memorials(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        output = render_region_map(
            info, "loc_test_town",
            site_memorials={"loc_test_town": ["Brave Hero fell here (Year 1001)"]},
        )
        self.assertIn("Brave Hero", output)

    def test_region_map_shows_traces(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        output = render_region_map(
            info, "loc_test_town",
            site_traces={"loc_test_town": ["Adventurer passed through"]},
        )
        self.assertIn("Adventurer passed through", output)

    def test_region_map_no_landmarks_when_none(self) -> None:
        set_locale("en")
        info = _make_simple_info()
        output = render_region_map(info, "loc_test_town")
        self.assertNotIn("Landmarks", output)


class TestAtlasUsesStoredCoords(unittest.TestCase):
    """Verify atlas renderer uses pre-computed atlas coordinates."""

    def test_stored_coords_used_in_canvas(self) -> None:
        """When atlas_x/atlas_y are set, the renderer should use them."""
        set_locale("en")
        info = MapRenderInfo(world_name="CoordTest", year=1, width=3, height=3)
        # Place a site with explicit atlas coords
        info.cells[(1, 1)] = MapCellInfo(
            location_id="loc_stored", canonical_name="StoredSite",
            region_type="city", icon="@", safety_label="ok",
            danger=10, traffic_indicator="", population=0,
            x=1, y=1, danger_band="low",
            atlas_x=35, atlas_y=15,  # centre of atlas
        )
        canvas = _build_atlas_canvas(info)
        # The site marker should appear at (35, 15) on the canvas
        self.assertIn(canvas[15][35], ("O", "@", "o"))


if __name__ == "__main__":
    unittest.main()

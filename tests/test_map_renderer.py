"""Tests for ui.map_renderer — MapCellInfo, MapRenderInfo, build_map_info, render_map_ascii.

These tests verify:
- Data extraction from World produces correct intermediate representations.
- The ASCII renderer generates output identical to the legacy world.render_map().
- Edge cases (empty grid, highlight by id/name, population count, dead chars,
  locale switching) are handled correctly.
- The intermediate representation is domain-independent and testable in isolation.
"""

from __future__ import annotations

import re
import unicodedata
import unittest

from fantasy_simulator.character import Character
from fantasy_simulator.i18n import set_locale
from fantasy_simulator.ui.map_renderer import (
    MapCellInfo,
    MapRenderInfo,
    build_map_info,
    render_map_ascii,
)
from fantasy_simulator.world import World


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _display_width(text: str) -> int:
    """Terminal column width — test-local helper matching production logic."""
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("F", "W") else 1
    return width


# ---------------------------------------------------------------------------
# build_map_info — data extraction from World
# ---------------------------------------------------------------------------

class TestBuildMapInfo(unittest.TestCase):
    """Verify that build_map_info extracts the correct snapshot from World."""

    def setUp(self) -> None:
        set_locale("en")
        self.world = World()

    def test_extracts_all_grid_cells(self) -> None:
        """Every cell in the world grid must appear in MapRenderInfo.cells."""
        info = build_map_info(self.world)
        self.assertEqual(len(info.cells), len(self.world.grid))
        for coord in self.world.grid:
            self.assertIn(coord, info.cells)

    def test_world_metadata_matches(self) -> None:
        """Top-level fields must match the source World."""
        info = build_map_info(self.world)
        self.assertEqual(info.world_name, self.world.name)
        self.assertEqual(info.year, self.world.year)
        self.assertEqual(info.width, self.world.width)
        self.assertEqual(info.height, self.world.height)

    def test_cell_fields_match_location_state(self) -> None:
        """Every MapCellInfo field must agree with the underlying LocationState."""
        info = build_map_info(self.world)
        for (x, y), cell in info.cells.items():
            loc = self.world.grid[(x, y)]
            self.assertEqual(cell.location_id, loc.id)
            self.assertEqual(cell.canonical_name, loc.canonical_name)
            self.assertEqual(cell.region_type, loc.region_type)
            self.assertEqual(cell.icon, loc.icon, f"Icon mismatch at ({x},{y})")
            self.assertEqual(cell.safety_label, loc.safety_label)
            self.assertEqual(cell.danger, loc.danger)
            self.assertEqual(cell.traffic_indicator, loc.traffic_indicator)
            self.assertEqual(cell.x, x)
            self.assertEqual(cell.y, y)
            self.assertFalse(cell.highlighted)
            # Extended fields for future renderers
            self.assertEqual(cell.prosperity, loc.prosperity)
            self.assertEqual(cell.prosperity_label, loc.prosperity_label)
            self.assertEqual(cell.mood, loc.mood)
            self.assertEqual(cell.mood_label, loc.mood_label)
            self.assertEqual(cell.rumor_heat, loc.rumor_heat)
            self.assertEqual(cell.road_condition, loc.road_condition)

    def test_population_counts_alive_characters_only(self) -> None:
        """Population must count only alive characters at a location."""
        loc_id = "loc_aethoria_capital"
        alive_char = Character("Alice", 25, "Female", "Human", "Warrior", location_id=loc_id)
        dead_char = Character("Bob", 70, "Male", "Human", "Warrior", location_id=loc_id)
        dead_char.alive = False
        self.world.add_character(alive_char)
        self.world.add_character(dead_char)

        info = build_map_info(self.world)
        capital_cell = None
        for cell in info.cells.values():
            if cell.location_id == loc_id:
                capital_cell = cell
                break
        self.assertIsNotNone(capital_cell)
        # get_characters_at_location only returns alive characters
        self.assertEqual(capital_cell.population, 1)

    def test_highlight_by_location_id(self) -> None:
        """Highlighting by location_id must set icon='*' and highlighted=True."""
        target_id = "loc_aethoria_capital"
        info = build_map_info(self.world, highlight_location=target_id)
        for cell in info.cells.values():
            if cell.location_id == target_id:
                self.assertEqual(cell.icon, "*")
                self.assertTrue(cell.highlighted)
            else:
                self.assertNotEqual(cell.icon, "*")
                self.assertFalse(cell.highlighted)

    def test_highlight_by_canonical_name(self) -> None:
        """Highlighting by name must also work, for backward compat."""
        target_name = "Aethoria Capital"
        info = build_map_info(self.world, highlight_location=target_name)
        highlighted = [c for c in info.cells.values() if c.highlighted]
        self.assertEqual(len(highlighted), 1)
        self.assertEqual(highlighted[0].canonical_name, target_name)
        self.assertEqual(highlighted[0].icon, "*")

    def test_no_highlight_when_none(self) -> None:
        """When highlight_location is None, nothing is highlighted."""
        info = build_map_info(self.world, highlight_location=None)
        for cell in info.cells.values():
            self.assertFalse(cell.highlighted)
            self.assertNotEqual(cell.icon, "*")

    def test_multiple_characters_increase_population(self) -> None:
        """Adding more characters at one location increases that cell's population."""
        loc_id = "loc_thornwood"
        for i in range(5):
            c = Character(f"Char{i}", 20 + i, "Male", "Elf", "Ranger", location_id=loc_id)
            self.world.add_character(c)

        info = build_map_info(self.world)
        for cell in info.cells.values():
            if cell.location_id == loc_id:
                self.assertEqual(cell.population, 5)
                break
        else:
            self.fail(f"No cell found for {loc_id}")


# ---------------------------------------------------------------------------
# render_map_ascii — ASCII rendering from MapRenderInfo
# ---------------------------------------------------------------------------

class TestRenderMapAscii(unittest.TestCase):
    """Verify the ASCII renderer produces correct, stable output."""

    def setUp(self) -> None:
        set_locale("en")
        self.world = World()

    def test_output_matches_legacy_world_render_map(self) -> None:
        """The new pipeline must produce output identical to the old inline method.

        This is the *key* backward-compat guarantee.  We build the
        intermediate representation and render it, then compare to what
        world.render_map() (which itself now delegates) returns.
        """
        info = build_map_info(self.world)
        new_output = render_map_ascii(info)
        legacy_output = self.world.render_map()
        self.assertEqual(new_output, legacy_output)

    def test_output_matches_legacy_with_highlight(self) -> None:
        """Highlighted rendering must also match."""
        hl = "loc_aethoria_capital"
        info = build_map_info(self.world, highlight_location=hl)
        new_output = render_map_ascii(info)
        legacy_output = self.world.render_map(highlight_location=hl)
        self.assertEqual(new_output, legacy_output)

    def test_header_contains_world_name_and_year(self) -> None:
        """The first content row should display the world name and year."""
        info = build_map_info(self.world)
        output = render_map_ascii(info)
        self.assertIn("Aethoria", output)
        self.assertIn("1000", output)

    def test_all_location_names_appear(self) -> None:
        """Every location canonical_name must appear somewhere in the output."""
        info = build_map_info(self.world)
        output = render_map_ascii(info)
        for cell in info.cells.values():
            self.assertIn(
                cell.canonical_name, output,
                f"{cell.canonical_name!r} missing from rendered map",
            )

    def test_english_lines_have_consistent_display_width(self) -> None:
        """Every content line within a row should have the same terminal width."""
        set_locale("en")
        info = build_map_info(self.world)
        output = render_map_ascii(info)
        lines = output.splitlines()
        # Borders and content lines should all be the same width.
        border_width = _display_width(lines[0])
        for i, line in enumerate(lines):
            w = _display_width(line)
            self.assertEqual(
                w, border_width,
                f"Line {i} width={w} differs from border width={border_width}: {line!r}",
            )

    def test_japanese_lines_have_consistent_display_width(self) -> None:
        """Width stability must also hold in Japanese locale."""
        set_locale("ja")
        info = build_map_info(self.world)
        output = render_map_ascii(info)
        lines = output.splitlines()
        border_width = _display_width(lines[0])
        for i, line in enumerate(lines):
            w = _display_width(line)
            self.assertEqual(
                w, border_width,
                f"Line {i} width={w} differs from border width={border_width}",
            )
        set_locale("en")

    def test_border_structure(self) -> None:
        """Output must start/end with border lines matching +---...---+."""
        info = build_map_info(self.world)
        output = render_map_ascii(info)
        lines = output.splitlines()
        border_re = re.compile(r"^\s+\+\-+\+$")
        self.assertRegex(lines[0], border_re)
        self.assertRegex(lines[-1], border_re)

    def test_six_data_rows_per_grid_row(self) -> None:
        """Each grid row produces 6 data lines (name, type, safety, danger,
        traffic, population) plus one border."""
        info = build_map_info(self.world)
        output = render_map_ascii(info)
        lines = output.splitlines()
        # Layout: top-border, header, border, then for each of 5 rows:
        # 6 data lines + border = 7 lines.
        expected = 3 + info.height * 7
        self.assertEqual(len(lines), expected)


# ---------------------------------------------------------------------------
# MapRenderInfo isolation — can be built and rendered without World
# ---------------------------------------------------------------------------

class TestMapRenderInfoIsolation(unittest.TestCase):
    """Verify that the intermediate representation works independently."""

    def setUp(self) -> None:
        set_locale("en")

    def test_render_empty_grid(self) -> None:
        """A 0×0 grid produces header/borders but no cell rows."""
        info = MapRenderInfo(world_name="Empty", year=1, width=0, height=0)
        output = render_map_ascii(info)
        lines = output.splitlines()
        # With width=0 the inner area has -1 columns — header is truncated.
        # The important thing is no crash and structure is valid.
        self.assertGreaterEqual(len(lines), 3)
        # Borders are the first and last lines
        self.assertTrue(lines[0].strip().startswith("+"))
        self.assertTrue(lines[-1].strip().startswith("+"))

    def test_render_single_cell(self) -> None:
        """A 1×1 grid with a manually built cell renders correctly.

        With cell_width=20 the header may be truncated, but the cell
        data itself must appear.
        """
        cell = MapCellInfo(
            location_id="test_loc",
            canonical_name="Test Town",
            region_type="village",
            icon="V",
            safety_label="Peaceful",
            danger=5,
            traffic_indicator="+",
            population=3,
            x=0,
            y=0,
        )
        info = MapRenderInfo(
            world_name="TestWorld",
            year=2000,
            width=1,
            height=1,
            cells={(0, 0): cell},
        )
        output = render_map_ascii(info)
        # Cell data lines must appear
        self.assertIn("Test Town", output)
        self.assertIn("Peaceful", output)
        self.assertIn("Pop: 3", output)
        # Header might be truncated at 20 cols, but year/title prefix exists
        self.assertIn("WORLD MAP", output)
        # Structure: 3 header lines + 1 row × 7 (6 data + border) = 10
        self.assertEqual(len(output.splitlines()), 10)

    def test_render_with_missing_cell_shows_placeholder(self) -> None:
        """A grid position with no cell produces '?' placeholder."""
        info = MapRenderInfo(
            world_name="Sparse",
            year=1,
            width=2,
            height=1,
            cells={
                (0, 0): MapCellInfo(
                    location_id="a", canonical_name="A", region_type="city",
                    icon="C", safety_label="Tense", danger=30,
                    traffic_indicator="++", population=10, x=0, y=0,
                ),
                # (1, 0) intentionally missing
            },
        )
        output = render_map_ascii(info)
        self.assertIn("?", output)
        self.assertIn("A", output)

    def test_highlighted_cell_icon(self) -> None:
        """A cell with highlighted=True should have been given icon='*'
        by build_map_info; the renderer just displays whatever icon it gets."""
        cell = MapCellInfo(
            location_id="hl", canonical_name="Highlighted",
            region_type="forest", icon="*",
            safety_label="Dangerous", danger=80,
            traffic_indicator="+", population=0,
            x=0, y=0, highlighted=True,
        )
        info = MapRenderInfo(
            world_name="W", year=1, width=1, height=1,
            cells={(0, 0): cell},
        )
        output = render_map_ascii(info)
        # The '*' icon should appear in the name row
        self.assertIn("* Highlighted", output)

    def test_long_japanese_name_truncated_to_cell_width(self) -> None:
        """A canonical_name wider than cell_width (20) is truncated with '...'
        and the resulting line still fits exactly within the cell boundary."""
        set_locale("ja")
        # 12 full-width chars = 24 display columns > cell_width of 20
        long_name = "非常に長い城の名前の詳細説明"
        cell = MapCellInfo(
            location_id="jp", canonical_name=long_name,
            region_type="city", icon="C",
            safety_label="安全", danger=10,
            traffic_indicator="+", population=2,
            x=0, y=0,
        )
        info = MapRenderInfo(
            world_name="テスト", year=1, width=1, height=1,
            cells={(0, 0): cell},
        )
        output = render_map_ascii(info)
        lines = output.splitlines()
        # Every content line must have the same display width
        border_width = _display_width(lines[0])
        for i, line in enumerate(lines):
            w = _display_width(line)
            self.assertEqual(
                w, border_width,
                f"Line {i} width={w} ≠ border width={border_width}: {line!r}",
            )
        # The name must be truncated (original doesn't fully appear)
        name_line = lines[3]  # first content row after header
        self.assertIn("...", name_line)
        set_locale("en")

    def test_extended_fields_have_defaults(self) -> None:
        """MapCellInfo extended fields default to safe values even when
        constructed with only the required fields."""
        cell = MapCellInfo(
            location_id="x", canonical_name="X", region_type="plains",
            icon="P", safety_label="Peaceful", danger=0,
            traffic_indicator="-", population=0, x=0, y=0,
        )
        self.assertEqual(cell.prosperity, 50)
        self.assertEqual(cell.mood, 50)
        self.assertEqual(cell.rumor_heat, 0)
        self.assertEqual(cell.road_condition, 50)
        self.assertEqual(cell.prosperity_label, "")
        self.assertEqual(cell.mood_label, "")


# ---------------------------------------------------------------------------
# Backward compat — world.render_map() delegates correctly
# ---------------------------------------------------------------------------

class TestWorldRenderMapDelegation(unittest.TestCase):
    """world.render_map() must continue to work exactly as before."""

    def setUp(self) -> None:
        set_locale("en")
        self.world = World()

    def test_render_map_returns_string(self) -> None:
        result = self.world.render_map()
        self.assertIsInstance(result, str)
        self.assertGreater(len(result), 0)

    def test_render_map_with_character_shows_population(self) -> None:
        """Adding a character should increase the population count in its cell."""
        loc_id = "loc_aethoria_capital"
        char = Character("TestHero", 25, "Male", "Human", "Warrior", location_id=loc_id)
        self.world.add_character(char)
        output = self.world.render_map()
        # The pop line for the capital should show 1
        self.assertIn("Pop: 1", output)


if __name__ == "__main__":
    unittest.main()

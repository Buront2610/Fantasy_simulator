"""Tests for screens module — importability and key helpers."""

from __future__ import annotations

import io
import re
import unittest
import unicodedata
from contextlib import redirect_stdout
from unittest.mock import patch

from character import Character
from i18n import set_locale
from world import World


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def _display_width(text: str) -> int:
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        width += 2 if unicodedata.east_asian_width(char) in ("F", "W") else 1
    return width


class TestScreensImport(unittest.TestCase):
    """Verify that screens module imports without errors."""

    def test_module_importable(self) -> None:
        import screens  # noqa: F401

    def test_public_screen_functions_exist(self) -> None:
        from screens import (
            screen_custom_simulation,
            screen_new_simulation,
            screen_world_lore,
        )
        self.assertTrue(callable(screen_new_simulation))
        self.assertTrue(callable(screen_custom_simulation))
        self.assertTrue(callable(screen_world_lore))

    def test_internal_helpers_exist(self) -> None:
        from screens import (
            _advance_simulation,
            _build_default_world,
            _load_simulation_snapshot,
            _run_simulation,
            _save_simulation_snapshot,
            _select_language,
            _show_results,
        )
        self.assertTrue(callable(_build_default_world))
        self.assertTrue(callable(_run_simulation))
        self.assertTrue(callable(_advance_simulation))
        self.assertTrue(callable(_show_results))
        self.assertTrue(callable(_save_simulation_snapshot))
        self.assertTrue(callable(_load_simulation_snapshot))
        self.assertTrue(callable(_select_language))


class TestBuildDefaultWorld(unittest.TestCase):
    """_build_default_world creates a properly populated world."""

    def setUp(self) -> None:
        set_locale("en")

    def test_default_character_count(self) -> None:
        from screens import _build_default_world
        world = _build_default_world()
        self.assertEqual(len(world.characters), 12)

    def test_custom_character_count(self) -> None:
        from screens import _build_default_world
        world = _build_default_world(num_characters=5)
        self.assertEqual(len(world.characters), 5)

    def test_characters_have_locations(self) -> None:
        from screens import _build_default_world
        world = _build_default_world(num_characters=4)
        for char in world.characters:
            self.assertTrue(len(char.location_id) > 0)


class TestMainEntryPoint(unittest.TestCase):
    """Verify that main.py still exports main()."""

    def test_main_function_callable(self) -> None:
        from main import main
        self.assertTrue(callable(main))


class TestRosterRendering(unittest.TestCase):
    def test_show_roster_keeps_header_and_rows_same_display_width_in_japanese(self) -> None:
        from screens import _show_roster

        set_locale("ja")
        world = World()
        world.add_character(
            Character(
                "勇者アレクサンドリアとても長い名前",
                25,
                "Female",
                "Human",
                "Warrior",
                location_id="loc_aethoria_capital",
            )
        )

        captured = io.StringIO()
        with patch("screens._pause", return_value=None):
            with redirect_stdout(captured):
                _show_roster(world)

        lines = [_ANSI_RE.sub("", line) for line in captured.getvalue().splitlines()]
        table_lines = [line for line in lines if "名前" in line or "人間 戦士" in line]

        self.assertEqual(len(table_lines), 2)
        widths = {_display_width(line) for line in table_lines}
        self.assertEqual(len(widths), 1)


if __name__ == "__main__":
    unittest.main()

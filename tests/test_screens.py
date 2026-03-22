"""Tests for screens module — importability and key helpers."""

from __future__ import annotations

import unittest

from i18n import set_locale


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


if __name__ == "__main__":
    unittest.main()

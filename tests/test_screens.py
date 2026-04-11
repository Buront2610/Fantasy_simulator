"""Tests for screens module — importability and key helpers."""

from __future__ import annotations

import io
import re
import unittest
import unicodedata
from contextlib import redirect_stdout
from types import SimpleNamespace

from fantasy_simulator.character import Character
from fantasy_simulator.i18n import set_locale
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


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
        import fantasy_simulator.ui.screens  # noqa: F401

    def test_public_screen_functions_exist(self) -> None:
        from fantasy_simulator.ui.screens import (
            screen_custom_simulation,
            screen_new_simulation,
            screen_world_lore,
        )
        self.assertTrue(callable(screen_new_simulation))
        self.assertTrue(callable(screen_custom_simulation))
        self.assertTrue(callable(screen_world_lore))

    def test_internal_helpers_exist(self) -> None:
        from fantasy_simulator.ui.screens import (
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
        from fantasy_simulator.ui.screens import _build_default_world
        world = _build_default_world()
        self.assertEqual(len(world.characters), 12)

    def test_custom_character_count(self) -> None:
        from fantasy_simulator.ui.screens import _build_default_world
        world = _build_default_world(num_characters=5)
        self.assertEqual(len(world.characters), 5)

    def test_characters_have_locations(self) -> None:
        from fantasy_simulator.ui.screens import _build_default_world
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
        from fantasy_simulator.ui.screens import _show_roster
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.input_backend import StdInputBackend
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

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

        # Build a context with a no-op pause
        class NoopInputBackend(StdInputBackend):
            def pause(self, message: str = "") -> None:
                pass
        ctx = UIContext(inp=NoopInputBackend(), out=PrintRenderBackend())

        captured = io.StringIO()
        with redirect_stdout(captured):
            _show_roster(world, ctx=ctx)

        lines = [_ANSI_RE.sub("", line) for line in captured.getvalue().splitlines()]
        table_lines = [line for line in lines if "名前" in line or "人間 戦士" in line]

        self.assertEqual(len(table_lines), 2)
        widths = {_display_width(line) for line in table_lines}
        self.assertEqual(len(widths), 1)


class TestMonthlyReportScreen(unittest.TestCase):
    def setUp(self) -> None:
        set_locale("en")

    def test_month_season_hint_contains_all_months(self) -> None:
        from fantasy_simulator.ui.screens import _month_season_hint

        hint = _month_season_hint(World(), 1000)
        self.assertIn("1: Embermorn (Winter)", hint)
        self.assertIn("12: Nightfrost (Winter)", hint)
        self.assertEqual(hint.count("("), 12)

    def test_show_monthly_report_uses_latest_completed_report_year(self) -> None:
        from fantasy_simulator.ui.screens import _show_monthly_report
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

        sim = SimpleNamespace(
            world=SimpleNamespace(
                year=1002,
                months_per_year_for_date=lambda year, month=1, day=1: 12,
                month_display_name_for_date=lambda year, month, day=1: World().month_display_name(month),
                season_for_date=lambda year, month, day=1: World().season_for_month(month),
            ),
            get_latest_completed_report_year=lambda: 1001,
            get_monthly_report=lambda year, month: f"REPORT {year}-{month}",
        )

        # Build a recording input backend that returns "1" for the month choice
        # and does nothing for pause
        class ScriptedInputBackend:
            def read_line(self, prompt: str = "") -> str:
                return "1"

            def read_menu_key(self, pairs, default=None):
                return pairs[0][0]

            def pause(self, message: str = "") -> None:
                pass

        ctx = UIContext(inp=ScriptedInputBackend(), out=PrintRenderBackend())

        captured = io.StringIO()
        with redirect_stdout(captured):
            _show_monthly_report(sim, ctx=ctx)

        text = _ANSI_RE.sub("", captured.getvalue())
        self.assertIn("Year: 1001", text)
        self.assertIn("1: Embermorn (Winter)", text)
        self.assertIn("REPORT 1001-1", text)


class TestAdventureAndLocationViews(unittest.TestCase):
    def test_adventure_summary_shows_party_marker_and_policy(self) -> None:
        from fantasy_simulator.adventure import AdventureRun, POLICY_TREASURE
        from fantasy_simulator.ui.screens import _show_adventure_summaries
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

        set_locale("en")
        world = World()
        leader = Character("Aldric", 25, "Male", "Human", "Warrior", location_id="loc_aethoria_capital")
        companion = Character("Lysara", 24, "Female", "Elf", "Mage", location_id="loc_aethoria_capital")
        world.add_character(leader)
        world.add_character(companion)
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=1)
        run = AdventureRun(
            character_id=leader.char_id,
            character_name=leader.name,
            origin="loc_aethoria_capital",
            destination="loc_thornwood",
            year_started=world.year,
            member_ids=[leader.char_id, companion.char_id],
            policy=POLICY_TREASURE,
        )
        world.add_adventure(run)

        class NoopInputBackend:
            def read_line(self, prompt: str = "") -> str:
                return ""

            def read_menu_key(self, pairs, default=None):
                return pairs[0][0]

            def pause(self, message: str = "") -> None:
                pass

        ctx = UIContext(inp=NoopInputBackend(), out=PrintRenderBackend())
        captured = io.StringIO()
        with redirect_stdout(captured):
            _show_adventure_summaries(sim, ctx=ctx)
        text = _ANSI_RE.sub("", captured.getvalue())

        self.assertIn("[Party]", text)
        self.assertIn("policy: Treasure Hunt", text)
        self.assertIn("Aldric & Lysara", text)

    def test_location_history_uses_i18n_count_tags(self) -> None:
        from fantasy_simulator.ui.screens import _show_location_history
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

        set_locale("en")
        world = World()
        loc = world.get_location_by_id("loc_aethoria_capital")
        assert loc is not None
        loc.aliases.append("The Crown City")
        loc.memorial_ids.append("m1")
        loc.live_traces.append({"year": 1001, "char_name": "Aldric", "text": "trace"})

        class PickFirstInputBackend:
            def __init__(self):
                self.calls = 0

            def read_line(self, prompt: str = "") -> str:
                self.calls += 1
                return "1" if self.calls == 1 else ""

            def read_menu_key(self, pairs, default=None):
                return pairs[0][0]

            def pause(self, message: str = "") -> None:
                pass

        ctx = UIContext(inp=PickFirstInputBackend(), out=PrintRenderBackend())
        captured = io.StringIO()
        with redirect_stdout(captured):
            _show_location_history(world, ctx=ctx)
        text = _ANSI_RE.sub("", captured.getvalue())

        self.assertIn("1 memorial(s)", text)
        self.assertIn("1 alias(es)", text)
        self.assertIn("1 trace(s)", text)


if __name__ == "__main__":
    unittest.main()

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
            _show_rumor_board,
            _show_world_dashboard,
            _show_results,
        )
        self.assertTrue(callable(_build_default_world))
        self.assertTrue(callable(_run_simulation))
        self.assertTrue(callable(_advance_simulation))
        self.assertTrue(callable(_show_results))
        self.assertTrue(callable(_save_simulation_snapshot))
        self.assertTrue(callable(_load_simulation_snapshot))
        self.assertTrue(callable(_select_language))
        self.assertTrue(callable(_show_rumor_board))
        self.assertTrue(callable(_show_world_dashboard))


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
        from fantasy_simulator.event_models import WorldEventRecord
        from fantasy_simulator.ui.screens import _show_location_history
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

        set_locale("en")
        world = World()
        loc = world.get_location_by_id("loc_aethoria_capital")
        assert loc is not None
        loc.aliases.append("The Crown City")
        loc.memorial_ids.append("m1")
        for idx in range(6):
            loc.live_traces.append({"year": 1001, "char_name": "Aldric", "text": f"trace {idx}"})
            world.record_event(
                WorldEventRecord(
                    record_id=f"r{idx + 1}",
                    kind="meeting",
                    year=1001,
                    month=1,
                    day=idx + 1,
                    location_id=loc.id,
                    description=f"Capital event {idx}",
                )
            )

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
        self.assertIn("6 trace(s)", text)
        self.assertIn("6 recent event(s)", text)
        self.assertIn("Recent events", text)
        self.assertIn("Capital event 5", text)
        self.assertIn("older visitor record", text)
        self.assertIn("older event", text)


class TestAutoAdvanceScreen(unittest.TestCase):
    def test_auto_advance_screen_prints_recommended_checks(self) -> None:
        from fantasy_simulator.ui.screen_simulation import _advance_auto
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

        set_locale("en")
        sim = SimpleNamespace(
            world=SimpleNamespace(
                characters=[SimpleNamespace(alive=True)],
                months_per_year=12,
                year=1000,
            ),
            get_pending_adventure_choices=lambda: [],
            advance_until_pause=lambda max_years: {
                "months_advanced": 0,
                "pause_reason": "dying_favorite",
                "pause_context": {"character": "Aldric", "location": "Aethoria Capital"},
                "pause_subreasons": [
                    {
                        "key": "actor_in_danger",
                        "character": "Aldric",
                        "location": "Aethoria Capital",
                    }
                ],
                "supplemental_reasons": [],
                "recommended_actions": [
                    {
                        "key": "inspect_character",
                        "character": "Aldric",
                        "location": "Aethoria Capital",
                    }
                ],
            },
        )

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
            _advance_auto(sim, ctx=ctx)
        text = _ANSI_RE.sub("", captured.getvalue())

        self.assertIn("Recommended checks:", text)
        self.assertIn("Why this matters:", text)
        self.assertIn("Aldric may die without attention.", text)
        self.assertIn("Inspect Aldric's condition", text)

    def test_auto_advance_screen_prints_location_only_world_change_context(self) -> None:
        from fantasy_simulator.ui.screen_simulation import _advance_auto
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

        set_locale("en")
        route = SimpleNamespace(
            route_id="route_capital_thornwood",
            from_site_id="loc_aethoria_capital",
            to_site_id="loc_thornwood",
        )
        sim = SimpleNamespace(
            world=SimpleNamespace(
                characters=[SimpleNamespace(alive=True)],
                months_per_year=12,
                year=1000,
                routes=[route],
                location_name=lambda location_id: {
                    "loc_aethoria_capital": "Aethoria Capital",
                    "loc_thornwood": "Thornwood",
                }.get(location_id, location_id),
            ),
            get_pending_adventure_choices=lambda: [],
            advance_until_pause=lambda max_years: {
                "months_advanced": 1,
                "pause_reason": "world_change_notification",
                "pause_context": {"location": "Aethoria Capital"},
                "pause_subreasons": [
                    {
                        "key": "world_change_notification",
                        "location": "Aethoria Capital",
                    }
                ],
                "supplemental_reasons": [],
                "recommended_actions": [
                    {
                        "key": "review_world_dashboard",
                        "location": "Aethoria Capital",
                        "target_type": "route",
                        "target_id": "route_capital_thornwood",
                    }
                ],
            },
        )

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
            _advance_auto(sim, ctx=ctx)
        text = _ANSI_RE.sub("", captured.getvalue())

        self.assertIn("Cause context: Aethoria Capital", text)
        self.assertNotIn("Cause context:  @ Aethoria Capital", text)
        self.assertIn("A world change requires attention at Aethoria Capital.", text)
        self.assertIn("Review the world dashboard (route: Aethoria Capital - Thornwood)", text)


class TestWorldDashboardScreen(unittest.TestCase):
    def test_world_dashboard_surfaces_observer_state(self) -> None:
        from fantasy_simulator.event_models import WorldEventRecord
        from fantasy_simulator.rumor_models import Rumor
        from fantasy_simulator.ui.screen_dashboard import _show_world_dashboard
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

        set_locale("en")
        world = World()
        hero = Character("Mira", 24, "Female", "Human", "Ranger", location_id="loc_aethoria_capital")
        hero.favorite = True
        world.add_character(hero)
        loc = world.get_location_by_id("loc_aethoria_capital")
        assert loc is not None
        loc.danger = 91
        world.record_event(
            WorldEventRecord(
                record_id="evt_major",
                kind="battle",
                year=world.year,
                month=1,
                day=1,
                location_id="loc_aethoria_capital",
                severity=4,
                description="Mira faced danger at the capital.",
            )
        )
        world.rumors.append(
            Rumor(
                description="The capital road is dangerous.",
                reliability="plausible",
                source_location_id="loc_aethoria_capital",
            )
        )
        sim = Simulator(world, events_per_year=0, seed=1)

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
            _show_world_dashboard(sim, ctx=ctx)
        text = _ANSI_RE.sub("", captured.getvalue())

        self.assertIn("Aethoria Dashboard", text)
        self.assertIn("Major events", text)
        self.assertIn("Mira faced danger at the capital.", text)
        self.assertIn("Watched actors", text)
        self.assertIn("Mira [favorite]", text)
        self.assertIn("The capital road is dangerous.", text)
        self.assertIn("Aethoria Capital (danger 91", text)
        self.assertIn("Follow up", text)
        self.assertIn("Inspect Mira at Aethoria Capital.", text)


class TestRumorBoardScreen(unittest.TestCase):
    class _ScriptedInputBackend:
        def __init__(self, answers):
            self.answers = list(answers)

        def read_line(self, prompt: str = "") -> str:
            return self.answers.pop(0) if self.answers else ""

        def read_menu_key(self, pairs, default=None):
            return pairs[0][0]

        def pause(self, message: str = "") -> None:
            pass

    def test_rumor_board_lists_active_rumors_with_context(self) -> None:
        from fantasy_simulator.rumor_models import Rumor
        from fantasy_simulator.ui.screen_rumors import _show_rumor_board
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

        set_locale("en")
        world = World()
        world.rumors.append(
            Rumor(
                id="rum_test",
                description="A road is said to be blocked.",
                reliability="plausible",
                source_location_id="loc_aethoria_capital",
                source_event_id="evt_road",
                age_in_months=2,
                spread_level=4,
            )
        )
        sim = Simulator(world, events_per_year=0, seed=1)

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
            _show_rumor_board(sim, ctx=ctx)
        text = _ANSI_RE.sub("", captured.getvalue())

        self.assertIn("RUMOR BOARD", text)
        self.assertIn("A road is said to be blocked.", text)
        self.assertIn("source: Aethoria Capital", text)
        self.assertIn("event: evt_road", text)

    def test_rumor_board_filters_by_location_query_and_clears_filter(self) -> None:
        from fantasy_simulator.rumor_models import Rumor
        from fantasy_simulator.ui.screen_rumors import _show_rumor_board
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

        set_locale("en")
        world = World()
        world.rumors.extend([
            Rumor(
                id="rum_capital",
                description="Capital rumor.",
                reliability="plausible",
                source_location_id="loc_aethoria_capital",
            ),
            Rumor(
                id="rum_thornwood",
                description="Forest rumor.",
                reliability="plausible",
                source_location_id="loc_thornwood",
            ),
        ])
        sim = Simulator(world, events_per_year=0, seed=1)

        ctx = UIContext(
            inp=self._ScriptedInputBackend(["l", "aethoria capital", "c", ""]),
            out=PrintRenderBackend(),
        )
        captured = io.StringIO()
        with redirect_stdout(captured):
            _show_rumor_board(sim, ctx=ctx)
        text = _ANSI_RE.sub("", captured.getvalue())

        self.assertIn("Filter: Aethoria Capital", text)
        self.assertIn("Capital rumor.", text)
        self.assertIn("Rumor source filter cleared.", text)
        self.assertIn("Forest rumor.", text)

    def test_rumor_board_handles_invalid_filter_choice_missing_event_and_empty_state(self) -> None:
        from fantasy_simulator.rumor_models import Rumor
        from fantasy_simulator.ui.screen_rumors import _show_rumor_board
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

        set_locale("en")
        world = World()
        world.rumors.append(
            Rumor(
                id="rum_missing",
                description="Missing source rumor.",
                reliability="plausible",
                source_location_id="loc_aethoria_capital",
                source_event_id="evt_missing",
            )
        )
        sim = Simulator(world, events_per_year=0, seed=1)

        ctx = UIContext(
            inp=self._ScriptedInputBackend(["z", "l", "missing place", "1", ""]),
            out=PrintRenderBackend(),
        )
        captured = io.StringIO()
        with redirect_stdout(captured):
            _show_rumor_board(sim, ctx=ctx)
        text = _ANSI_RE.sub("", captured.getvalue())

        self.assertIn("Invalid choice", text)
        self.assertIn("No matching location: missing place", text)
        self.assertIn("Source event is no longer available: evt_missing", text)

        world.rumors.clear()
        captured = io.StringIO()
        with redirect_stdout(captured):
            _show_rumor_board(sim, ctx=UIContext(inp=self._ScriptedInputBackend([""]), out=PrintRenderBackend()))
        empty_text = _ANSI_RE.sub("", captured.getvalue())
        self.assertIn("No active rumors are circulating.", empty_text)

    def test_rumor_board_excludes_expired_rumors(self) -> None:
        from fantasy_simulator.rumor_models import Rumor
        from fantasy_simulator.ui.screen_rumors import _show_rumor_board
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

        set_locale("en")
        world = World()
        world.rumors.append(
            Rumor(
                id="rum_expired",
                description="Expired rumor.",
                reliability="plausible",
                source_location_id="loc_aethoria_capital",
                age_in_months=999,
            )
        )
        sim = Simulator(world, events_per_year=0, seed=1)
        captured = io.StringIO()
        with redirect_stdout(captured):
            _show_rumor_board(
                sim,
                ctx=UIContext(inp=self._ScriptedInputBackend([""]), out=PrintRenderBackend()),
            )
        text = _ANSI_RE.sub("", captured.getvalue())

        self.assertIn("No active rumors are circulating.", text)
        self.assertNotIn("Expired rumor.", text)

    def test_rumor_board_detail_links_source_event_and_location(self) -> None:
        from fantasy_simulator.event_models import WorldEventRecord
        from fantasy_simulator.rumor_models import Rumor
        from fantasy_simulator.ui.screen_rumors import _show_rumor_board
        from fantasy_simulator.ui.ui_context import UIContext
        from fantasy_simulator.ui.render_backend import PrintRenderBackend

        set_locale("en")
        world = World()
        world.record_event(
            WorldEventRecord(
                record_id="evt_road",
                kind="journey",
                year=world.year,
                month=1,
                day=1,
                location_id="loc_aethoria_capital",
                description="A road incident was recorded.",
                summary_key="events.journey.summary",
                render_params={"actor": "Aldric"},
            )
        )
        world.rumors.append(
            Rumor(
                id="rum_test",
                description="A road is said to be blocked.",
                reliability="certain",
                source_location_id="loc_aethoria_capital",
                source_event_id="evt_road",
                age_in_months=1,
                spread_level=7,
            )
        )
        sim = Simulator(world, events_per_year=0, seed=1)

        class ScriptedInputBackend:
            def __init__(self) -> None:
                self.answers = ["1", ""]

            def read_line(self, prompt: str = "") -> str:
                return self.answers.pop(0)

            def read_menu_key(self, pairs, default=None):
                return pairs[0][0]

            def pause(self, message: str = "") -> None:
                pass

        ctx = UIContext(inp=ScriptedInputBackend(), out=PrintRenderBackend())
        captured = io.StringIO()
        with redirect_stdout(captured):
            _show_rumor_board(sim, ctx=ctx)
        text = _ANSI_RE.sub("", captured.getvalue())

        self.assertIn("RUMOR DETAIL", text)
        self.assertIn("Source event", text)
        self.assertIn("A road incident was recorded.", text)
        self.assertIn("Related location", text)
        self.assertIn("Recent events", text)


if __name__ == "__main__":
    unittest.main()

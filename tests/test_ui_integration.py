"""Integration tests for UIContext — prove backends are wired end-to-end.

These tests verify that ``screens.py``, ``main.py``, and
``character_creator.py`` truly route all I/O through the injected
``InputBackend`` and ``RenderBackend``, making the UI layer fully
swappable.
"""

from __future__ import annotations

import io
import os
import re
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from fantasy_simulator.character import Character
from fantasy_simulator.i18n import set_locale
from fantasy_simulator.ui.ui_context import UIContext
from fantasy_simulator.world import World
from tests.ui_test_doubles import RecordingRenderBackend, ScriptedInputBackend


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


# ---------------------------------------------------------------------------
# Tests: screens.py routes through backends
# ---------------------------------------------------------------------------

class TestShowResultsUsesBackends(unittest.TestCase):
    """_show_results routes all I/O through UIContext."""

    def setUp(self) -> None:
        set_locale("en")

    def test_yearly_report_goes_through_render_backend(self) -> None:
        """Selecting 'yearly_report' then 'back_to_main' must produce
        output ONLY through the recording backend (not print())."""
        from fantasy_simulator.ui.screens import _show_results, _build_default_world

        world = _build_default_world(num_characters=4, seed=42)
        from fantasy_simulator.simulator import Simulator
        sim = Simulator(world, events_per_year=2)
        sim.advance_years(1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["yearly_report", "back_to_main"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        # Output must have been captured by the recording backend
        self.assertTrue(len(out.calls) > 0, "No output was captured")
        # Heading calls must exist (post-results header)
        headings = [c for c in out.calls if c[0] == "print_heading"]
        self.assertTrue(len(headings) >= 1, "No headings printed")

    def test_world_map_goes_through_render_backend(self) -> None:
        """Selecting 'world_map' renders via backend, not print()."""
        from fantasy_simulator.ui.screens import _show_results, _build_default_world

        world = _build_default_world(num_characters=4, seed=42)
        from fantasy_simulator.simulator import Simulator
        sim = Simulator(world, events_per_year=2)
        sim.advance_years(1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["world_map", "back_to_main"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        # Map output must appear through render backend
        # At minimum the backend captured several lines
        self.assertTrue(len(out.calls) > 5)

    def test_simulation_summary_goes_through_render_backend(self) -> None:
        from fantasy_simulator.ui.screens import _show_results, _build_default_world

        world = _build_default_world(num_characters=4, seed=42)
        from fantasy_simulator.simulator import Simulator
        sim = Simulator(world, events_per_year=2)
        sim.advance_years(1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["simulation_summary", "back_to_main"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)
        self.assertTrue(len(out.calls) > 5)

    def test_event_log_goes_through_render_backend(self) -> None:
        from fantasy_simulator.ui.screens import _show_results, _build_default_world

        world = _build_default_world(num_characters=8, seed=42)
        from fantasy_simulator.simulator import Simulator
        sim = Simulator(world, events_per_year=8)
        sim.advance_years(3)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["event_log_last_30", "back_to_main"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)
        # Backend must have captured output (even if event log happens to be empty,
        # the separator/heading calls prove the route goes through backends)
        self.assertTrue(len(out.calls) > 3, "Too few backend calls captured")

    def test_world_map_auto_mode_uses_minimal_on_narrow_terminal(self) -> None:
        from fantasy_simulator.ui.screens import _show_results, _build_default_world

        world = _build_default_world(num_characters=4, seed=42)
        from fantasy_simulator.simulator import Simulator
        sim = Simulator(world, events_per_year=2)
        sim.advance_years(1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["world_map", "back_to_main", "back_to_main"])
        ctx = UIContext(inp=inp, out=out)

        with (
            patch("shutil.get_terminal_size", return_value=os.terminal_size((50, 24))),
            patch("fantasy_simulator.ui.atlas_renderer.render_atlas_overview", return_value="WIDE"),
            patch("fantasy_simulator.ui.atlas_renderer.render_atlas_compact", return_value="COMPACT"),
            patch("fantasy_simulator.ui.atlas_renderer.render_atlas_minimal", return_value="MINIMAL"),
        ):
            _show_results(sim, ctx=ctx)

        self.assertIn("MINIMAL", out.text)
        self.assertNotIn("WIDE", out.text)

    def test_world_map_auto_mode_uses_compact_on_medium_terminal(self) -> None:
        from fantasy_simulator.ui.screens import _show_results, _build_default_world

        world = _build_default_world(num_characters=4, seed=42)
        from fantasy_simulator.simulator import Simulator
        sim = Simulator(world, events_per_year=2)
        sim.advance_years(1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["world_map", "back_to_main", "back_to_main"])
        ctx = UIContext(inp=inp, out=out)

        with (
            patch("shutil.get_terminal_size", return_value=os.terminal_size((72, 24))),
            patch("fantasy_simulator.ui.atlas_renderer.render_atlas_overview", return_value="WIDE"),
            patch("fantasy_simulator.ui.atlas_renderer.render_atlas_compact", return_value="COMPACT"),
            patch("fantasy_simulator.ui.atlas_renderer.render_atlas_minimal", return_value="MINIMAL"),
        ):
            _show_results(sim, ctx=ctx)

        self.assertIn("COMPACT", out.text)
        self.assertNotIn("WIDE", out.text)

    def test_world_map_auto_mode_uses_wide_on_large_terminal(self) -> None:
        from fantasy_simulator.ui.screens import _show_results, _build_default_world

        world = _build_default_world(num_characters=4, seed=42)
        from fantasy_simulator.simulator import Simulator
        sim = Simulator(world, events_per_year=2)
        sim.advance_years(1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["world_map", "back_to_main", "back_to_main"])
        ctx = UIContext(inp=inp, out=out)

        with (
            patch("shutil.get_terminal_size", return_value=os.terminal_size((100, 24))),
            patch("fantasy_simulator.ui.atlas_renderer.render_atlas_overview", return_value="WIDE"),
            patch("fantasy_simulator.ui.atlas_renderer.render_atlas_compact", return_value="COMPACT"),
            patch("fantasy_simulator.ui.atlas_renderer.render_atlas_minimal", return_value="MINIMAL"),
        ):
            _show_results(sim, ctx=ctx)

        self.assertIn("WIDE", out.text)

    def test_world_map_prints_semantic_legend_and_keys_hint(self) -> None:
        from fantasy_simulator.ui.screens import _show_results, _build_default_world

        world = _build_default_world(num_characters=4, seed=42)
        from fantasy_simulator.simulator import Simulator
        sim = Simulator(world, events_per_year=2)
        sim.advance_years(1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["world_map", "back_to_main", "back_to_main"])
        ctx = UIContext(inp=inp, out=out)
        _show_results(sim, ctx=ctx)
        self.assertIn("Semantic legend", out.text)
        self.assertIn("Keys:", out.text)

    def test_world_map_uses_panel_when_backend_supports_it(self) -> None:
        from fantasy_simulator.ui.screens import _show_results, _build_default_world

        world = _build_default_world(num_characters=4, seed=42)
        from fantasy_simulator.simulator import Simulator
        sim = Simulator(world, events_per_year=2)
        sim.advance_years(1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["world_map", "back_to_main", "back_to_main"])
        ctx = UIContext(inp=inp, out=out)
        _show_results(sim, ctx=ctx)

        panel_calls = [c for c in out.calls if c[0] == "print_panel"]
        self.assertGreaterEqual(len(panel_calls), 1)


class TestShowRosterUsesBackends(unittest.TestCase):
    """_show_roster routes through UIContext."""

    def setUp(self) -> None:
        set_locale("en")

    def test_roster_output_goes_through_backend(self) -> None:
        from fantasy_simulator.ui.screens import _show_roster

        world = World()
        world.add_character(Character("Alice", 25, "Female", "Human", "Warrior",
                                      location_id="loc_aethoria_capital"))

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend()
        ctx = UIContext(inp=inp, out=out)

        _show_roster(world, ctx=ctx)

        # Must have separator, heading, and character line
        self.assertTrue(any(c[0] == "print_separator" for c in out.calls))
        self.assertTrue(any(c[0] == "print_heading" for c in out.calls))
        self.assertTrue(any("Alice" in c[1] for c in out.calls if len(c) > 1))


class TestSelectLanguageUsesBackends(unittest.TestCase):
    """_select_language routes through UIContext."""

    def setUp(self) -> None:
        set_locale("en")

    def test_select_english_via_backend(self) -> None:
        from fantasy_simulator.ui.screens import _select_language

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["en"])
        ctx = UIContext(inp=inp, out=out)

        _select_language(ctx=ctx)

        success_calls = [c for c in out.calls if c[0] == "print_success"]
        self.assertTrue(len(success_calls) >= 1)


class TestScreenNewSimUsesBackends(unittest.TestCase):
    """screen_new_simulation routes through UIContext."""

    def setUp(self) -> None:
        set_locale("en")

    def test_new_sim_output_through_backend(self) -> None:
        from fantasy_simulator.ui.screens import screen_new_simulation

        out = RecordingRenderBackend()
        # answers: "4" chars, "1" year;  menu_keys: "back_to_main" for results
        inp = ScriptedInputBackend(
            answers=["4", "1"],
            menu_keys=["back_to_main"],
        )
        ctx = UIContext(inp=inp, out=out)

        screen_new_simulation(ctx=ctx)

        # Must have captured heading and simulation output
        self.assertTrue(len(out.calls) > 5)
        headings = [c for c in out.calls if c[0] == "print_heading"]
        self.assertTrue(len(headings) >= 1)


class TestWorldLoreUsesBackends(unittest.TestCase):
    """screen_world_lore routes through UIContext."""

    def setUp(self) -> None:
        set_locale("en")

    def test_lore_output_goes_through_backend(self) -> None:
        from fantasy_simulator.ui.screens import screen_world_lore

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend()
        ctx = UIContext(inp=inp, out=out)

        screen_world_lore(ctx=ctx)

        # Must have wrapped text (world lore)
        wrapped = [c for c in out.calls if c[0] == "print_wrapped"]
        self.assertTrue(len(wrapped) > 0, "World lore was not sent through print_wrapped")
        headings = [call[1] for call in out.calls if call[0] == "print_heading"]
        self.assertTrue(any("Languages" in heading for heading in headings))

    def test_lore_output_prefers_world_setting_bundle(self) -> None:
        from fantasy_simulator.content.setting_bundle import JobDefinition, RaceDefinition, default_aethoria_bundle
        from fantasy_simulator.ui.screens import screen_world_lore

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend()
        ctx = UIContext(inp=inp, out=out)
        world = World()
        bundle = default_aethoria_bundle(lore_text="Bundle lore text for tests.")
        bundle.world_definition.races = [
            RaceDefinition(name="Scholar", description="Readers of lost signs.", stat_bonuses={"intelligence": 2})
        ]
        bundle.world_definition.jobs = [
            JobDefinition(name="Archivist", description="Preserves old memory.", primary_skills=["Lore Mastery"])
        ]
        world.setting_bundle = bundle

        screen_world_lore(world=world, ctx=ctx)

        wrapped = [c for c in out.calls if c[0] == "print_wrapped"]
        self.assertTrue(any("Bundle lore text for tests." in call[1] for call in wrapped))
        self.assertTrue(any("Readers of lost signs." in call[1] for call in wrapped))
        self.assertTrue(any("Preserves old memory." in call[1] for call in wrapped))

    def test_lore_output_uses_same_race_job_fallbacks_as_character_creator(self) -> None:
        from fantasy_simulator.content.setting_bundle import default_aethoria_bundle
        from fantasy_simulator.ui.screens import screen_world_lore

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend()
        ctx = UIContext(inp=inp, out=out)
        world = World()
        bundle = default_aethoria_bundle(lore_text="Fallback lore text.")
        bundle.world_definition.races = []
        bundle.world_definition.jobs = []
        world.setting_bundle = bundle

        screen_world_lore(world=world, ctx=ctx)

        highlighted = [call[1] for call in out.calls if call[0] == "print_highlighted"]
        self.assertTrue(any("Human" in entry for entry in highlighted))
        self.assertTrue(any("Warrior" in entry for entry in highlighted))

    def test_lore_output_accepts_ctx_as_first_positional_argument(self) -> None:
        from fantasy_simulator.ui.screens import screen_world_lore

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend()
        ctx = UIContext(inp=inp, out=out)

        screen_world_lore(ctx)

        wrapped = [c for c in out.calls if c[0] == "print_wrapped"]
        self.assertTrue(len(wrapped) > 0, "Positional ctx call should still render lore text")


# ---------------------------------------------------------------------------
# Tests: main.py routes through backends
# ---------------------------------------------------------------------------

class TestMainMenuUsesBackends(unittest.TestCase):
    """main() routes all I/O through UIContext."""

    def setUp(self) -> None:
        set_locale("en")

    def test_main_exit_via_injected_backend(self) -> None:
        """Selecting 'exit' from the main menu must go through
        the injected backends and produce output there."""
        from fantasy_simulator.main import main

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["exit"])
        ctx = UIContext(inp=inp, out=out)

        with self.assertRaises(SystemExit):
            main(ctx=ctx)

        # Farewell message must have been captured
        self.assertTrue(len(out.calls) > 0)


# ---------------------------------------------------------------------------
# Tests: CharacterCreator routes through backends
# ---------------------------------------------------------------------------

class TestCharacterCreatorUsesBackends(unittest.TestCase):
    """CharacterCreator.create_interactive() routes through UIContext."""

    def setUp(self) -> None:
        set_locale("en")

    def test_interactive_creation_uses_backend(self) -> None:
        from fantasy_simulator.character_creator import CharacterCreator

        out = RecordingRenderBackend()
        # answers: name, gender, race, job, age, stats ("n" = accept defaults)
        inp = ScriptedInputBackend(answers=[
            "TestHero",     # name
            "",             # gender (default)
            "1",            # race (Human)
            "1",            # job (Warrior)
            "25",           # age
            "n",            # don't manually distribute stats
        ])
        ctx = UIContext(inp=inp, out=out)

        creator = CharacterCreator()
        char = creator.create_interactive(ctx=ctx)

        self.assertEqual(char.name, "TestHero")
        # Verify output was captured through backend
        self.assertTrue(len(out.calls) > 5)
        # Must have printed separator and character info
        seps = [c for c in out.calls if c[0] == "print_separator"]
        self.assertTrue(len(seps) >= 1)


# ---------------------------------------------------------------------------
# Tests: prove zero print()/input() leaks
# ---------------------------------------------------------------------------

class TestNoPrintLeaks(unittest.TestCase):
    """Verify that when backends are injected, stdout gets NO output.

    This is the strongest integration guarantee: if all I/O truly goes
    through the backends, capturing stdout should produce nothing.
    """

    def setUp(self) -> None:
        set_locale("en")

    def test_show_roster_produces_no_stdout(self) -> None:
        from fantasy_simulator.ui.screens import _show_roster

        world = World()
        world.add_character(Character("X", 20, "Male", "Human", "Warrior",
                                      location_id="loc_aethoria_capital"))

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend()
        ctx = UIContext(inp=inp, out=out)

        captured = io.StringIO()
        with redirect_stdout(captured):
            _show_roster(world, ctx=ctx)

        stdout_text = captured.getvalue()
        self.assertEqual(stdout_text, "", f"Leaked to stdout: {stdout_text!r}")

    def test_select_language_produces_no_stdout(self) -> None:
        from fantasy_simulator.ui.screens import _select_language

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["en"])
        ctx = UIContext(inp=inp, out=out)

        captured = io.StringIO()
        with redirect_stdout(captured):
            _select_language(ctx=ctx)

        stdout_text = captured.getvalue()
        self.assertEqual(stdout_text, "", f"Leaked to stdout: {stdout_text!r}")

    def test_world_lore_produces_no_stdout(self) -> None:
        from fantasy_simulator.ui.screens import screen_world_lore

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend()
        ctx = UIContext(inp=inp, out=out)

        captured = io.StringIO()
        with redirect_stdout(captured):
            screen_world_lore(ctx=ctx)

        stdout_text = captured.getvalue()
        self.assertEqual(stdout_text, "", f"Leaked to stdout: {stdout_text!r}")

    def test_screen_new_simulation_produces_no_stdout(self) -> None:
        """The full new-simulation path (build world, run sim, show results)
        must not leak any bytes to stdout when backends are injected."""
        from fantasy_simulator.ui.screens import screen_new_simulation

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(answers=["4", "1"], menu_keys=["back_to_main"])
        ctx = UIContext(inp=inp, out=out)

        captured = io.StringIO()
        with redirect_stdout(captured):
            screen_new_simulation(ctx=ctx)

        stdout_text = captured.getvalue()
        self.assertEqual(stdout_text, "", f"Leaked to stdout: {stdout_text!r}")

    def test_advance_simulation_produces_no_stdout(self) -> None:
        """_advance_simulation must not leak to stdout."""
        from fantasy_simulator.ui.screens import _build_default_world, _advance_simulation
        from fantasy_simulator.simulator import Simulator

        world = _build_default_world(num_characters=4, seed=42)
        sim = Simulator(world, events_per_year=2)
        sim.advance_years(1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend()
        ctx = UIContext(inp=inp, out=out)

        captured = io.StringIO()
        with redirect_stdout(captured):
            _advance_simulation(sim, 1, ctx=ctx)

        stdout_text = captured.getvalue()
        self.assertEqual(stdout_text, "", f"Leaked to stdout: {stdout_text!r}")

    def test_advance_simulation_heading_is_localized(self) -> None:
        from fantasy_simulator.ui.screens import _build_default_world, _advance_simulation
        from fantasy_simulator.simulator import Simulator

        set_locale("ja")
        try:
            world = _build_default_world(num_characters=4, seed=42)
            sim = Simulator(world, events_per_year=2)

            out = RecordingRenderBackend()
            inp = ScriptedInputBackend()
            ctx = UIContext(inp=inp, out=out)

            _advance_simulation(sim, 2, ctx=ctx)

            headings = [call[1] for call in out.calls if call[0] == "print_heading"]
            self.assertTrue(any("+2年" in heading for heading in headings))
            self.assertNotIn("years", out.text)
        finally:
            set_locale("en")

    def test_main_exit_produces_no_stdout(self) -> None:
        """main() exit path must not leak to stdout."""
        from fantasy_simulator.main import main

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["exit"])
        ctx = UIContext(inp=inp, out=out)

        captured = io.StringIO()
        with redirect_stdout(captured):
            try:
                main(ctx=ctx)
            except SystemExit:
                pass

        stdout_text = captured.getvalue()
        self.assertEqual(stdout_text, "", f"Leaked to stdout: {stdout_text!r}")


class TestGetNumericChoiceUsesBackend(unittest.TestCase):
    """_get_numeric_choice routes through UIContext."""

    def setUp(self) -> None:
        set_locale("en")

    def test_valid_choice_returns_index(self) -> None:
        from fantasy_simulator.ui.screens import _get_numeric_choice

        inp = ScriptedInputBackend(answers=["2"])
        out = RecordingRenderBackend()
        ctx = UIContext(inp=inp, out=out)

        result = _get_numeric_choice("Pick: ", 5, ctx=ctx)
        self.assertEqual(result, 1)  # 0-based

    def test_empty_returns_none(self) -> None:
        from fantasy_simulator.ui.screens import _get_numeric_choice

        inp = ScriptedInputBackend(answers=[""])
        out = RecordingRenderBackend()
        ctx = UIContext(inp=inp, out=out)

        result = _get_numeric_choice("Pick: ", 5, ctx=ctx)
        self.assertIsNone(result)

    def test_out_of_range_shows_warning(self) -> None:
        from fantasy_simulator.ui.screens import _get_numeric_choice

        inp = ScriptedInputBackend(answers=["99"])
        out = RecordingRenderBackend()
        ctx = UIContext(inp=inp, out=out)

        result = _get_numeric_choice("Pick: ", 5, ctx=ctx)
        self.assertIsNone(result)
        warnings = [c for c in out.calls if c[0] == "print_warning"]
        self.assertTrue(len(warnings) >= 1)

    def test_non_digit_shows_warning(self) -> None:
        from fantasy_simulator.ui.screens import _get_numeric_choice

        inp = ScriptedInputBackend(answers=["abc"])
        out = RecordingRenderBackend()
        ctx = UIContext(inp=inp, out=out)

        result = _get_numeric_choice("Pick: ", 5, ctx=ctx)
        self.assertIsNone(result)
        warnings = [c for c in out.calls if c[0] == "print_warning"]
        self.assertTrue(len(warnings) >= 1)


class TestReadBoundedIntUsesBackend(unittest.TestCase):
    """_read_bounded_int centralizes bounded numeric prompts."""

    def test_valid_value(self) -> None:
        from fantasy_simulator.ui.screen_input import _read_bounded_int

        inp = ScriptedInputBackend(answers=["7"])
        ctx = UIContext(inp=inp, out=RecordingRenderBackend())

        result = _read_bounded_int("Count: ", default=12, minimum=4, maximum=30, ctx=ctx)
        self.assertEqual(result, 7)

    def test_default_for_non_digit(self) -> None:
        from fantasy_simulator.ui.screen_input import _read_bounded_int

        inp = ScriptedInputBackend(answers=["many"])
        ctx = UIContext(inp=inp, out=RecordingRenderBackend())

        result = _read_bounded_int("Count: ", default=12, minimum=4, maximum=30, ctx=ctx)
        self.assertEqual(result, 12)

    def test_clamps_to_bounds(self) -> None:
        from fantasy_simulator.ui.screen_input import _read_bounded_int

        low_ctx = UIContext(inp=ScriptedInputBackend(answers=["1"]), out=RecordingRenderBackend())
        high_ctx = UIContext(inp=ScriptedInputBackend(answers=["99"]), out=RecordingRenderBackend())

        self.assertEqual(_read_bounded_int("Count: ", default=12, minimum=4, maximum=30, ctx=low_ctx), 4)
        self.assertEqual(_read_bounded_int("Count: ", default=12, minimum=4, maximum=30, ctx=high_ctx), 30)


if __name__ == "__main__":
    unittest.main()

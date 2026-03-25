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
from typing import List, Optional, Tuple
from unittest.mock import patch

from fantasy_simulator.character import Character
from fantasy_simulator.i18n import set_locale
from fantasy_simulator.world import World
from fantasy_simulator.ui.ui_context import UIContext


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


# ---------------------------------------------------------------------------
# Recording backends — capture every call for assertions
# ---------------------------------------------------------------------------

class RecordingRenderBackend:
    """Captures all output calls as structured records."""

    def __init__(self) -> None:
        self.calls: List[Tuple[str, ...]] = []

    def print_line(self, text: str = "") -> None:
        self.calls.append(("print_line", text))

    def print_heading(self, text: str) -> None:
        self.calls.append(("print_heading", text))

    def print_separator(self, char: str = "=", width: int = 62) -> None:
        self.calls.append(("print_separator", char, str(width)))

    def print_error(self, text: str) -> None:
        self.calls.append(("print_error", text))

    def print_success(self, text: str) -> None:
        self.calls.append(("print_success", text))

    def print_warning(self, text: str) -> None:
        self.calls.append(("print_warning", text))

    def print_wrapped(self, text: str, indent: int = 4) -> None:
        self.calls.append(("print_wrapped", text))

    def print_dim(self, text: str) -> None:
        self.calls.append(("print_dim", text))

    def print_highlighted(self, text: str) -> None:
        self.calls.append(("print_highlighted", text))

    def format_status(self, text: str, positive: bool) -> str:
        # Return plain text — no ANSI in tests
        return text

    def print_menu(self, prompt: str, key_label_pairs, default=None) -> None:
        self.calls.append(("print_menu", prompt, len(key_label_pairs)))

    def print_panel(self, title: str, text: str) -> None:
        self.calls.append(("print_panel", title, text))

    def get_terminal_width(self) -> int:
        import shutil

        return shutil.get_terminal_size(fallback=(80, 24)).columns

    @property
    def text(self) -> str:
        """Concatenate all printed text for simple substring checks."""
        return "\n".join(str(t) for (_, *rest) in self.calls for t in rest)


class ScriptedInputBackend:
    """Returns pre-scripted answers to read_line / choose_key / pause."""

    def __init__(self, answers: List[str] | None = None,
                 menu_keys: List[str] | None = None) -> None:
        self._answers = list(answers or [])
        self._menu_keys = list(menu_keys or [])
        self._answer_idx = 0
        self._menu_idx = 0

    def read_line(self, prompt: str = "") -> str:
        if self._answer_idx < len(self._answers):
            val = self._answers[self._answer_idx]
            self._answer_idx += 1
            return val
        return ""

    def read_menu_key(
        self,
        key_label_pairs: List[Tuple[str, str]],
        default: Optional[str] = None,
    ) -> str:
        if self._menu_idx < len(self._menu_keys):
            val = self._menu_keys[self._menu_idx]
            self._menu_idx += 1
            return val
        return key_label_pairs[-1][0]  # fallback: last option (usually "back")

    def pause(self, message: str = "") -> None:
        pass


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

    def test_world_map_auto_mode_uses_compact_on_narrow_terminal(self) -> None:
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

        self.assertIn("COMPACT", out.text)
        self.assertNotIn("WIDE", out.text)

    def test_world_map_auto_mode_uses_minimal_on_tiny_terminal(self) -> None:
        from fantasy_simulator.ui.screens import _show_results, _build_default_world

        world = _build_default_world(num_characters=4, seed=42)
        from fantasy_simulator.simulator import Simulator
        sim = Simulator(world, events_per_year=2)
        sim.advance_years(1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["world_map", "back_to_main", "back_to_main"])
        ctx = UIContext(inp=inp, out=out)

        with (
            patch("shutil.get_terminal_size", return_value=os.terminal_size((30, 24))),
            patch("fantasy_simulator.ui.atlas_renderer.render_atlas_overview", return_value="WIDE"),
            patch("fantasy_simulator.ui.atlas_renderer.render_atlas_compact", return_value="COMPACT"),
            patch("fantasy_simulator.ui.atlas_renderer.render_atlas_minimal", return_value="MINIMAL"),
        ):
            _show_results(sim, ctx=ctx)

        self.assertIn("MINIMAL", out.text)
        self.assertNotIn("WIDE", out.text)

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


if __name__ == "__main__":
    unittest.main()

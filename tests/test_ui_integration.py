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
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
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

    def test_results_leave_warning_can_keep_reviewing_then_exit(self) -> None:
        from fantasy_simulator.simulator import Simulator
        from fantasy_simulator.ui.screens import _build_default_world, _show_results

        world = _build_default_world(num_characters=4, seed=42)
        sim = Simulator(world, events_per_year=0)
        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["back_to_main", "keep_reviewing", "back_to_main", "exit"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        self.assertIn("There are unsaved simulation results.", out.text)

    def test_save_snapshot_cancel_preserves_existing_file(self) -> None:
        from fantasy_simulator.ui.screens import _save_simulation_snapshot

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "snapshot.json"
            path.write_text("original", encoding="utf-8")
            out = RecordingRenderBackend()
            inp = ScriptedInputBackend(answers=[str(path)], menu_keys=["cancel"])
            ctx = UIContext(inp=inp, out=out)

            saved = _save_simulation_snapshot(object(), ctx=ctx)

            self.assertFalse(saved)
            self.assertEqual(path.read_text(encoding="utf-8"), "original")
            self.assertIn("Save cancelled.", out.text)

    def test_yearly_report_defaults_to_card_without_legacy_text(self) -> None:
        from types import SimpleNamespace
        from fantasy_simulator.ui.screens import _show_yearly_report

        world = World()
        sim = SimpleNamespace(
            world=world,
            get_latest_completed_report_year=lambda: world.year,
            get_yearly_report=lambda year: f"RAW YEARLY REPORT {year}",
        )
        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["back"])
        ctx = UIContext(inp=inp, out=out)

        _show_yearly_report(sim, ctx=ctx)

        self.assertIn("Yearly highlights", out.text)
        self.assertIn("Report view", out.text)
        self.assertNotIn("RAW YEARLY REPORT", out.text)

    def test_yearly_report_can_show_legacy_detail_on_demand(self) -> None:
        from types import SimpleNamespace
        from fantasy_simulator.ui.screens import _show_yearly_report

        world = World()
        sim = SimpleNamespace(
            world=world,
            get_latest_completed_report_year=lambda: world.year,
            get_yearly_report=lambda year: f"RAW YEARLY REPORT {year}",
        )
        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["details"])
        ctx = UIContext(inp=inp, out=out)

        _show_yearly_report(sim, ctx=ctx)

        self.assertIn("Yearly highlights", out.text)
        self.assertIn("RAW YEARLY REPORT", out.text)

    def test_monthly_report_defaults_to_card_without_legacy_text(self) -> None:
        from types import SimpleNamespace
        from fantasy_simulator.ui.screens import _show_monthly_report

        world = World()
        sim = SimpleNamespace(
            world=world,
            get_latest_completed_report_year=lambda: world.year,
            get_monthly_report=lambda year, month: f"RAW MONTHLY REPORT {year}-{month}",
        )
        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(answers=["1"], menu_keys=["back"])
        ctx = UIContext(inp=inp, out=out)

        _show_monthly_report(sim, ctx=ctx)

        self.assertIn("Monthly highlights", out.text)
        self.assertIn("Report view", out.text)
        self.assertNotIn("RAW MONTHLY REPORT", out.text)

    def test_monthly_report_can_show_legacy_detail_on_demand(self) -> None:
        from types import SimpleNamespace
        from fantasy_simulator.ui.screens import _show_monthly_report

        world = World()
        sim = SimpleNamespace(
            world=world,
            get_latest_completed_report_year=lambda: world.year,
            get_monthly_report=lambda year, month: f"RAW MONTHLY REPORT {year}-{month}",
        )
        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(answers=["1"], menu_keys=["details"])
        ctx = UIContext(inp=inp, out=out)

        _show_monthly_report(sim, ctx=ctx)

        self.assertIn("Monthly highlights", out.text)
        self.assertIn("RAW MONTHLY REPORT", out.text)

    def test_monthly_report_follow_up_opens_character_story(self) -> None:
        from types import SimpleNamespace
        from fantasy_simulator.events import WorldEventRecord
        from fantasy_simulator.ui.screens import _show_monthly_report

        world = World()
        hero = Character("Mira", 24, "Female", "Human", "Ranger", location_id="loc_aethoria_capital")
        hero.favorite = True
        hero.history.append("Year 1000: Held the capital gate.")
        world.add_character(hero)
        world.record_event(
            WorldEventRecord(
                record_id="mira_gate",
                kind="battle",
                year=world.year,
                month=1,
                day=3,
                primary_actor_id=hero.char_id,
                severity=5,
                description="Mira held the capital gate.",
            )
        )
        sim = SimpleNamespace(
            world=world,
            get_latest_completed_report_year=lambda: world.year,
            get_monthly_report=lambda year, month: f"RAW MONTHLY REPORT {year}-{month}",
            get_character_story=lambda character_id: "\n".join(hero.history),
        )
        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(answers=["1"], menu_keys=["followup:1"])
        ctx = UIContext(inp=inp, out=out)

        _show_monthly_report(sim, ctx=ctx)

        self.assertIn("Watched threads", out.text)
        self.assertIn("Report view", out.text)
        self.assertIn("Held the capital gate.", out.text)
        self.assertNotIn("RAW MONTHLY REPORT", out.text)

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

    def test_event_log_renders_causal_chain_without_internal_hashes(self) -> None:
        from types import SimpleNamespace
        from fantasy_simulator.event_models import WorldEventRecord
        from fantasy_simulator.ui.screens import _show_results

        cause_id = "0123456789abcdef0123456789abcdef"
        effect_id = "fedcba9876543210fedcba9876543210"
        world = World()
        world.record_event(
            WorldEventRecord(
                record_id=cause_id,
                kind="war_declared",
                year=world.year,
                month=1,
                day=2,
                description="The northern houses declared war.",
            )
        )
        world.record_event(
            WorldEventRecord(
                record_id=effect_id,
                kind="war_battle",
                year=world.year,
                month=2,
                day=9,
                description="The armies clashed at the old bridge.",
                cause_event_ids=[cause_id],
            )
        )
        sim = SimpleNamespace(world=world)
        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["event_log_last_30", "back_to_main", "exit"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        self.assertIn("The armies clashed at the old bridge.", out.text)
        self.assertIn("Because: The northern houses declared war.", out.text)
        self.assertIsNone(re.search(r"\b[0-9a-f]{32}\b", out.text))

    def test_event_log_renders_relationship_personality_and_catalyst_factors(self) -> None:
        import random
        from types import SimpleNamespace
        from fantasy_simulator.event_models import WorldEventRecord
        from fantasy_simulator.events import EventSystem
        from fantasy_simulator.ui.screens import _show_results

        world = World()
        saved = Character("Saved", 25, "Female", "Human", "Warrior", char_id="saved")
        rescuer = Character("Rescuer", 25, "Male", "Human", "Warrior", char_id="rescuer")
        saved.personality = {
            "openness": 100,
            "discipline": 0,
            "extraversion": 100,
            "agreeableness": 20,
            "stability": 20,
        }
        rescuer.personality = {
            "openness": 0,
            "discipline": 100,
            "extraversion": 0,
            "agreeableness": 20,
            "stability": 20,
        }
        for character in (saved, rescuer):
            world.add_character(character)
        world.record_event(WorldEventRecord(
            record_id="rescue_cause",
            kind="dying_rescued",
            year=world.year,
            primary_actor_id=saved.char_id,
            secondary_actor_ids=[rescuer.char_id],
            description="Rescuer saved Saved.",
        ))
        result = EventSystem().event_marriage(saved, rescuer, world, rng=random.Random(1))
        world.record_event(WorldEventRecord.from_event_result(result, rng=random.Random(2)))
        sim = SimpleNamespace(world=world)
        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["event_log_last_30", "back_to_main", "exit"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        self.assertIn("Because: Rescuer saved Saved.", out.text)
        self.assertIn("Relationship factors:", out.text)
        self.assertIn("personality", out.text)
        self.assertIn("gratitude after being rescued", out.text)
        self.assertIn("catalyst a rescue debt", out.text)

    def test_event_log_summarizes_combat_rounds_without_expanding_details(self) -> None:
        from types import SimpleNamespace
        from fantasy_simulator.event_models import WorldEventRecord
        from fantasy_simulator.ui.screens import _show_results

        world = World()
        world.record_event(
            WorldEventRecord(
                record_id="battle-round-visible",
                kind="war_battle",
                year=world.year,
                month=2,
                day=9,
                description="The armies clashed at the old bridge.",
                render_params={
                    "combat_log": [
                        {
                            "round_number": 1,
                            "actor_name": "Northern levy",
                            "target_name": "Bridge guard",
                            "action_kind": "weapon_attack",
                            "skill_key": "Swordsmanship",
                            "dice": 14,
                            "modifier": 6,
                            "attack_total": 20,
                            "defense_total": 16,
                            "damage": 3,
                            "outcome": "advantage",
                        }
                    ]
                },
            )
        )
        sim = SimpleNamespace(world=world)
        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["event_log_last_30", "back_to_main", "exit"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        self.assertIn("Combat log: 1 rounds.", out.text)
        self.assertNotIn("R1: Northern levy used Swordsmanship", out.text)
        self.assertNotIn("roll 14+6=20 vs 16, damage 3, advantage.", out.text)

    def test_combat_log_menu_renders_latest_combat_without_full_event_log(self) -> None:
        from types import SimpleNamespace
        from fantasy_simulator.event_models import WorldEventRecord
        from fantasy_simulator.ui.screens import _show_results

        world = World()
        world.record_event(
            WorldEventRecord(
                record_id="battle-focused",
                kind="battle",
                year=world.year,
                month=2,
                day=9,
                description="Aldric fought a rival.",
                render_params={
                    "combat_log": [
                        {
                            "round_number": 1,
                            "actor_name": "Aldric",
                            "target_name": "Rival",
                            "action_kind": "weapon_attack",
                            "skill_key": "Swordsmanship",
                            "dice": 14,
                            "modifier": 6,
                            "attack_total": 20,
                            "defense_total": 16,
                            "damage": 3,
                            "outcome": "advantage",
                        }
                    ]
                },
            )
        )
        sim = SimpleNamespace(world=world)
        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(answers=["1"], menu_keys=["combat_logs", "latest", "back_to_main", "exit"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        self.assertIn("Combat logs", out.text)
        self.assertIn("Aldric fought a rival.", out.text)
        self.assertIn("R1: Aldric used Swordsmanship", out.text)

    def test_combat_log_menu_filters_by_character(self) -> None:
        from types import SimpleNamespace
        from fantasy_simulator.event_models import WorldEventRecord
        from fantasy_simulator.ui.screens import _show_results

        world = World()
        hero = Character("Aldric", 25, "Male", "Human", "Warrior", char_id="hero")
        rival = Character("Rival", 25, "Male", "Human", "Warrior", char_id="rival")
        bystander = Character("Mira", 25, "Female", "Human", "Mage", char_id="bystander")
        for character in (hero, rival, bystander):
            world.add_character(character)
        world.record_event(
            WorldEventRecord(
                record_id="battle-hero",
                kind="battle",
                year=world.year,
                primary_actor_id=hero.char_id,
                secondary_actor_ids=[rival.char_id],
                description="Aldric fought a rival.",
                render_params={
                    "combat_log": [{"round_number": 1, "actor_id": hero.char_id, "target_id": rival.char_id}]
                },
            )
        )
        sim = SimpleNamespace(world=world)
        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(answers=["1", "1"], menu_keys=["combat_logs", "character", "back_to_main", "exit"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        self.assertIn("Combat logs: Aldric", out.text)
        self.assertIn("Aldric fought a rival.", out.text)
        self.assertNotIn("Combat logs: Mira", out.text)

    def test_adventure_detail_renders_hazard_combat_rounds(self) -> None:
        from fantasy_simulator.adventure import AdventureRun
        from fantasy_simulator.simulator import Simulator
        from fantasy_simulator.ui.screens import _show_results

        world = World()
        hero = Character("Aldric", 25, "Male", "Human", "Warrior", location_id="loc_aethoria_capital")
        world.add_character(hero)
        run = AdventureRun(
            character_id=hero.char_id,
            character_name=hero.name,
            origin="loc_aethoria_capital",
            destination="loc_thornwood",
            year_started=world.year,
        )
        run.detail_log.append("Aldric entered the thornwood.")
        run.combat_logs.append({
            "step": 2,
            "location_id": "loc_thornwood",
            "member_id": hero.char_id,
            "member_name": hero.name,
            "hazard_id": "hazard:adv:2",
            "hazard_name": "forest warden",
            "winner_id": hero.char_id,
            "loser_id": "hazard:adv:2",
            "combat_log": [
                {
                    "round_number": 1,
                    "actor_name": hero.name,
                    "target_name": "forest warden",
                    "action_kind": "weapon_attack",
                    "skill_key": "Swordsmanship",
                    "dice": 12,
                    "modifier": 5,
                    "attack_total": 17,
                    "defense_total": 11,
                    "damage": 4,
                    "outcome": "decisive",
                }
            ],
        })
        world.add_adventure(run)
        sim = Simulator(world, events_per_year=0, seed=1)
        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(answers=["1"], menu_keys=["adventure_details", "back_to_main", "exit"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        self.assertIn("Combat encounter: Aldric vs forest warden", out.text)
        self.assertIn("R1: Aldric used Swordsmanship", out.text)
        self.assertIn("damage 4, decisive.", out.text)

    def test_world_dashboard_follow_up_opens_character_story(self) -> None:
        from fantasy_simulator.simulator import Simulator
        from fantasy_simulator.ui.screens import _show_results

        world = World()
        hero = Character("Mira", 24, "Female", "Human", "Ranger", location_id="loc_aethoria_capital")
        hero.favorite = True
        hero.history.append("Year 1000: Watched the capital gate.")
        world.add_character(hero)
        sim = Simulator(world, events_per_year=0, seed=1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["world_dashboard", "1", "back_to_main"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        self.assertIn("Open follow-up", out.text)
        self.assertIn("Mira", out.text)
        self.assertIn("Watched the capital gate.", out.text)

    def test_world_dashboard_follow_up_opens_location_map_detail(self) -> None:
        from fantasy_simulator.simulator import Simulator
        from fantasy_simulator.ui.screens import _show_results

        world = World()
        route = world.routes[0]
        world.apply_route_blocked_change(route.route_id, True, month=2)
        sim = Simulator(world, events_per_year=0, seed=1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(menu_keys=["world_dashboard", "1", "back", "back_to_main"])
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        self.assertIn("Open follow-up", out.text)
        self.assertIn("Location follow-up", out.text)
        self.assertIn("Local site sketch", out.text)

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

    def test_world_map_can_browse_sites_by_local_cue_category(self) -> None:
        from fantasy_simulator.ui.screens import _show_results, _build_default_world

        world = _build_default_world(num_characters=4, seed=42)
        from fantasy_simulator.simulator import Simulator
        sim = Simulator(world, events_per_year=2)
        sim.advance_years(1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(
            answers=["1"],
            menu_keys=["world_map", "cue", "memory", "back_to_main", "back_to_main"],
        )
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        self.assertIn("Local cue category", out.text)
        self.assertIn("Sites with Memory cues", out.text)
        self.assertIn("Accident site", out.text)

    def test_world_map_detail_can_follow_up_to_location_history(self) -> None:
        from fantasy_simulator.ui.screens import _show_results, _build_default_world

        world = _build_default_world(num_characters=4, seed=42)
        world.add_live_trace(
            "loc_aethoria_capital",
            1001,
            "Scout",
            "A scout marked this gate after sunset.",
        )
        from fantasy_simulator.simulator import Simulator
        sim = Simulator(world, events_per_year=2)
        sim.advance_years(1)

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(
            answers=["1"],
            menu_keys=["world_map", "detail", "location_history", "back_to_main", "back_to_main"],
        )
        ctx = UIContext(inp=inp, out=out)

        _show_results(sim, ctx=ctx)

        self.assertIn("Location follow-up", out.text)
        self.assertIn("LOCATION DETAIL - Aethoria Capital", out.text)
        self.assertIn("A scout marked this gate after sunset.", out.text)

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

    def test_roster_profile_groups_background_family_history_and_combat(self) -> None:
        from fantasy_simulator.event_models import WorldEventRecord
        from fantasy_simulator.ui.screens import _show_roster

        world = World()
        hero = Character(
            "Aldric",
            25,
            "Male",
            "Human",
            "Warrior",
            char_id="hero",
            location_id="loc_aethoria_capital",
            founder_background={
                "family_origin": "minor_noble",
                "family_status": "fallen",
                "upbringing": "strict_training",
                "pre_adventure": "local_guard",
                "reputation": "promising",
            },
            history=["Year 1000: Took up the sword.", "Year 1001: Guarded the north road."],
            personality_feats=["brave", "oathbound"],
        )
        spouse = Character("Mira", 24, "Female", "Human", "Mage", char_id="spouse")
        child = Character("Lio", 3, "Male", "Human", "Warrior", char_id="child")
        hero.spouse_id = spouse.char_id
        hero.add_relation_tag(child.char_id, "child")
        hero.add_relation_tag(spouse.char_id, "spouse")
        hero.update_relationship(spouse.char_id, 72)
        for character in (hero, spouse, child):
            world.add_character(character)
        world.record_event(
            WorldEventRecord(
                record_id="rescue_1",
                kind="dying_rescued",
                year=1001,
                primary_actor_id=hero.char_id,
                secondary_actor_ids=[spouse.char_id],
                description="Mira pulled Aldric from a collapsed bridge.",
            )
        )
        world.record_event(
            WorldEventRecord(
                record_id="comfort_1",
                kind="relationship_comfort",
                year=1002,
                primary_actor_id=hero.char_id,
                secondary_actor_ids=[spouse.char_id],
                description="Aldric and Mira found a quiet moment of comfort.",
                cause_event_ids=["rescue_1"],
                render_params={
                    "personality_affinity": 6,
                    "personality_factors": "mutual warmth; relief after recovery",
                    "relationship_delta": 12,
                },
            )
        )
        world.record_event(
            WorldEventRecord(
                record_id="battle_1",
                kind="battle",
                year=1002,
                primary_actor_id=hero.char_id,
                secondary_actor_ids=["rival"],
                description="Aldric fought a rival.",
                render_params={
                    "combat_log": [{
                        "round_number": 1,
                        "actor_id": hero.char_id,
                        "actor_name": hero.name,
                        "target_id": "rival",
                        "target_name": "Rival",
                        "action_kind": "weapon_attack",
                        "skill_key": "Swordsmanship",
                        "dice": 12,
                        "modifier": 5,
                        "attack_total": 17,
                        "defense_total": 11,
                        "damage": 4,
                        "outcome": "decisive",
                    }],
                },
            )
        )

        out = RecordingRenderBackend()
        inp = ScriptedInputBackend(answers=["1"])
        ctx = UIContext(inp=inp, out=out)

        _show_roster(world, ctx=ctx)

        self.assertIn("Aldric profile", out.text)
        self.assertIn("Personality", out.text)
        self.assertIn("Temperament", out.text)
        self.assertIn("Features", out.text)
        self.assertIn("brave, oathbound", out.text)
        self.assertIn("Current demeanor", out.text)
        self.assertIn("gratitude after being rescued", out.text)
        self.assertIn("combat tension", out.text)
        self.assertIn("Background", out.text)
        self.assertIn("Family", out.text)
        self.assertIn("Spouse: Mira", out.text)
        self.assertIn("Children: Lio", out.text)
        self.assertIn("Relationships", out.text)
        self.assertIn("Mira: +72", out.text)
        self.assertIn("Relationship history", out.text)
        self.assertIn("Aldric and Mira found a quiet moment of comfort.", out.text)
        self.assertIn("Because: Mira pulled Aldric from a collapsed bridge.", out.text)
        self.assertIn("Factors: personality mutual warmth; relief after recovery", out.text)
        self.assertIn("Recent history", out.text)
        self.assertIn("Guarded the north road", out.text)
        self.assertIn("Recent combat", out.text)
        self.assertIn("Aldric fought a rival.", out.text)


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

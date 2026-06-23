"""Snapshot-style rendering tests for key CLI views."""

import io
from contextlib import redirect_stdout
from types import SimpleNamespace

from fantasy_simulator.character import Character
from fantasy_simulator.i18n import set_locale
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.ui.render_backend import PrintRenderBackend
from fantasy_simulator.ui.screens import (
    _show_adventure_summaries,
    _show_location_history,
    _show_monthly_report,
    _show_roster,
    _show_world_map,
)
from fantasy_simulator.ui.ui_context import UIContext
from fantasy_simulator.world import World
from fantasy_simulator.adventure import AdventureRun, POLICY_TREASURE
from tests.support.ui_doubles import RecordingRenderBackend, ScriptedInputBackend


class _NoopInput:
    def __init__(self, first=""):
        self.first = first
        self.calls = 0

    def read_line(self, prompt: str = "") -> str:
        self.calls += 1
        if self.calls == 1:
            return self.first
        return ""

    def read_menu_key(self, pairs, default=None):
        return pairs[0][0]

    def pause(self, message: str = "") -> None:
        return None


def test_snapshot_adventure_summary_en():
    set_locale("en")
    world = World()
    a = Character("Aldric", 20, "Male", "Human", "Warrior", location_id="loc_aethoria_capital")
    b = Character("Lysara", 20, "Female", "Elf", "Mage", location_id="loc_aethoria_capital")
    world.add_character(a)
    world.add_character(b)
    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=1)
    world.add_adventure(
        AdventureRun(
            character_id=a.char_id,
            character_name=a.name,
            origin=a.location_id,
            destination="loc_thornwood",
            year_started=world.year,
            member_ids=[a.char_id, b.char_id],
            policy=POLICY_TREASURE,
        )
    )
    ctx = UIContext(inp=_NoopInput(), out=PrintRenderBackend())
    buf = io.StringIO()
    with redirect_stdout(buf):
        _show_adventure_summaries(sim, ctx=ctx)
    out = buf.getvalue()
    assert "ADVENTURE SUMMARIES" in out
    assert "[Party]" in out


def test_snapshot_location_history_ja():
    set_locale("ja")
    world = World()
    loc = world.get_location_by_id("loc_aethoria_capital")
    assert loc is not None
    loc.aliases.append("王都")
    loc.memorial_ids.append("m1")
    loc.live_traces.append({"year": 1, "char_name": "A", "text": "Aが通過"})
    ctx = UIContext(inp=_NoopInput(first="1"), out=PrintRenderBackend())
    buf = io.StringIO()
    with redirect_stdout(buf):
        _show_location_history(world, ctx=ctx)
    out = buf.getvalue()
    assert "地点詳細" in out
    assert "記念碑" in out


def test_snapshot_monthly_report_card_screen_en():
    set_locale("en")
    world = World()
    route = world.routes[0]
    blocked = world.apply_route_blocked_change(route.route_id, True, year=world.year, month=3, day=2)
    assert blocked is not None
    sim = SimpleNamespace(
        world=world,
        get_latest_completed_report_year=lambda: world.year,
        get_monthly_report=lambda year, month: f"RAW MONTHLY REPORT {year}-{month}",
    )
    out = RecordingRenderBackend()
    inp = ScriptedInputBackend(answers=["3"], menu_keys=["back"])
    ctx = UIContext(inp=inp, out=out)

    _show_monthly_report(sim, ctx=ctx)

    assert out.lines[:4] == [
        "",
        "  Year: 1000",
        "  1: Embermorn (Winter), 2: Frostwane (Winter), 3: Raincall (Spring), "
        "4: Bloomtide (Spring), 5: Suncrest (Spring), 6: Highsun (Summer), "
        "7: Goldleaf (Summer), 8: Hearthwane (Summer), 9: Duskmarch (Autumn), "
        "10: Cinderfall (Autumn), 11: Longshade (Autumn), 12: Nightfrost (Winter)",
        "",
    ]
    assert any("Monthly highlights (1000-Raincall)" in line for line in out.lines)
    assert any("World-change threads" in line for line in out.lines)
    assert any("Route: 1 change(s)" in line for line in out.lines)
    assert "RAW MONTHLY REPORT" not in out.text


def test_snapshot_character_roster_screen_en():
    set_locale("en")
    world = World()
    world.characters.clear()
    world.add_character(
        Character("Mira", 24, "Female", "Human", "Ranger", location_id="loc_aethoria_capital")
    )
    world.add_character(
        Character("Thorn Archivist With A Very Long Name", 41, "Male", "Elf", "Mage", location_id="loc_thornwood")
    )
    out = RecordingRenderBackend()
    ctx = UIContext(inp=ScriptedInputBackend(), out=out)

    _show_roster(world, ctx=ctx)

    assert out.lines[:4] == [
        "",
        "=" * 62,
        "  Name                   Race/Job               Age   STR INT DEX   Status      Location            ",
        "=" * 62,
    ]
    assert any("Mira" in line and "Human Ranger" in line and "Aethoria Capital" in line for line in out.lines)
    assert any("Thorn Archivist Wit..." in line and "Elf Mage" in line and "Thornwood" in line for line in out.lines)


def test_snapshot_world_map_screen_en():
    set_locale("en")
    world = World()
    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=1)
    out = RecordingRenderBackend()
    ctx = UIContext(inp=ScriptedInputBackend(menu_keys=["back"]), out=out)

    _show_world_map(sim, ctx=ctx)

    assert out.lines[0] == ""
    assert out.lines[1] == "World map (Wide atlas (full))"
    assert "Aethoria (Year: 1000)" in out.lines[2]
    assert "Aethoria Capital" in out.text
    assert "Semantic legend" in out.text
    assert "Keys:" in out.text

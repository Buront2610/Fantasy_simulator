"""Snapshot-style rendering tests for key CLI views."""

import io
from contextlib import redirect_stdout

from fantasy_simulator.character import Character
from fantasy_simulator.i18n import set_locale
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.ui.render_backend import PrintRenderBackend
from fantasy_simulator.ui.screens import _show_adventure_summaries, _show_location_history
from fantasy_simulator.ui.ui_context import UIContext
from fantasy_simulator.world import World
from fantasy_simulator.adventure import AdventureRun, POLICY_TREASURE


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

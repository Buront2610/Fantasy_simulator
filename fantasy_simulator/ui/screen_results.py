"""Post-simulation result menu flow."""

from __future__ import annotations

from ..i18n import tr
from ..simulator import Simulator
from .screen_adventures import (
    _resolve_pending_adventure_choice,
    _show_adventure_details,
    _show_adventure_summaries,
)
from .screen_history import (
    _show_location_history,
    _show_monthly_report,
    _show_single_story,
)
from .screen_map import _show_world_map
from .screen_persistence import _save_simulation_snapshot
from .screen_roster import _show_roster
from .screen_simulation import _advance_auto, _advance_simulation
from .ui_context import UIContext, _default_ctx


def _show_results(sim: Simulator, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out
    inp = ctx.inp
    world = sim.world

    while True:
        out.print_line()
        out.print_separator("=")
        out.print_heading(f"  {tr('post_results')}")
        out.print_separator("=")
        action = ctx.choose_key(
            tr("what_to_view"),
            [
                ("advance_1_year", tr("advance_1_year")),
                ("advance_5_years", tr("advance_5_years")),
                ("advance_auto", tr("advance_auto")),
                ("yearly_report", tr("yearly_report")),
                ("monthly_report", tr("monthly_report")),
                ("world_map", tr("world_map")),
                ("character_roster", tr("character_roster")),
                ("event_log_last_30", tr("event_log_last_30")),
                ("full_event_log", tr("full_event_log")),
                ("adventure_summaries", tr("adventure_summaries")),
                ("adventure_details", tr("adventure_details")),
                ("resolve_pending_choice", tr("resolve_pending_choice")),
                ("save_snapshot", tr("save_snapshot")),
                ("character_story", tr("character_story")),
                ("all_character_stories", tr("all_character_stories")),
                ("simulation_summary", tr("simulation_summary")),
                ("location_history", tr("location_history_menu")),
                ("back_to_main", tr("back_to_main")),
            ],
        )

        if action == "advance_1_year":
            _advance_simulation(sim, 1, ctx=ctx)
        elif action == "advance_5_years":
            _advance_simulation(sim, 5, ctx=ctx)
        elif action == "advance_auto":
            _advance_auto(sim, ctx=ctx)
        elif action == "yearly_report":
            out.print_line()
            out.print_line(sim.get_latest_yearly_report())
            inp.pause()
        elif action == "monthly_report":
            _show_monthly_report(sim, ctx=ctx)
        elif action == "world_map":
            _show_world_map(sim, ctx=ctx)
        elif action == "character_roster":
            _show_roster(world, ctx=ctx)
        elif action == "event_log_last_30":
            out.print_line()
            for entry in sim.get_event_log(last_n=30):
                out.print_line(f"  - {entry}")
            inp.pause()
        elif action == "full_event_log":
            out.print_line()
            for entry in sim.get_event_log():
                out.print_line(f"  - {entry}")
            inp.pause()
        elif action == "adventure_summaries":
            _show_adventure_summaries(sim, ctx=ctx)
        elif action == "adventure_details":
            _show_adventure_details(sim, ctx=ctx)
        elif action == "resolve_pending_choice":
            _resolve_pending_adventure_choice(sim, ctx=ctx)
        elif action == "save_snapshot":
            _save_simulation_snapshot(sim, ctx=ctx)
        elif action == "character_story":
            _show_single_story(sim, ctx=ctx)
        elif action == "all_character_stories":
            out.print_line()
            out.print_line(sim.get_all_stories())
            inp.pause()
        elif action == "simulation_summary":
            out.print_line()
            out.print_line(sim.get_summary())
            inp.pause()
        elif action == "location_history":
            _show_location_history(world, ctx=ctx)
        else:
            break

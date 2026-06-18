"""Post-simulation result menu flow."""

from __future__ import annotations

from ..event_rendering import render_event_record
from ..i18n import tr
from ..simulator import Simulator
from .combat_log_presenter import combat_log_lines_for_event
from .screen_adventures import (
    _resolve_pending_adventure_choice,
    _show_adventure_details,
    _show_adventure_summaries,
)
from .screen_dashboard import _show_world_dashboard
from .screen_history import (
    _show_location_history,
    _show_monthly_report,
    _show_single_story,
    _show_yearly_report,
)
from .screen_family_tree import _show_family_tree
from .screen_map import _show_world_map
from .screen_persistence import _save_simulation_snapshot
from .screen_roster import _show_roster
from .screen_rumors import _show_rumor_board
from .screen_simulation import _advance_auto, _advance_simulation
from .ui_context import UIContext, _default_ctx


def _confirm_leave_with_unsaved_changes(ctx: UIContext) -> bool:
    choice = ctx.choose_key(
        tr("unsaved_leave_prompt"),
        [
            ("keep_reviewing", tr("unsaved_leave_keep_reviewing")),
            ("exit", tr("unsaved_leave_confirm")),
        ],
        default="1",
    )
    return choice == "exit"


def _result_menu_options() -> list[tuple[str, str]]:
    return [
        ("advance_1_year", tr("advance_1_year")),
        ("advance_5_years", tr("advance_5_years")),
        ("advance_auto", tr("advance_auto")),
        ("world_dashboard", tr("dashboard_menu")),
        ("yearly_report", tr("yearly_report")),
        ("monthly_report", tr("monthly_report")),
        ("rumor_board", tr("rumor_board_menu")),
        ("world_map", tr("world_map")),
        ("character_roster", tr("character_roster")),
        ("family_tree", tr("family_tree_menu")),
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
    ]


def _show_event_log(sim: Simulator, ctx: UIContext, last_n: int | None = None) -> None:
    ctx.out.print_line()
    records = list(getattr(sim.world, "event_records", []))
    shown = records[-last_n:] if last_n is not None else records
    if not shown:
        ctx.out.print_dim(f"  {tr('event_log_empty')}")
        ctx.inp.pause()
        return
    for record in shown:
        ctx.out.print_line(f"  - {_event_log_prefix(record)} {render_event_record(record, world=sim.world)}")
        cause_text = _event_log_cause_text(sim, record)
        if cause_text:
            ctx.out.print_dim(f"      {cause_text}")
        for line in combat_log_lines_for_event(record):
            ctx.out.print_dim(f"      {line}")
    ctx.inp.pause()


def _event_log_prefix(record: object) -> str:
    year = int(getattr(record, "year", 0) or 0)
    month = int(getattr(record, "month", 0) or 0)
    day = int(getattr(record, "day", 0) or 0)
    if day > 0 and month > 0:
        return tr("event_log_prefix_day", year=year, month=month, day=day)
    if month > 0:
        return tr("event_log_prefix_month", year=year, month=month)
    return tr("event_log_prefix", year=year)


def _event_log_cause_text(sim: Simulator, record: object) -> str:
    cause_ids = list(getattr(record, "cause_event_ids", []))
    if not cause_ids:
        return ""
    causes = [
        render_event_record(cause, world=sim.world)
        for cause in sim.world.get_event_causes(getattr(record, "record_id", ""))
    ]
    if not causes:
        return tr("event_log_causes_unavailable")
    return tr("event_log_caused_by", events=" | ".join(causes))


def _update_dirty_state_for_action(action: str, sim: Simulator, ctx: UIContext) -> bool | None:
    if action == "advance_1_year":
        _advance_simulation(sim, 1, ctx=ctx)
        return True
    if action == "advance_5_years":
        _advance_simulation(sim, 5, ctx=ctx)
        return True
    if action == "advance_auto":
        _advance_auto(sim, ctx=ctx)
        return True
    if action == "resolve_pending_choice":
        _resolve_pending_adventure_choice(sim, ctx=ctx)
        return True
    if action == "save_snapshot":
        return not _save_simulation_snapshot(sim, ctx=ctx)
    return None


def _show_result_view(action: str, sim: Simulator, ctx: UIContext) -> bool:
    if action == "world_dashboard":
        _show_world_dashboard(sim, ctx=ctx)
    elif action == "yearly_report":
        _show_yearly_report(sim, ctx=ctx)
    elif action == "monthly_report":
        _show_monthly_report(sim, ctx=ctx)
    elif action == "rumor_board":
        _show_rumor_board(sim, ctx=ctx)
    elif action == "world_map":
        _show_world_map(sim, ctx=ctx)
    elif action == "character_roster":
        _show_roster(sim.world, ctx=ctx)
    elif action == "family_tree":
        _show_family_tree(sim, ctx=ctx)
    elif action == "event_log_last_30":
        _show_event_log(sim, ctx, last_n=30)
    elif action == "full_event_log":
        _show_event_log(sim, ctx)
    elif action == "adventure_summaries":
        _show_adventure_summaries(sim, ctx=ctx)
    elif action == "adventure_details":
        _show_adventure_details(sim, ctx=ctx)
    elif action == "character_story":
        _show_single_story(sim, ctx=ctx)
    elif action == "all_character_stories":
        ctx.out.print_line()
        ctx.out.print_line(sim.get_all_stories())
        ctx.inp.pause()
    elif action == "simulation_summary":
        ctx.out.print_line()
        ctx.out.print_line(sim.get_summary())
        ctx.inp.pause()
    elif action == "location_history":
        _show_location_history(sim.world, ctx=ctx)
    else:
        return False
    return True


def _show_results(sim: Simulator, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out
    has_unsaved_changes = True

    while True:
        out.print_line()
        out.print_separator("=")
        out.print_heading(f"  {tr('post_results')}")
        out.print_separator("=")
        action = ctx.choose_key(tr("what_to_view"), _result_menu_options())

        dirty_state = _update_dirty_state_for_action(action, sim, ctx)
        if dirty_state is not None:
            has_unsaved_changes = dirty_state
            continue
        if _show_result_view(action, sim, ctx):
            continue
        if has_unsaved_changes and not _confirm_leave_with_unsaved_changes(ctx):
            continue
        break

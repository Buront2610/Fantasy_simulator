"""Report, story, and location-history screen flows."""

from __future__ import annotations

from typing import Any

from ..i18n import tr, tr_term
from ..simulator import Simulator
from ..world import World
from .presenters import LocationPresenter, ReportPresenter
from .screen_input import _get_numeric_choice
from .ui_context import UIContext, _default_ctx
from .view_models import (
    FollowUpActionView,
    LocationHistoryView,
    build_location_observation_view,
    build_monthly_report_card_view,
    build_yearly_report_card_view,
)


def _open_report_follow_up(sim: Simulator, action: FollowUpActionView, ctx: UIContext) -> None:
    world = sim.world
    if action.target_type == "character":
        character = world.get_character_by_id(action.target_id)
        if character is not None:
            _show_character_story(sim, character.char_id, ctx=ctx)
            return
    if action.target_type in {"location", "world_change"} and action.location_id:
        loc = world.get_location_by_id(action.location_id)
        if loc is not None:
            _show_location_history_for_location(world, loc, ctx=ctx)
            return
    ctx.out.print_dim(f"  {tr('dashboard_follow_up_unavailable')}")
    ctx.inp.pause()


def _month_season_hint(world: World, year: int) -> str:
    """Return a compact historical-calendar hint for monthly report selection."""
    months_per_year = world.months_per_year_for_date(year, 1, 1)
    return ", ".join(
        f"{month}: {world.month_display_name_for_date(year, month)} "
        f"({tr('season_' + world.season_for_date(year, month))})"
        for month in range(1, months_per_year + 1)
    )


def _show_monthly_report(sim: Simulator, ctx: UIContext | None = None) -> None:
    """Show a monthly report card for the latest completed year."""
    ctx = _default_ctx(ctx)
    out = ctx.out

    year = sim.get_latest_completed_report_year()
    out.print_line()
    out.print_line(f"  {tr('year_label')}: {year}")
    report_months = sim.world.months_per_year_for_date(year, 1, 1)
    out.print_line(f"  {_month_season_hint(sim.world, year)}")
    month_idx = _get_numeric_choice(
        f"  {tr('monthly_report')} (1-{report_months}): ",
        report_months,
        ctx=ctx,
    )
    if month_idx is None:
        return
    month = month_idx + 1
    out.print_line()
    card = build_monthly_report_card_view(sim.world, year, month)
    for line in ReportPresenter.render_monthly_card(card):
        out.print_line(f"  {line}")

    follow_up_options = [
        (f"followup:{index}", item.label)
        for index, item in enumerate(card.follow_up_actions, 1)
    ]
    action = ctx.choose_key(
        tr("report_followup_prompt"),
        [
            ("details", tr("report_show_detailed_text")),
            *follow_up_options,
            ("back", tr("back_to_main")),
        ],
    )
    if action == "details":
        out.print_line()
        out.print_line(sim.get_monthly_report(year, month))
    elif action.startswith("followup:"):
        index = int(action.split(":", 1)[1]) - 1
        if 0 <= index < len(card.follow_up_actions):
            _open_report_follow_up(sim, card.follow_up_actions[index], ctx)
            return
    ctx.inp.pause()


def _show_yearly_report(sim: Simulator, ctx: UIContext | None = None) -> None:
    """Show a yearly report card, with detailed text available on demand."""
    ctx = _default_ctx(ctx)
    out = ctx.out

    year = sim.get_latest_completed_report_year()
    out.print_line()
    card = build_yearly_report_card_view(sim.world, year)
    for line in ReportPresenter.render_yearly_card(card):
        out.print_line(f"  {line}")

    action = ctx.choose_key(
        tr("report_followup_prompt"),
        [
            ("details", tr("report_show_detailed_text")),
            ("back", tr("back_to_main")),
        ],
    )
    if action == "details":
        out.print_line()
        out.print_line(sim.get_yearly_report(year))
    ctx.inp.pause()


def _show_single_story(sim: Simulator, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out
    world = sim.world

    out.print_line()
    for i, character in enumerate(world.characters, 1):
        status = out.format_status(
            tr("status_alive") if character.alive else tr("status_dead"),
            character.alive,
        )
        out.print_line(
            f"  {i:>2}. [{status}] {character.name} "
            f"({tr_term(character.race)} {tr_term(character.job)}, "
            f"{tr('age_short_label')} {character.age})"
        )
    out.print_line()
    idx = _get_numeric_choice(f"  {tr('enter_character_number')}", len(world.characters), ctx=ctx)
    if idx is None:
        return
    character = world.characters[idx]
    _show_character_story(sim, character.char_id, ctx=ctx)


def _show_character_story(sim: Simulator, character_id: str, ctx: UIContext | None = None) -> None:
    """Show one already-selected character story."""
    ctx = _default_ctx(ctx)
    ctx.out.print_line()
    ctx.out.print_line(sim.get_character_story(character_id))
    ctx.inp.pause()


def _show_location_history(world: World, ctx: UIContext | None = None) -> None:
    """Show live traces, memorials, and aliases for a selected location."""
    ctx = _default_ctx(ctx)
    out = ctx.out

    locations = sorted(world.grid.values(), key=lambda loc: loc.canonical_name)
    out.print_line()
    for i, loc in enumerate(locations, 1):
        view = LocationHistoryView(
            location_name=loc.canonical_name,
            region_type=tr_term(loc.region_type),
            aliases=list(loc.aliases),
            memorials=list(loc.memorial_ids),
            traces=[trace.get("text", "") for trace in loc.live_traces],
            recent_event_count=len(loc.recent_event_ids),
        )
        out.print_line(LocationPresenter.render_location_row(i, view))
    out.print_line()

    idx = _get_numeric_choice(f"  {tr('enter_location_number')}", len(locations), ctx=ctx)
    if idx is None:
        return

    _show_location_history_for_location(world, locations[idx], ctx=ctx)


def _show_location_history_for_location(world: World, loc: Any, ctx: UIContext | None = None) -> None:
    """Show live traces, memorials, and aliases for one already-selected location."""
    ctx = _default_ctx(ctx)
    out = ctx.out

    observation = build_location_observation_view(world, loc.id)
    out.print_line()
    out.print_separator()
    out.print_heading(f"  {tr('location_detail_header', name=loc.canonical_name)}")
    out.print_separator()
    for line in LocationPresenter.render_observation_sections(observation):
        out.print_line(line)
    if len(loc.live_traces) > 5:
        out.print_dim(f"    {tr('location_live_traces_truncated', count=len(loc.live_traces) - 5)}")
    if len(loc.recent_event_ids) > 5:
        out.print_dim(f"    {tr('location_recent_events_truncated', count=len(loc.recent_event_ids) - 5)}")

    ctx.inp.pause()

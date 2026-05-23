"""Rumor board screen helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..event_rendering import render_event_record
from ..i18n import tr
from ..location_observation import RumorSummaryView, build_rumor_summary_views, render_rumor_brief
from ..simulator import Simulator
from .ui_context import UIContext, _default_ctx

if TYPE_CHECKING:
    from ..world import World


def _show_rumor_board(sim: Simulator, ctx: UIContext | None = None) -> None:
    """Render active rumors as a compact inspection board."""
    ctx = _default_ctx(ctx)
    out = ctx.out
    location_filter: str | None = None

    while True:
        rumors = build_rumor_summary_views(sim.world, location_id=location_filter, limit=20)
        out.print_line()
        out.print_heading(f"  {tr('rumor_board_title')}")
        if location_filter:
            out.print_dim(f"  {tr('rumor_board_filter_label', location=sim.world.location_name(location_filter))}")
        if not rumors:
            out.print_dim(f"  {tr('rumor_board_empty')}")
        else:
            _render_rumor_rows(rumors, ctx=ctx)

        choice = ctx.inp.read_line(tr("rumor_board_prompt")).strip()
        if not choice:
            return
        normalized = choice.lower()
        if normalized == "l":
            selected = _read_location_filter(sim.world, ctx=ctx)
            if selected is not None:
                location_filter = selected
            continue
        if normalized == "c":
            location_filter = None
            out.print_dim(f"  {tr('rumor_board_filter_cleared')}")
            continue
        if not choice.isdigit():
            out.print_error(f"  {tr('invalid_choice')}")
            continue
        index = int(choice) - 1
        if index < 0 or index >= len(rumors):
            out.print_error(f"  {tr('invalid_choice')}")
            continue
        _show_rumor_detail(sim, rumors[index], ctx=ctx)


def _render_rumor_rows(rumors: list[RumorSummaryView], ctx: UIContext) -> None:
    out = ctx.out
    for index, rumor in enumerate(rumors, 1):
        location = rumor.source_location_name or "-"
        event_id = rumor.source_event_id or "-"
        out.print_line(f"  {index}. {render_rumor_brief(rumor)}")
        meta = tr(
            "rumor_board_meta",
            location=location,
            age=rumor.age_in_months,
            spread=rumor.spread_level,
            event_id=event_id,
        )
        out.print_dim(f"     {meta}")


def _read_location_filter(world: "World", ctx: UIContext) -> str | None:
    value = ctx.inp.read_line(tr("rumor_board_filter_prompt")).strip()
    if not value:
        return None
    location = world.find_location_by_id_or_name(value)
    if location is not None:
        return location.id
    ctx.out.print_error(f"  {tr('rumor_board_filter_not_found', location=value)}")
    return None


def _show_rumor_detail(sim: Simulator, rumor: RumorSummaryView, ctx: UIContext) -> None:
    out = ctx.out
    out.print_line()
    out.print_heading(f"  {tr('rumor_board_detail_title')}")
    out.print_line(f"  {render_rumor_brief(rumor)}")
    source_location = rumor.source_location_name or "-"
    source_meta = tr(
        "rumor_board_detail_source",
        location=source_location,
        age=rumor.age_in_months,
        spread=rumor.spread_level,
    )
    out.print_dim(f"  {source_meta}")
    if rumor.source_event_id:
        record = sim.world.get_event_by_id(rumor.source_event_id)
        if record is None:
            out.print_dim(f"  {tr('rumor_board_event_missing', event_id=rumor.source_event_id)}")
        else:
            out.print_line()
            out.print_highlighted(f"  {tr('rumor_board_source_event')}")
            out.print_wrapped(render_event_record(record, world=sim.world), indent=4)
    else:
        out.print_dim(f"  {tr('rumor_board_no_source_event')}")

    if rumor.source_location_id:
        out.print_line()
        out.print_highlighted(f"  {tr('rumor_board_related_location')}")
        out.print_line(sim.get_location_observation(rumor.source_location_id))
    ctx.inp.pause()

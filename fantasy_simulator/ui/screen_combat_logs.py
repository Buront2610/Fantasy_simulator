"""Focused combat-log browsing screens."""

from __future__ import annotations

from typing import Any

from ..combat_system.log_index import CombatLogEntryView, build_combat_log_index
from ..world_event.rendering import render_event_record
from ..i18n import tr
from .combat_log_presenter import combat_log_lines_for_adventure_entry, combat_log_lines_for_event
from .screen_input import _get_numeric_choice
from .ui_context import UIContext, _default_ctx


def _show_combat_logs(sim: Any, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    action = ctx.choose_key(
        tr("combat_logs_prompt"),
        [
            ("latest", tr("combat_logs_latest")),
            ("character", tr("combat_logs_by_character")),
            ("back", tr("back_to_main")),
        ],
    )
    if action == "latest":
        _show_combat_log_entries(sim, build_combat_log_index(sim.world), ctx)
    elif action == "character":
        _show_character_combat_logs(sim, ctx)


def _show_character_combat_logs(sim: Any, ctx: UIContext) -> None:
    characters = sorted(sim.world.characters, key=lambda character: character.name)
    ctx.out.print_line()
    for index, character in enumerate(characters, 1):
        ctx.out.print_line(f"  {index:>2}. {character.name}")
    choice = _get_numeric_choice(f"  {tr('enter_character_number')}", len(characters), ctx=ctx)
    if choice is None:
        return
    character = characters[choice]
    _show_combat_log_entries(
        sim,
        build_combat_log_index(sim.world, character_id=character.char_id),
        ctx,
        title=tr("combat_logs_character_header", name=character.name),
    )


def _show_combat_log_entries(
    sim: Any,
    entries: tuple[CombatLogEntryView, ...],
    ctx: UIContext,
    *,
    title: str | None = None,
    limit: int = 30,
) -> None:
    shown = entries[:limit]
    ctx.out.print_line()
    ctx.out.print_heading(f"  {title or tr('combat_logs_header')}")
    if not shown:
        ctx.out.print_dim(f"  {tr('combat_logs_empty')}")
        ctx.inp.pause()
        return
    for index, entry in enumerate(shown, 1):
        ctx.out.print_line(f"  {index:>2}. {_entry_summary(sim, entry)}")
    if len(entries) > limit:
        ctx.out.print_dim(f"  {tr('combat_logs_truncated', count=len(entries) - limit)}")
    choice = _get_numeric_choice(f"  {tr('combat_logs_choose_detail')}", len(shown), ctx=ctx)
    if choice is None:
        return
    _show_combat_log_detail(sim, shown[choice], ctx)


def _show_combat_log_detail(sim: Any, entry: CombatLogEntryView, ctx: UIContext) -> None:
    ctx.out.print_line()
    ctx.out.print_heading(f"  {_entry_summary(sim, entry)}")
    if entry.source_kind == "adventure_combat":
        for line in combat_log_lines_for_adventure_entry(entry.source, sim.world):
            ctx.out.print_dim(f"  {line}")
    else:
        ctx.out.print_line(f"  {render_event_record(entry.source, world=sim.world)}")
        for line in combat_log_lines_for_event(entry.source):
            ctx.out.print_dim(f"  {line}")
    ctx.inp.pause()


def _entry_summary(sim: Any, entry: CombatLogEntryView) -> str:
    location = sim.world.location_name(entry.location_id) if entry.location_id else tr("combat_log_unknown")
    event_type_key = f"event_type_{entry.source_kind}"
    kind = tr(event_type_key)
    if kind == event_type_key:
        kind = entry.source_kind
    return tr(
        "combat_logs_entry",
        date=_date_label(entry),
        kind=kind,
        title=entry.title,
        location=location,
        rounds=entry.round_count,
    )


def _date_label(entry: CombatLogEntryView) -> str:
    if entry.day > 0 and entry.month > 0:
        return tr("event_log_prefix_day", year=entry.year, month=entry.month, day=entry.day)
    if entry.month > 0:
        return tr("event_log_prefix_month", year=entry.year, month=entry.month)
    return tr("event_log_prefix", year=entry.year)

"""Simulation construction and advancement helpers for CLI screens."""

from __future__ import annotations

import time
from typing import Any

from ..character_creator import CharacterCreator
from ..i18n import tr
from ..simulator import Simulator
from ..world import World
from .ui_context import UIContext, _default_ctx


def _build_default_world(num_characters: int = 12, seed: int | None = None) -> World:
    world = World()
    creator = CharacterCreator()
    location_ids = [loc.id for loc in world.grid.values() if loc.region_type != "dungeon"]

    import random as _random

    rng: Any = _random.Random(seed) if seed is not None else _random
    for _ in range(num_characters):
        char = creator.create_random(rng=rng)
        char.location_id = rng.choice(location_ids)
        world.add_character(char)
    return world


def _run_simulation(world: World, years: int, ctx: UIContext | None = None) -> Simulator:
    ctx = _default_ctx(ctx)
    out = ctx.out
    out.print_line()
    out.print_heading(f"  {tr('running_simulation_details', years=years, events=8)}")
    sim = Simulator(world, events_per_year=8, world_changes_per_year=1)
    for _ in range(years):
        sim.advance_years(1)
        alive = sum(1 for c in world.characters if c.alive)
        out.print_line(
            f"  {tr('year_label')} {world.year}  |  {out.format_status(str(alive), True)} {tr('alive')}"
        )
    out.print_success(f"  {tr('simulation_complete')}")
    return sim


def _advance_simulation(sim: Simulator, years: int, ctx: UIContext | None = None) -> None:
    if years <= 0:
        return
    ctx = _default_ctx(ctx)
    out = ctx.out

    out.print_line()
    out.print_heading(f"  {tr('advancing_simulation_years', years=years)}")
    for _ in range(years):
        sim.advance_years(1)
        pending = len(sim.get_pending_adventure_choices())
        alive = sum(1 for c in sim.world.characters if c.alive)
        out.print_line(
            f"  {tr('year_label')} {sim.world.year}  |  "
            f"{out.format_status(str(alive), True)} {tr('alive')}  |  "
            f"{pending} {tr('pending_choices')}"
        )
    out.print_success(f"  {tr('simulation_advanced_to_year', year=sim.world.year)}")


def _advance_days(
    sim: Simulator,
    days: int,
    ctx: UIContext | None = None,
    *,
    live: bool = False,
    delay_seconds: float = 0.0,
) -> None:
    if days <= 0:
        return
    ctx = _default_ctx(ctx)
    out = ctx.out

    out.print_line()
    out.print_heading(f"  {tr('advancing_simulation_days', days=days)}")
    for _ in range(days):
        year = sim.world.year
        month = sim.current_month
        day = sim.current_day
        before_events = len(sim.world.event_records)
        sim.advance_days(1)
        new_events = len(sim.world.event_records) - before_events
        if live:
            out.print_line(_daily_progress_line(sim, year, month, day, new_events))
            _print_daily_event_highlights(sim, before_events, ctx=ctx)
            if delay_seconds > 0:
                time.sleep(delay_seconds)
    if not live:
        alive = sum(1 for c in sim.world.characters if c.alive)
        pending = len(sim.get_pending_adventure_choices())
        out.print_line(
            f"  {_simulation_date_label(sim, sim.world.year, sim.current_month, sim.current_day)}  |  "
            f"{out.format_status(str(alive), True)} {tr('alive')}  |  "
            f"{pending} {tr('pending_choices')}"
        )
    out.print_success(
        f"  {tr('simulation_advanced_to_date', date=_simulation_date_label(sim, sim.world.year, sim.current_month, sim.current_day))}"  # noqa: E501
    )


def _advance_daily_live(sim: Simulator, ctx: UIContext | None = None, *, days: int = 30) -> None:
    """Advance a short window one day at a time, printing each tick."""
    _advance_days(sim, days, ctx=ctx, live=True, delay_seconds=0.03)


def _daily_progress_line(sim: Simulator, year: int, month: int, day: int, new_events: int) -> str:
    alive = sum(1 for c in sim.world.characters if c.alive)
    pending = len(sim.get_pending_adventure_choices())
    return (
        f"  {tr('daily_tick_line', date=_simulation_date_label(sim, year, month, day), events=new_events)}  |  "
        f"{sim.world.name}  |  {alive} {tr('alive')}  |  {pending} {tr('pending_choices')}"
    )


def _print_daily_event_highlights(sim: Simulator, start_index: int, ctx: UIContext) -> None:
    from ..event_rendering import render_event_record

    new_records = sim.world.event_records[start_index:]
    for record in new_records[-3:]:
        ctx.out.print_dim(f"    - {render_event_record(record, world=sim.world)}")


def _simulation_date_label(sim: Simulator, year: int, month: int, day: int) -> str:
    month_name = sim.world.month_display_name_for_date(year, month, day)
    return tr("simulation_date_label", year=year, month=month_name, day=day)


def _format_auto_pause_context(pause_context: dict[str, Any]) -> str:
    actor = pause_context.get("character", "")
    location = pause_context.get("location", "")
    if actor and location:
        return tr("auto_pause_context", actor=actor, location=location)
    if location:
        return tr("auto_pause_context_location", location=location)
    if actor:
        return tr("auto_pause_context_actor", actor=actor)
    return ""


def _route_target_label(world: Any, route_id: str) -> str:
    for route in getattr(world, "routes", []):
        if getattr(route, "route_id", "") != route_id:
            continue
        from_id = getattr(route, "from_site_id", "")
        to_id = getattr(route, "to_site_id", "")
        if hasattr(world, "location_name") and from_id and to_id:
            return f"{world.location_name(from_id)} - {world.location_name(to_id)}"
        return route_id
    return route_id


def _format_auto_pause_action_target(world: Any, action: dict[str, Any]) -> str:
    target_type = action.get("target_type", "")
    target_id = action.get("target_id", "")
    if not target_type or not target_id:
        return ""
    if target_type == "location" and hasattr(world, "location_name"):
        target = world.location_name(target_id)
    elif target_type == "route":
        target = _route_target_label(world, target_id)
    else:
        target = str(target_id)
    return tr(f"auto_pause_action_target_{target_type}", target=target)


def _advance_auto(sim: Simulator, ctx: UIContext | None = None) -> None:
    """Run simulation until auto-pause triggers (design doc section 4.4)."""
    ctx = _default_ctx(ctx)
    out = ctx.out

    out.print_line()
    out.print_heading(f"  {tr('advancing_auto')}")
    result = sim.advance_until_pause(max_years=12)
    months = result["months_advanced"]
    reason = result["pause_reason"]
    alive = sum(1 for c in sim.world.characters if c.alive)
    pending = len(sim.get_pending_adventure_choices())
    out.print_line(
        f"  {tr('year_label')} {sim.world.year}  |  "
        f"{out.format_status(str(alive), True)} {tr('alive')}  |  "
        f"{pending} {tr('pending_choices')}"
    )
    reason_key = f"auto_pause_{reason}"
    reason_text = tr(reason_key)
    supplemental = result.get("supplemental_reasons", [])
    pause_context = result.get("pause_context", {})
    years = months // sim.world.months_per_year
    remainder_months = months % sim.world.months_per_year
    if remainder_months == 0:
        out.print_warning(f"  {tr('auto_paused_after', years=years)}: {reason_text}")
    else:
        out.print_warning(
            f"  {tr('auto_paused_after_months', years=years, months=remainder_months)}: {reason_text}"
        )
    context_text = _format_auto_pause_context(pause_context)
    if context_text:
        out.print_dim(f"  {context_text}")
    subreasons = result.get("pause_subreasons", [])
    if subreasons:
        out.print_dim(f"  {tr('auto_pause_subreasons')}")
        for item in subreasons[:3]:
            subreason_key = item.get("key", "auto_window_elapsed")
            actor = item.get("character", "-") or "-"
            location = item.get("location", "-") or "-"
            out.print_dim(
                f"    - {tr(f'auto_pause_subreason_{subreason_key}', actor=actor, location=location)}"
            )
    if supplemental:
        extras = ", ".join(tr(f"auto_pause_{r}") for r in supplemental[:3])
        out.print_dim(f"  {tr('auto_pause_supplemental', reasons=extras)}")
    recommendations = result.get("recommended_actions", [])
    if recommendations:
        out.print_dim(f"  {tr('auto_pause_recommendations')}")
        for item in recommendations[:3]:
            action_key = item.get("key", "review_recent_events")
            actor = item.get("character", "-") or "-"
            location = item.get("location", "-") or "-"
            target_text = _format_auto_pause_action_target(sim.world, item)
            suffix = f" ({target_text})" if target_text else ""
            out.print_dim(
                f"    - {tr(f'auto_pause_recommendation_{action_key}', actor=actor, location=location)}{suffix}"
            )

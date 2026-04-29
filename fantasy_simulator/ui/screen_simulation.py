"""Simulation construction and advancement helpers for CLI screens."""

from __future__ import annotations

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
    sim = Simulator(world, events_per_year=8)
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
    if pause_context:
        actor = pause_context.get("character", "-")
        location = pause_context.get("location", "-")
        out.print_dim(f"  {tr('auto_pause_context', actor=actor, location=location)}")
    if supplemental:
        extras = ", ".join(tr(f"auto_pause_{r}") for r in supplemental[:3])
        out.print_dim(f"  {tr('auto_pause_supplemental', reasons=extras)}")

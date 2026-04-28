"""
screens.py - Screen / menu functions and simulation helpers for the CLI.

All screen functions accept an optional ``ctx: UIContext`` parameter.
When ``None`` (the default), a standard stdin/stdout context is created
internally — so **all existing call-sites keep working unchanged**.

Internally, every I/O operation goes through ``ctx.inp`` (InputBackend)
and ``ctx.out`` (RenderBackend).  This makes the entire UI layer
testable with recording / buffer backends and swappable to Rich,
prompt_toolkit, or Textual in future phases.
"""

from __future__ import annotations

from typing import Any, List, Optional

from ..character import Character
from ..character_creator import CharacterCreator
from ..content.setting_bundle import default_aethoria_bundle
from ..i18n import set_locale, tr, tr_term
from ..persistence.save_load import load_simulation, save_simulation
from ..simulator import Simulator
from ..world import World
from .presenters import LanguagePresenter
from .screen_adventures import (  # noqa: F401
    _party_display_names as _party_display_names,
    _resolve_pending_adventure_choice as _resolve_pending_adventure_choice,
    _show_adventure_details as _show_adventure_details,
    _show_adventure_summaries as _show_adventure_summaries,
)
from .screen_history import (  # noqa: F401
    _month_season_hint as _month_season_hint,
    _show_location_history as _show_location_history,
    _show_monthly_report as _show_monthly_report,
    _show_single_story as _show_single_story,
)
from .screen_map import (  # noqa: F401
    _build_detail_memory_payload as _build_detail_memory_payload,
    _build_detail_observation_payload as _build_detail_observation_payload,
    _build_region_memory_payloads as _build_region_memory_payloads,
    _region_drill_loop as _region_drill_loop,
    _render_location_detail_for_location as _render_location_detail_for_location,
    _render_region_map_for_location as _render_region_map_for_location,
    _show_detail_for_location as _show_detail_for_location,
    _show_world_map as _show_world_map,
    render_world_map_views_for_location as render_world_map_views_for_location,
)
from .screen_input import _get_numeric_choice as _get_numeric_choice, _read_bounded_int  # noqa: F401
from .ui_helpers import fit_display_width

from .ui_context import UIContext, _default_ctx


# ---------------------------------------------------------------------------
# Simulation helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Result / post-simulation viewers
# ---------------------------------------------------------------------------

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


def _show_roster(world: World, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out

    out.print_line()
    out.print_separator()
    header = (
        "  "
        + fit_display_width(tr("roster_header_name"), 22)
        + " "
        + fit_display_width(tr("roster_header_race_job"), 22)
        + " "
        + fit_display_width(tr("roster_header_age"), 4)
        + "  "
        + fit_display_width(tr("stat_str"), 4)
        + fit_display_width(tr("stat_int"), 4)
        + fit_display_width(tr("stat_dex"), 4)
        + "  "
        + fit_display_width(tr("roster_header_status"), 10)
        + "  "
        + fit_display_width(tr("roster_header_location"), 20)
    )
    out.print_heading(header)
    out.print_separator()
    for c in world.characters:
        status_text = fit_display_width(
            tr("status_alive") if c.alive else tr("status_dead"),
            10,
        )
        status = out.format_status(status_text, c.alive)
        name_trunc = fit_display_width(c.name, 22)
        racejob = fit_display_width(f"{tr_term(c.race)} {tr_term(c.job)}", 22)
        loc_trunc = fit_display_width(world.location_name(c.location_id), 20)
        out.print_line(
            f"  {name_trunc} {racejob} {c.age:>4}  "
            f"{c.strength:>4}{c.intelligence:>4}{c.dexterity:>4}  "
            f"{status}  {loc_trunc}"
        )
    out.print_separator()
    ctx.inp.pause()


# ---------------------------------------------------------------------------
# Save / Load UI
# ---------------------------------------------------------------------------

def _save_simulation_snapshot(sim: Simulator, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out

    out.print_line()
    default_name = "simulation_snapshot.json"
    path = ctx.inp.read_line(f"  {tr('save_path_prompt', default_name=default_name)}").strip() or default_name
    if save_simulation(sim, path):
        out.print_success(f"  {tr('save_succeeded', path=path)}")
    else:
        out.print_error(f"  {tr('save_failed', error=tr('save_error_io'))}")
    ctx.inp.pause()


def _load_simulation_snapshot(ctx: UIContext | None = None) -> Optional[Simulator]:
    ctx = _default_ctx(ctx)
    out = ctx.out

    out.print_line()
    out.print_separator("=")
    out.print_heading(f"  {tr('load_snapshot_header')}")
    out.print_separator("=")
    default_name = "simulation_snapshot.json"
    path = ctx.inp.read_line(f"  {tr('load_path_prompt', default_name=default_name)}").strip() or default_name
    sim = load_simulation(path)
    if sim is None:
        out.print_error(f"  {tr('load_failed', error=tr('load_error_corrupted'))}")
        ctx.inp.pause()
        return None

    out.print_success(f"  {tr('load_succeeded', path=path)}")
    return sim


# ---------------------------------------------------------------------------
# Language selection
# ---------------------------------------------------------------------------

def _select_language(ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    action = ctx.choose_key(
        tr("load_language_prompt"),
        [
            ("ja", tr("language_option_ja")),
            ("en", tr("language_option_en")),
        ],
        default="1",
    )
    if action == "ja":
        set_locale("ja")
        ctx.out.print_success(f"  {tr('language_set_ja')}")
    else:
        set_locale("en")
        ctx.out.print_success(f"  {tr('language_set_en')}")


# ---------------------------------------------------------------------------
# Top-level screen functions
# ---------------------------------------------------------------------------

def screen_new_simulation(ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out

    out.print_line()
    out.print_separator("=")
    out.print_heading(f"  {tr('new_simulation')} - {tr('default_world')}")
    out.print_separator("=")

    num = _read_bounded_int(
        f"  > {tr('number_of_characters')}: ",
        default=12,
        minimum=4,
        maximum=30,
        ctx=ctx,
    )
    years = _read_bounded_int(
        f"  > {tr('simulation_length')}: ",
        default=20,
        minimum=1,
        maximum=200,
        ctx=ctx,
    )

    world = _build_default_world(num_characters=num)
    out.print_line()
    out.print_success(f"  {tr('world_created', world=world.name, count=num)}")
    sim = _run_simulation(world, years, ctx=ctx)
    _show_results(sim, ctx=ctx)


def screen_custom_simulation(ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out
    inp = ctx.inp

    out.print_line()
    out.print_separator("=")
    out.print_heading(f"  {tr('custom_character_simulation')}")
    out.print_separator("=")
    creator = CharacterCreator()
    world = World()
    custom_chars: List[Character] = []

    while True:
        action = ctx.choose_key(
            tr("add_character_or_start"),
            [
                ("create_interactive", tr("create_character_interactively")),
                ("create_random", tr("create_random_character")),
                ("create_template", tr("create_from_template")),
                ("start_simulation", tr("start_simulation_with_roster", count=len(custom_chars))),
            ],
        )

        if action == "create_interactive":
            char = creator.create_interactive(ctx=ctx)
            world.add_character(char)
            custom_chars.append(char)
            out.print_line()
            out.print_success(f"  {tr('character_added', name=char.name)}")
        elif action == "create_random":
            char = creator.create_random()
            world.add_character(char)
            custom_chars.append(char)
            msg = tr('random_character_added', name=char.name, race=tr_term(char.race), job=tr_term(char.job))
            out.print_line()
            out.print_success(f"  {msg}")
        elif action == "create_template":
            templates = creator.list_templates()
            if not templates:
                out.print_warning(f"  {tr('no_templates_available')}")
                continue
            out.print_line(f"\n  {tr('available_templates')}: " + ", ".join(templates))
            tmpl_name = inp.read_line(f"  > {tr('template_name')}: ").strip()
            char_name = inp.read_line(f"  > {tr('character_name_optional')}: ").strip() or None
            try:
                char = creator.create_from_template(tmpl_name, name=char_name)
                world.add_character(char)
                custom_chars.append(char)
                out.print_line()
                msg = tr(
                    'template_character_added',
                    name=char.name, race=tr_term(char.race), job=tr_term(char.job),
                )
                out.print_success(f"  {msg}")
            except ValueError as exc:
                out.print_error(f"  {tr('error_prefix')}: {exc}")
        else:
            if not custom_chars:
                out.print_warning(f"  {tr('need_one_character')}")
                for _ in range(5):
                    world.add_character(creator.create_random())

            fill = max(0, 8 - len(world.characters))
            for _ in range(fill):
                world.add_character(creator.create_random())

            years = _read_bounded_int(
                f"  > {tr('simulation_length')}: ",
                default=20,
                minimum=1,
                maximum=200,
                ctx=ctx,
            )

            sim = _run_simulation(world, years, ctx=ctx)
            _show_results(sim, ctx=ctx)
            break


def screen_world_lore(ctx: UIContext | None = None, *, world: World | None = None) -> None:
    """Show lore using the active world's bundle, or the default bundle pre-sim."""

    ctx = _default_ctx(ctx)
    out = ctx.out
    bundle = world.setting_bundle if world is not None else default_aethoria_bundle()
    world_definition = bundle.world_definition
    creator = CharacterCreator(setting_bundle=bundle)
    lore_text = world_definition.lore_text

    out.print_line()
    out.print_separator("=")
    out.print_heading(f"  {tr('world_lore')}")
    out.print_separator("=")
    out.print_wrapped(lore_text)
    out.print_line()
    out.print_heading(f"  {tr('races_of_aethoria')}")
    out.print_separator()
    for race_name, race_description, stat_bonuses in creator.race_entries:
        bonus_str = ", ".join(
            f"{stat} {'+' if value >= 0 else ''}{value}"
            for stat, value in stat_bonuses.items()
            if value != 0
        )
        out.print_highlighted(f"  {tr_term(race_name)}")
        out.print_wrapped(race_description)
        if bonus_str:
            out.print_dim(f"    {tr('bonuses')}: {bonus_str}")
        out.print_line()
    out.print_heading(f"  {tr('jobs_classes')}")
    out.print_separator()
    for job_name, job_description, primary_skills in creator.job_entries:
        skills_str = ', '.join(tr_term(skill) for skill in primary_skills)
        out.print_highlighted(f"  {tr_term(job_name)}")
        out.print_line(f"    {tr('primary_skills_label')}: {skills_str}")
        out.print_wrapped(job_description)
        out.print_line()
    language_statuses = world.language_status() if world is not None else _build_default_language_status(bundle)
    if language_statuses:
        out.print_heading(f"  {tr('languages_header')}")
        out.print_separator()
        for status in language_statuses:
            for line in LanguagePresenter.render_status(status):
                out.print_line(line)
            out.print_line()
    ctx.inp.pause()


def _build_default_language_status(bundle: Any) -> List[dict]:
    """Build language status for bundle lore without requiring a simulated world."""
    from ..language.engine import LanguageEngine
    from ..world_language import language_status

    engine = LanguageEngine(bundle.world_definition)
    return language_status(bundle.world_definition, engine, [])

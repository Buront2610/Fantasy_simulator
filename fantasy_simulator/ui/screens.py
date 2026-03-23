"""
screens.py - Screen / menu functions and simulation helpers for the CLI.
"""

from __future__ import annotations

from typing import Any, List, Optional

from character import Character
from character_creator import CharacterCreator
from i18n import set_locale, tr, tr_term
from save_load import load_simulation, save_simulation
from simulator import Simulator
from ui_helpers import (
    _choose_key,
    _hr,
    _pause,
    _print_wrapped,
    bold,
    cyan,
    dim,
    fit_display_width,
    green,
    red,
    yellow,
)
from world import World
from world_data import JOBS, RACES, WORLD_LORE


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def _get_numeric_choice(prompt: str, count: int) -> Optional[int]:
    """Prompt the user for a 1-based index and return 0-based index, or None."""
    raw = input(prompt).strip()
    if not raw:
        return None
    if not raw.isdigit():
        print(yellow(f"  {tr('invalid_input')}"))
        return None
    idx = int(raw) - 1
    if not (0 <= idx < count):
        print(yellow(f"  {tr('invalid_input')}"))
        return None
    return idx


def _month_season_hint() -> str:
    """Return a compact month -> season hint for monthly report selection."""
    season_by_month = {
        1: "winter", 2: "winter", 3: "spring",
        4: "spring", 5: "spring", 6: "summer",
        7: "summer", 8: "summer", 9: "autumn",
        10: "autumn", 11: "autumn", 12: "winter",
    }
    return ", ".join(
        f"{month} ({tr('season_' + season_by_month[month])})"
        for month in range(1, 13)
    )


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


def _run_simulation(world: World, years: int) -> Simulator:
    print()
    print(f"  {bold(tr('running_simulation_details', years=years, events=8))}")
    sim = Simulator(world, events_per_year=8)
    for _ in range(years):
        sim.advance_years(1)
        alive = sum(1 for c in world.characters if c.alive)
        print(
            f"  {tr('year_label')} {world.year}  |  {green(str(alive))} {tr('alive')}",
            end="\r",
        )
    print()
    print(f"  {green('*')}  {tr('simulation_complete')}")
    return sim


def _advance_simulation(sim: Simulator, years: int) -> None:
    if years <= 0:
        return

    print()
    print(f"  {bold(tr('advancing_simulation'))} (+{years} years)")
    for _ in range(years):
        sim.advance_years(1)
        pending = len(sim.get_pending_adventure_choices())
        alive = sum(1 for c in sim.world.characters if c.alive)
        print(
            f"  {tr('year_label')} {sim.world.year}  |  {green(str(alive))} {tr('alive')}  |  "
            f"{yellow(str(pending))} {tr('pending_choices')}",
            end="\r",
        )
    print()
    print(f"  {green('*')}  {tr('simulation_advanced_to_year', year=sim.world.year)}")


def _advance_auto(sim: Simulator) -> None:
    """Run simulation until auto-pause triggers (design doc section 4.4)."""
    print()
    print(f"  {bold(tr('advancing_auto'))}")
    result = sim.advance_until_pause(max_years=12)
    years = result["years_advanced"]
    reason = result["pause_reason"]
    alive = sum(1 for c in sim.world.characters if c.alive)
    pending = len(sim.get_pending_adventure_choices())
    print(
        f"  {tr('year_label')} {sim.world.year}  |  {green(str(alive))} {tr('alive')}  |  "
        f"{yellow(str(pending))} {tr('pending_choices')}"
    )
    reason_key = f"auto_pause_{reason}"
    reason_text = tr(reason_key)
    print(f"  {yellow('!')}  {tr('auto_paused_after', years=years)}: {reason_text}")


# ---------------------------------------------------------------------------
# Result / post-simulation viewers
# ---------------------------------------------------------------------------

def _show_results(sim: Simulator) -> None:
    world = sim.world
    while True:
        print("\n" + _hr("="))
        print(bold(f"  {tr('post_results')}"))
        print(_hr("="))
        action = _choose_key(
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
                ("back_to_main", tr("back_to_main")),
            ],
        )

        if action == "advance_1_year":
            _advance_simulation(sim, 1)
        elif action == "advance_5_years":
            _advance_simulation(sim, 5)
        elif action == "advance_auto":
            _advance_auto(sim)
        elif action == "yearly_report":
            print()
            print(sim.get_latest_yearly_report())
            _pause()
        elif action == "monthly_report":
            _show_monthly_report(sim)
        elif action == "world_map":
            print()
            print(world.render_map())
            _pause()
        elif action == "character_roster":
            _show_roster(world)
        elif action == "event_log_last_30":
            print()
            for entry in sim.get_event_log(last_n=30):
                print(f"  - {entry}")
            _pause()
        elif action == "full_event_log":
            print()
            for entry in sim.get_event_log():
                print(f"  - {entry}")
            _pause()
        elif action == "adventure_summaries":
            _show_adventure_summaries(sim)
        elif action == "adventure_details":
            _show_adventure_details(sim)
        elif action == "resolve_pending_choice":
            _resolve_pending_adventure_choice(sim)
        elif action == "save_snapshot":
            _save_simulation_snapshot(sim)
        elif action == "character_story":
            _show_single_story(sim)
        elif action == "all_character_stories":
            print()
            print(sim.get_all_stories())
            _pause()
        elif action == "simulation_summary":
            print()
            print(sim.get_summary())
            _pause()
        else:
            break


def _show_monthly_report(sim: Simulator) -> None:
    """Show a monthly report for the latest completed year.

    The user picks a month (1-12) within that year.  Reports are
    derived solely from event records, so content stays stable.
    """
    year = sim.get_latest_completed_report_year()
    print()
    print(f"  {tr('year_label')}: {year}")
    print(f"  {_month_season_hint()}")
    month_idx = _get_numeric_choice(
        f"  {tr('monthly_report')} (1-12): ", 12,
    )
    if month_idx is None:
        return
    month = month_idx + 1
    print()
    print(sim.get_monthly_report(year, month))
    _pause()


def _show_roster(world: World) -> None:
    print()
    print(_hr())
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
    print(bold(header))
    print(_hr())
    for c in world.characters:
        status_text = fit_display_width(
            tr("status_alive") if c.alive else tr("status_dead"),
            10,
        )
        status = green(status_text) if c.alive else red(status_text)
        name_trunc = fit_display_width(c.name, 22)
        racejob = fit_display_width(f"{tr_term(c.race)} {tr_term(c.job)}", 22)
        loc_trunc = fit_display_width(world.location_name(c.location_id), 20)
        print(
            f"  {name_trunc} {racejob} {c.age:>4}  "
            f"{c.strength:>4}{c.intelligence:>4}{c.dexterity:>4}  "
            f"{status}  {loc_trunc}"
        )
    print(_hr())
    _pause()


def _show_single_story(sim: Simulator) -> None:
    world = sim.world
    print()
    for i, c in enumerate(world.characters, 1):
        status = green(tr("status_alive")) if c.alive else red(tr("status_dead"))
        print(f"  {i:>2}. [{status}] {c.name} ({tr_term(c.race)} {tr_term(c.job)}, {tr('age_short_label')} {c.age})")
    print()
    idx = _get_numeric_choice(f"  {tr('enter_character_number')}", len(world.characters))
    if idx is None:
        return
    char = world.characters[idx]
    print()
    print(sim.get_character_story(char.char_id))
    _pause()


def _show_adventure_summaries(sim: Simulator) -> None:
    runs = list(sim.world.completed_adventures) + list(sim.world.active_adventures)
    print()
    if not runs:
        print(dim(f"  {tr('no_adventures_recorded')}"))
        _pause()
        return

    print(_hr())
    print(bold(f"  {tr('adventure_summaries_header')}"))
    print(_hr())
    for i, run in enumerate(runs, 1):
        status = tr(f"outcome_{run.outcome}") if run.outcome else tr(f"state_{run.state}")
        loot = (
            f" | {tr('loot_label')}: {', '.join(tr_term(item) for item in run.loot_summary)}"
            if run.loot_summary else ""
        )
        injury = (
            f" | {tr('injury_label')}: {tr(f'injury_status_{run.injury_status}')}"
            if run.injury_status != "none" else ""
        )
        origin_name = sim.world.location_name(run.origin)
        dest_name = sim.world.location_name(run.destination)
        print(
            f"  {i:>2}. {run.character_name} | {origin_name} -> {dest_name} "
            f"| {status}{injury}{loot}"
        )
    print(_hr())
    _pause()


def _show_adventure_details(sim: Simulator) -> None:
    runs = list(sim.world.completed_adventures) + list(sim.world.active_adventures)
    print()
    if not runs:
        print(dim(f"  {tr('no_adventures_to_inspect')}"))
        _pause()
        return

    for i, run in enumerate(runs, 1):
        status = tr(f"outcome_{run.outcome}") if run.outcome else tr(f"state_{run.state}")
        dest_name = sim.world.location_name(run.destination)
        print(f"  {i:>2}. {run.character_name} {tr('at_label')} {dest_name} [{status}]")
    print()
    idx = _get_numeric_choice(f"  {tr('enter_adventure_number')}", len(runs))
    if idx is None:
        return

    run = runs[idx]
    print()
    print(_hr())
    print(bold(f"  {tr('adventure_detail_header', name=run.character_name)}"))
    print(_hr())
    print(f"  {tr('id_label'):<11}: {run.adventure_id}")
    print(f"  {tr('route'):<11}: {sim.world.location_name(run.origin)} -> {sim.world.location_name(run.destination)}")
    print(f"  {tr('state'):<11}: {tr(f'state_{run.state}')}")
    print(f"  {tr('outcome'):<11}: {tr(f'outcome_{run.outcome}') if run.outcome else tr('unresolved')}")
    print(f"  {tr('injury'):<11}: {tr(f'injury_status_{run.injury_status}')}")
    print(f"  {tr('steps'):<11}: {run.steps_taken}")
    if run.loot_summary:
        print(f"  {tr('discoveries'):<11}: {', '.join(tr_term(item) for item in run.loot_summary)}")
    print()
    for entry in sim.get_adventure_details(run.adventure_id):
        print(f"  - {entry}")
    _pause()


def _resolve_pending_adventure_choice(sim: Simulator) -> None:
    pending = sim.get_pending_adventure_choices()
    print()
    if not pending:
        print(dim(f"  {tr('no_pending_choices')}"))
        _pause()
        return

    for i, item in enumerate(pending, 1):
        options = ", ".join(tr(f"choice_{option}") for option in item["options"])
        default_label = tr(f"choice_{item['default_option']}")
        print(
            f"  {i:>2}. {item['character_name']} | {item['prompt']} "
            f"[{options}] {tr('choice_default_hint', default_option=default_label)}"
        )
    print()

    idx = _get_numeric_choice(f"  {tr('enter_pending_choice_number')}", len(pending))
    if idx is None:
        return

    item = pending[idx]
    options = item["options"]
    print()
    for i, option in enumerate(options, 1):
        default_marker = f" {tr('default_marker')}" if option == item["default_option"] else ""
        print(f"  {i:>2}. {tr(f'choice_{option}')}{default_marker}")
    option_idx = _get_numeric_choice(f"  {tr('enter_option_number')}", len(options))
    chosen_option = options[option_idx] if option_idx is not None else None

    resolved = sim.resolve_adventure_choice(item["adventure_id"], option=chosen_option)
    print()
    if resolved:
        print(green(f"  {tr('choice_resolved')}"))
    else:
        print(red(f"  {tr('choice_resolve_failed')}"))
    _pause()


# ---------------------------------------------------------------------------
# Save / Load UI
# ---------------------------------------------------------------------------

def _save_simulation_snapshot(sim: Simulator) -> None:
    print()
    default_name = "simulation_snapshot.json"
    path = input(f"  {tr('save_path_prompt', default_name=default_name)}").strip() or default_name
    if save_simulation(sim, path):
        print(green(f"  {tr('save_succeeded', path=path)}"))
    else:
        print(red(f"  {tr('save_failed', error=tr('save_error_io'))}"))
    _pause()


def _load_simulation_snapshot() -> Optional[Simulator]:
    print("\n" + _hr("="))
    print(bold(f"  {tr('load_snapshot_header')}"))
    print(_hr("="))
    default_name = "simulation_snapshot.json"
    path = input(f"  {tr('load_path_prompt', default_name=default_name)}").strip() or default_name
    sim = load_simulation(path)
    if sim is None:
        print(red(f"  {tr('load_failed', error=tr('load_error_corrupted'))}"))
        _pause()
        return None

    print(green(f"  {tr('load_succeeded', path=path)}"))
    return sim


# ---------------------------------------------------------------------------
# Language selection
# ---------------------------------------------------------------------------

def _select_language() -> None:
    action = _choose_key(
        tr("load_language_prompt"),
        [
            ("ja", tr("language_option_ja")),
            ("en", tr("language_option_en")),
        ],
        default="1",
    )
    if action == "ja":
        set_locale("ja")
        print(green(f"  {tr('language_set_ja')}"))
    else:
        set_locale("en")
        print(green(f"  {tr('language_set_en')}"))


# ---------------------------------------------------------------------------
# Top-level screen functions
# ---------------------------------------------------------------------------

def screen_new_simulation() -> None:
    print("\n" + _hr("="))
    print(bold(f"  {tr('new_simulation')} - {tr('default_world')}"))
    print(_hr("="))

    raw = input(f"  > {tr('number_of_characters')}: ").strip()
    num = int(raw) if raw.isdigit() else 12
    num = max(4, min(30, num))

    raw = input(f"  > {tr('simulation_length')}: ").strip()
    years = int(raw) if raw.isdigit() else 20
    years = max(1, min(200, years))

    world = _build_default_world(num_characters=num)
    print(f"\n  {green('*')}  {tr('world_created', world=world.name, count=num)}")
    sim = _run_simulation(world, years)
    _show_results(sim)


def screen_custom_simulation() -> None:
    print("\n" + _hr("="))
    print(bold(f"  {tr('custom_character_simulation')}"))
    print(_hr("="))
    creator = CharacterCreator()
    world = World()
    custom_chars: List[Character] = []

    while True:
        action = _choose_key(
            tr("add_character_or_start"),
            [
                ("create_interactive", tr("create_character_interactively")),
                ("create_random", tr("create_random_character")),
                ("create_template", tr("create_from_template")),
                ("start_simulation", tr("start_simulation_with_roster", count=len(custom_chars))),
            ],
        )

        if action == "create_interactive":
            char = creator.create_interactive()
            world.add_character(char)
            custom_chars.append(char)
            print(f"\n  {green('*')}  {tr('character_added', name=char.name)}")
        elif action == "create_random":
            char = creator.create_random()
            world.add_character(char)
            custom_chars.append(char)
            msg = tr('random_character_added', name=char.name, race=tr_term(char.race), job=tr_term(char.job))
            print(f"\n  {green('*')}  {msg}")
        elif action == "create_template":
            templates = CharacterCreator.list_templates()
            print(f"\n  {tr('available_templates')}: " + ", ".join(templates))
            tmpl_name = input(f"  > {tr('template_name')}: ").strip()
            char_name = input(f"  > {tr('character_name_optional')}: ").strip() or None
            try:
                char = creator.create_from_template(tmpl_name, name=char_name)
                world.add_character(char)
                custom_chars.append(char)
                print(
                    f"\n  {green('*')}  "
                    f"{tr('template_character_added', name=char.name, race=tr_term(char.race), job=tr_term(char.job))}"
                )
            except ValueError as exc:
                print(red(f"  {tr('error_prefix')}: {exc}"))
        else:
            if not custom_chars:
                print(yellow(f"  {tr('need_one_character')}"))
                for _ in range(5):
                    world.add_character(creator.create_random())

            fill = max(0, 8 - len(world.characters))
            for _ in range(fill):
                world.add_character(creator.create_random())

            raw = input(f"  > {tr('simulation_length')}: ").strip()
            years = int(raw) if raw.isdigit() else 20
            years = max(1, min(200, years))

            sim = _run_simulation(world, years)
            _show_results(sim)
            break


def screen_world_lore() -> None:
    print("\n" + _hr("="))
    print(bold(f"  {tr('world_lore')}"))
    print(_hr("="))
    _print_wrapped(WORLD_LORE)
    print()
    print(bold(f"  {tr('races_of_aethoria')}"))
    print(_hr())
    for rname, rdesc, bonuses in RACES:
        bonus_str = ", ".join(
            f"{stat} {'+' if v >= 0 else ''}{v}" for stat, v in bonuses.items() if v != 0
        )
        print(f"  {cyan(rname)}")
        _print_wrapped(rdesc)
        if bonus_str:
            print(f"    {dim(tr('bonuses') + ':')} {bonus_str}")
        print()
    print(bold(f"  {tr('jobs_classes')}"))
    print(_hr())
    for jname, jdesc, jskills in JOBS:
        skills_str = ', '.join(tr_term(skill) for skill in jskills)
        print(f"  {cyan(tr_term(jname))}  |  {tr('primary_skills_label')}: {skills_str}")
        _print_wrapped(jdesc)
        print()
    _pause()

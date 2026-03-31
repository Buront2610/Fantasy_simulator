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

import shutil
from typing import Any, List, Optional

from ..character import Character
from ..character_creator import CharacterCreator
from ..content.setting_bundle import default_aethoria_bundle
from ..i18n import set_locale, tr, tr_term
from ..persistence.save_load import load_simulation, save_simulation
from ..simulator import Simulator
from .ui_helpers import fit_display_width
from ..world import World
from ..content.world_data import JOBS, RACES
from .presenters import AdventurePresenter, LocationPresenter, ReportPresenter
from .view_models import AdventureSummaryView, LocationHistoryView, build_monthly_report_card_view

from .ui_context import UIContext, _default_ctx


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------

def _get_numeric_choice(prompt: str, count: int, ctx: UIContext | None = None) -> Optional[int]:
    """Prompt the user for a 1-based index and return 0-based index, or None."""
    ctx = _default_ctx(ctx)
    raw = ctx.inp.read_line(prompt).strip()
    if not raw:
        return None
    if not raw.isdigit():
        ctx.out.print_warning(f"  {tr('invalid_input')}")
        return None
    idx = int(raw) - 1
    if not (0 <= idx < count):
        ctx.out.print_warning(f"  {tr('invalid_input')}")
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
    out.print_heading(f"  {tr('advancing_simulation')} (+{years} years)")
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
    years = months // 12
    remainder_months = months % 12
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


def _show_detail_for_location(
    world: World,
    info: Any,
    loc: Any,
    ctx: UIContext | None = None,
) -> None:
    """Render the detail panel for a single location."""
    from .map_renderer import render_location_detail

    ctx = _default_ctx(ctx)
    out = ctx.out
    inp = ctx.inp

    mem_list: list[str] = []
    if loc.memorial_ids:
        mems = world.get_memorials_for_location(loc.id)
        mem_list = [
            tr("memorial_entry", year=m.year, epitaph=m.epitaph)
            for m in mems
        ]
    recent_traces = list(reversed(loc.live_traces[-5:]))
    trace_list = [t.get("text", "") for t in recent_traces]
    out.print_line()
    out.print_line(render_location_detail(
        info, loc.id,
        memorials=mem_list or None,
        aliases=list(loc.aliases) or None,
        live_traces=trace_list or None,
    ))
    inp.pause()


def _region_drill_loop(
    world: World,
    info: Any,
    center_loc: Any,
    ctx: UIContext | None = None,
) -> None:
    """Region map loop allowing navigation to nearby sites.

    Shows the region centred on *center_loc*, then offers:

    * **detail** — pick any visible site to see its detail panel
    * **recenter** — pick any visible site and re-centre the region
    * **back** — return to the atlas overview
    """
    from .map_renderer import render_region_map

    ctx = _default_ctx(ctx)
    out = ctx.out

    # Build location_id → cell lookup once (stable across iterations)
    cell_by_id = {c.location_id: c for c in info.cells.values()}

    while True:
        # Build world memory data for region map enrichment (item 9)
        site_memorials: dict[str, list[str]] = {}
        site_aliases: dict[str, list[str]] = {}
        site_traces: dict[str, list[str]] = {}
        for loc in world.grid.values():
            if loc.memorial_ids:
                mems = world.get_memorials_for_location(loc.id)
                if mems:
                    site_memorials[loc.id] = [
                        tr("memorial_entry", year=m.year, epitaph=m.epitaph)
                        for m in mems[:3]
                    ]
            if loc.aliases:
                site_aliases[loc.id] = list(loc.aliases)[:3]
            if loc.live_traces:
                site_traces[loc.id] = [
                    t.get("text", "") for t in loc.live_traces[-3:]
                ]

        out.print_line()
        out.print_line(render_region_map(
            info, center_loc.id,
            site_memorials=site_memorials,
            site_aliases=site_aliases,
            site_traces=site_traces,
        ))

        # Build the visible-site list for the current region centre
        center_cell = None
        for c in info.cells.values():
            if c.location_id == center_loc.id:
                center_cell = c
                break
        if center_cell is None:
            break

        radius = 2
        x_min = max(0, center_cell.x - radius)
        x_max = min(info.width - 1, center_cell.x + radius)
        y_min = max(0, center_cell.y - radius)
        y_max = min(info.height - 1, center_cell.y + radius)

        visible_locs = []
        for loc in sorted(world.grid.values(), key=lambda lc: lc.canonical_name):
            cell = cell_by_id.get(loc.id)
            if cell and x_min <= cell.x <= x_max and y_min <= cell.y <= y_max:
                visible_locs.append(loc)

        out.print_line()
        for i, vloc in enumerate(visible_locs, 1):
            marker = "@" if vloc.id == center_loc.id else " "
            out.print_line(f"  {marker}{i}. {vloc.canonical_name} ({tr_term(vloc.region_type)})")

        sub = ctx.choose_key(
            tr("map_nav_prompt"),
            [
                ("detail", tr("map_nav_detail")),
                ("recenter", tr("map_nav_recenter")),
                ("back", tr("back_to_main")),
            ],
        )

        if sub == "detail":
            idx = _get_numeric_choice(
                f"  {tr('enter_location_number')}", len(visible_locs), ctx=ctx,
            )
            if idx is not None:
                _show_detail_for_location(world, info, visible_locs[idx], ctx=ctx)

        elif sub == "recenter":
            idx = _get_numeric_choice(
                f"  {tr('enter_location_number')}", len(visible_locs), ctx=ctx,
            )
            if idx is not None:
                center_loc = visible_locs[idx]
        else:
            break


def _show_world_map(sim: Simulator, ctx: UIContext | None = None) -> None:
    """Three-layer map navigation: overview -> region -> detail.

    PR-G2: Atlas-based world map.  The overview renders a continent-
    scale terrain canvas where locations are anchor points -- not a
    direct visualization of the 5x5 grid.

    Supports three display modes:
    * **wide** — full 72-column atlas canvas with legend
    * **compact** — 40-column atlas canvas (narrow terminals)
    * **minimal** — text-only site list (screen readers, tiny terminals)

    The atlas renders a direct-selection shortlist of labeled sites
    so the user can jump to region/detail without a separate menu.
    """
    from .map_renderer import build_map_info
    from .atlas_renderer import (
        render_atlas_overview,
        render_atlas_compact,
        render_atlas_minimal,
        atlas_labeled_sites,
    )

    ctx = _default_ctx(ctx)
    out = ctx.out
    inp = ctx.inp
    world = sim.world
    info = build_map_info(world)
    atlas_mode = "auto"  # default mode

    def _resolved_mode() -> str:
        if atlas_mode != "auto":
            return atlas_mode
        width = 80
        try:
            width = int(out.get_terminal_width())
        except Exception:
            width = shutil.get_terminal_size(fallback=(80, 24)).columns
        # NOTE: thresholds include panel frame/padding overhead in Rich mode.
        if width < 56:
            return "minimal"
        if width < 88:
            return "compact"
        return "wide"

    while True:
        out.print_line()
        render_mode = _resolved_mode()
        if render_mode == "compact":
            atlas_text = render_atlas_compact(info)
        elif render_mode == "minimal":
            atlas_text = render_atlas_minimal(info)
        else:
            atlas_text = render_atlas_overview(info)

        panel_title = f"{tr('world_map')} ({tr('atlas_mode_' + render_mode)})"
        out.print_panel(panel_title, atlas_text)

        # --- Direct selection shortlist (item 11) ---
        labeled = atlas_labeled_sites(info)
        out.print_line()
        out.print_heading(f"  {tr('atlas_site_list')}:")
        for i, (loc_id, name) in enumerate(labeled, 1):
            cell = None
            for c in info.cells.values():
                if c.location_id == loc_id:
                    cell = c
                    break
            overlay = ""
            if cell:
                from .atlas_renderer import _overlay_suffix
                ov = _overlay_suffix(cell)
                overlay = f" [{ov}]" if ov else ""
            out.print_line(f"    {i:>2}. {name}{overlay}")
        out.print_line()
        out.print_heading(f"  {tr('map_semantic_legend_title')}")
        out.print_error(f"    !  {tr('map_legend_danger_high')}")
        out.print_warning(f"    $  {tr('map_legend_traffic_high')}")
        out.print_highlighted(f"    ?  {tr('map_legend_rumor_high')}")
        out.print_dim(f"    m  {tr('map_legend_memorial')} / a  {tr('map_legend_alias')}")
        out.print_dim(f"  {tr('map_nav_keys_hint')}")
        out.print_line()

        action = ctx.choose_key(
            tr("map_nav_prompt"),
            [
                ("select", tr("map_nav_select")),
                ("region", tr("map_nav_region")),
                ("detail", tr("map_nav_detail")),
                ("mode", tr("map_nav_mode")),
                ("legacy", tr("map_nav_legacy")),
                ("back", tr("back_to_main")),
            ],
        )

        if action == "select":
            idx = _get_numeric_choice(
                f"  {tr('enter_location_number')}", len(labeled), ctx=ctx,
            )
            if idx is not None:
                loc_id, _ = labeled[idx]
                loc = world._location_id_index.get(loc_id)
                if loc is not None:
                    _region_drill_loop(
                        world, info, loc, ctx=ctx,
                    )

        elif action == "region":
            locations = sorted(world.grid.values(), key=lambda loc: loc.canonical_name)
            out.print_line()
            for i, loc in enumerate(locations, 1):
                out.print_line(f"  {i}. {loc.canonical_name} ({tr_term(loc.region_type)})")
            idx = _get_numeric_choice(
                f"  {tr('enter_location_number')}", len(locations), ctx=ctx,
            )
            if idx is not None:
                center_loc = locations[idx]
                _region_drill_loop(world, info, center_loc, ctx=ctx)

        elif action == "detail":
            locations = sorted(world.grid.values(), key=lambda loc: loc.canonical_name)
            out.print_line()
            for i, loc in enumerate(locations, 1):
                out.print_line(f"  {i}. {loc.canonical_name} ({tr_term(loc.region_type)})")
            idx = _get_numeric_choice(
                f"  {tr('enter_location_number')}", len(locations), ctx=ctx,
            )
            if idx is not None:
                loc = locations[idx]
                _show_detail_for_location(world, info, loc, ctx=ctx)

        elif action == "mode":
            new_mode = ctx.choose_key(
                tr("atlas_mode_prompt"),
                [
                    ("auto", tr("atlas_mode_auto")),
                    ("wide", tr("atlas_mode_wide")),
                    ("compact", tr("atlas_mode_compact")),
                    ("minimal", tr("atlas_mode_minimal")),
                ],
            )
            atlas_mode = new_mode

        elif action == "legacy":
            out.print_line()
            from .map_renderer import render_map_ascii
            out.print_line(render_map_ascii(info))
            inp.pause()

        else:
            break


def _show_monthly_report(sim: Simulator, ctx: UIContext | None = None) -> None:
    """Show a monthly report for the latest completed year.

    The user picks a month (1-12) within that year.  Reports are
    derived solely from event records, so content stays stable.
    """
    ctx = _default_ctx(ctx)
    out = ctx.out

    year = sim.get_latest_completed_report_year()
    out.print_line()
    out.print_line(f"  {tr('year_label')}: {year}")
    out.print_line(f"  {_month_season_hint()}")
    month_idx = _get_numeric_choice(
        f"  {tr('monthly_report')} (1-12): ", 12, ctx=ctx,
    )
    if month_idx is None:
        return
    month = month_idx + 1
    out.print_line()
    card = build_monthly_report_card_view(sim.world, year, month)
    for line in ReportPresenter.render_monthly_card(card):
        out.print_line(f"  {line}")
    out.print_line()
    out.print_line(sim.get_monthly_report(year, month))
    ctx.inp.pause()


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


def _show_single_story(sim: Simulator, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out
    world = sim.world

    out.print_line()
    for i, c in enumerate(world.characters, 1):
        status = out.format_status(tr("status_alive") if c.alive else tr("status_dead"), c.alive)
        out.print_line(
            f"  {i:>2}. [{status}] {c.name} ({tr_term(c.race)} {tr_term(c.job)}, "
            f"{tr('age_short_label')} {c.age})"
        )
    out.print_line()
    idx = _get_numeric_choice(f"  {tr('enter_character_number')}", len(world.characters), ctx=ctx)
    if idx is None:
        return
    char = world.characters[idx]
    out.print_line()
    out.print_line(sim.get_character_story(char.char_id))
    ctx.inp.pause()


def _show_adventure_summaries(sim: Simulator, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out

    runs = list(sim.world.completed_adventures) + list(sim.world.active_adventures)
    out.print_line()
    if not runs:
        out.print_dim(f"  {tr('no_adventures_recorded')}")
        ctx.inp.pause()
        return

    out.print_separator()
    out.print_heading(f"  {tr('adventure_summaries_header')}")
    out.print_separator()
    for i, run in enumerate(runs, 1):
        status = tr(f"outcome_{run.outcome}") if run.outcome else tr(f"state_{run.state}")
        origin_name = sim.world.location_name(run.origin)
        dest_name = sim.world.location_name(run.destination)
        if run.is_party:
            party_name = _party_display_names(sim.world, run)
            leader_display = party_name
            policy_label = tr(f"policy_{run.policy}")
        else:
            leader_display = run.character_name
            policy_label = ""
        view = AdventureSummaryView(
            title=leader_display,
            status=status,
            origin=origin_name,
            destination=dest_name,
            policy=policy_label,
            loot=[tr_term(item) for item in run.loot_summary],
            injury=tr(f'injury_status_{run.injury_status}') if run.injury_status != "none" else "none",
        )
        out.print_line(AdventurePresenter.render_summary_row(i, view))
    out.print_separator()
    ctx.inp.pause()


def _show_adventure_details(sim: Simulator, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out

    runs = list(sim.world.completed_adventures) + list(sim.world.active_adventures)
    out.print_line()
    if not runs:
        out.print_dim(f"  {tr('no_adventures_to_inspect')}")
        ctx.inp.pause()
        return

    for i, run in enumerate(runs, 1):
        status = tr(f"outcome_{run.outcome}") if run.outcome else tr(f"state_{run.state}")
        dest_name = sim.world.location_name(run.destination)
        out.print_line(f"  {i:>2}. {run.character_name} {tr('at_label')} {dest_name} [{status}]")
    out.print_line()
    idx = _get_numeric_choice(f"  {tr('enter_adventure_number')}", len(runs), ctx=ctx)
    if idx is None:
        return

    run = runs[idx]
    out.print_line()
    out.print_separator()
    out.print_heading(f"  {tr('adventure_detail_header', name=run.character_name)}")
    out.print_separator()
    out.print_line(f"  {tr('id_label'):<11}: {run.adventure_id}")
    out.print_line(
        f"  {tr('route'):<11}: {sim.world.location_name(run.origin)} -> "
        f"{sim.world.location_name(run.destination)}"
    )
    # Show party members for multi-member adventures
    if run.is_party:
        member_names = []
        for mid in run.member_ids:
            c = sim.world.get_character_by_id(mid)
            if c is not None:
                member_names.append(c.name)
        if not member_names:
            member_names = [run.character_name]
        out.print_line(f"  {tr('party_members_label'):<11}: {', '.join(member_names)}")
        out.print_line(f"  {tr('party_policy_label'):<11}: {tr(f'policy_{run.policy}')}")
        out.print_line(f"  {tr('party_supply_label'):<11}: {tr(f'supply_{run.supply_state}')}")
    out.print_line(f"  {tr('state'):<11}: {tr(f'state_{run.state}')}")
    out.print_line(
        f"  {tr('outcome'):<11}: {tr(f'outcome_{run.outcome}') if run.outcome else tr('unresolved')}"
    )
    out.print_line(f"  {tr('injury'):<11}: {tr(f'injury_status_{run.injury_status}')}")
    out.print_line(f"  {tr('steps'):<11}: {run.steps_taken}")
    if run.loot_summary:
        out.print_line(
            f"  {tr('discoveries'):<11}: {', '.join(tr_term(item) for item in run.loot_summary)}"
        )
    out.print_line()
    for entry in sim.get_adventure_details(run.adventure_id):
        out.print_line(f"  - {entry}")
    ctx.inp.pause()


def _resolve_pending_adventure_choice(sim: Simulator, ctx: UIContext | None = None) -> None:
    ctx = _default_ctx(ctx)
    out = ctx.out

    pending = sim.get_pending_adventure_choices()
    out.print_line()
    if not pending:
        out.print_dim(f"  {tr('no_pending_choices')}")
        ctx.inp.pause()
        return

    for i, item in enumerate(pending, 1):
        options = ", ".join(tr(f"choice_{option}") for option in item["options"])
        default_label = tr(f"choice_{item['default_option']}")
        out.print_line(
            f"  {i:>2}. {item['character_name']} | {item['prompt']} "
            f"[{options}] {tr('choice_default_hint', default_option=default_label)}"
        )
    out.print_line()

    idx = _get_numeric_choice(f"  {tr('enter_pending_choice_number')}", len(pending), ctx=ctx)
    if idx is None:
        return

    item = pending[idx]
    options = item["options"]
    out.print_line()
    for i, option in enumerate(options, 1):
        default_marker = f" {tr('default_marker')}" if option == item["default_option"] else ""
        out.print_line(f"  {i:>2}. {tr(f'choice_{option}')}{default_marker}")
    option_idx = _get_numeric_choice(f"  {tr('enter_option_number')}", len(options), ctx=ctx)
    chosen_option = options[option_idx] if option_idx is not None else None

    resolved = sim.resolve_adventure_choice(item["adventure_id"], option=chosen_option)
    out.print_line()
    if resolved:
        out.print_success(f"  {tr('choice_resolved')}")
    else:
        out.print_error(f"  {tr('choice_resolve_failed')}")
    ctx.inp.pause()


# ---------------------------------------------------------------------------
# Location history (PR-F: world memory)
# ---------------------------------------------------------------------------

def _show_location_history(world: World, ctx: UIContext | None = None) -> None:
    """Show live traces, memorials, and aliases for a selected location.

    PR-F (design §E-2): Surfaces world memory data — who visited, who
    died there, and any aliases the location has gained — so the player
    can observe how the world has been shaped over time.
    """
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
            traces=[t.get("text", "") for t in loc.live_traces],
            recent_event_count=len(loc.recent_event_ids),
        )
        out.print_line(LocationPresenter.render_location_row(i, view))
    out.print_line()

    idx = _get_numeric_choice(f"  {tr('enter_location_number')}", len(locations), ctx=ctx)
    if idx is None:
        return

    loc = locations[idx]
    out.print_line()
    out.print_separator()
    out.print_heading(f"  {tr('location_detail_header', name=loc.canonical_name)}")
    out.print_separator()

    # Aliases
    if loc.aliases:
        out.print_line(f"  {tr('location_aliases_label')}: {', '.join(loc.aliases)}")
        out.print_line()

    # Memorials
    out.print_line(f"  {tr('location_memorials_label')}:")
    memorials = world.get_memorials_for_location(loc.id)
    if memorials:
        for mem in memorials:
            out.print_line(f"    {tr('memorial_entry', year=mem.year, epitaph=mem.epitaph)}")
    else:
        out.print_dim(f"    {tr('no_memorials')}")

    # Live traces (most recent first, up to 5)
    out.print_line()
    out.print_line(f"  {tr('location_live_traces_label')}:")
    if loc.live_traces:
        for trace in reversed(loc.live_traces[-5:]):
            out.print_line(f"    - {trace['text']}")
    else:
        out.print_dim(f"    {tr('no_live_traces')}")

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
    inp = ctx.inp

    out.print_line()
    out.print_separator("=")
    out.print_heading(f"  {tr('new_simulation')} - {tr('default_world')}")
    out.print_separator("=")

    raw = inp.read_line(f"  > {tr('number_of_characters')}: ").strip()
    num = int(raw) if raw.isdigit() else 12
    num = max(4, min(30, num))

    raw = inp.read_line(f"  > {tr('simulation_length')}: ").strip()
    years = int(raw) if raw.isdigit() else 20
    years = max(1, min(200, years))

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
            templates = CharacterCreator.list_templates()
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

            raw = inp.read_line(f"  > {tr('simulation_length')}: ").strip()
            years = int(raw) if raw.isdigit() else 20
            years = max(1, min(200, years))

            sim = _run_simulation(world, years, ctx=ctx)
            _show_results(sim, ctx=ctx)
            break


def screen_world_lore(world: World | None = None, ctx: UIContext | None = None) -> None:
    """Show lore using the active world's bundle, or the default bundle pre-sim."""

    ctx = _default_ctx(ctx)
    out = ctx.out
    bundle = world.setting_bundle if world is not None else default_aethoria_bundle()
    lore_text = bundle.world_definition.lore_text

    out.print_line()
    out.print_separator("=")
    out.print_heading(f"  {tr('world_lore')}")
    out.print_separator("=")
    out.print_wrapped(lore_text)
    out.print_line()
    out.print_heading(f"  {tr('races_of_aethoria')}")
    out.print_separator()
    for rname, rdesc, bonuses in RACES:
        bonus_str = ", ".join(
            f"{stat} {'+' if v >= 0 else ''}{v}" for stat, v in bonuses.items() if v != 0
        )
        out.print_highlighted(f"  {rname}")
        out.print_wrapped(rdesc)
        if bonus_str:
            out.print_dim(f"    {tr('bonuses')}: {bonus_str}")
        out.print_line()
    out.print_heading(f"  {tr('jobs_classes')}")
    out.print_separator()
    for jname, jdesc, jskills in JOBS:
        skills_str = ', '.join(tr_term(skill) for skill in jskills)
        out.print_highlighted(f"  {tr_term(jname)}")
        out.print_line(f"    {tr('primary_skills_label')}: {skills_str}")
        out.print_wrapped(jdesc)
        out.print_line()
    ctx.inp.pause()


def _party_display_names(world: World, run: Any, max_shown: int = 3) -> str:
    names = []
    for mid in run.member_ids:
        c = world.get_character_by_id(mid)
        if c is not None:
            names.append(c.name)
    if not names:
        names = [run.character_name]
    shown = names[:max_shown]
    label = " & ".join(shown)
    if len(names) > max_shown:
        label += f" +{len(names) - max_shown}"
    return label

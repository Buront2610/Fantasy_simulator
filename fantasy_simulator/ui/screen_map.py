"""World-map screen flow and render payload helpers."""

from __future__ import annotations

import shutil
from typing import Any

from ..i18n import tr, tr_term
from ..simulator import Simulator
from ..world import World
from .presenters import RumorPresenter
from .screen_input import _get_numeric_choice
from .ui_context import UIContext, _default_ctx
from .view_models import build_location_observation_view


def _build_region_memory_payloads(
    world: World,
) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, list[str]], dict[str, str]]:
    """Return renderer-ready world memory payloads for region-map enrichment."""
    site_memorials: dict[str, list[str]] = {}
    site_aliases: dict[str, list[str]] = {}
    site_traces: dict[str, list[str]] = {}
    site_endonyms: dict[str, str] = {}
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
        if loc.generated_endonym:
            site_endonyms[loc.id] = loc.generated_endonym
    return site_memorials, site_aliases, site_traces, site_endonyms


def _build_detail_memory_payload(
    world: World,
    loc: Any,
) -> tuple[list[str] | None, list[str] | None, list[str] | None, str | None]:
    """Return renderer-ready world memory payloads for a location detail panel."""
    memorials: list[str] | None = None
    aliases = list(loc.aliases) or None
    live_traces: list[str] | None = None
    generated_endonym = loc.generated_endonym or None

    if loc.memorial_ids:
        memorials = [
            tr("memorial_entry", year=m.year, epitaph=m.epitaph)
            for m in world.get_memorials_for_location(loc.id)
        ] or None

    recent_traces = list(reversed(loc.live_traces[-5:]))
    if recent_traces:
        live_traces = [trace.get("text", "") for trace in recent_traces] or None

    return memorials, aliases, live_traces, generated_endonym


def _build_detail_observation_payload(
    world: World,
    loc: Any,
) -> tuple[list[str] | None, list[str] | None, list[str] | None]:
    """Return inspectable route/event/rumor notes for the rich detail panel."""
    observation = build_location_observation_view(world, loc.id)
    connected_routes = observation.connected_routes or None
    recent_events = observation.recent_events or None
    rumor_lines = [RumorPresenter.render_brief(rumor) for rumor in observation.rumors] or None
    return connected_routes, recent_events, rumor_lines


def _render_region_map_for_location(
    world: World,
    info: Any,
    center_loc: Any,
) -> str:
    """Render a region map using the same enrichment path as the interactive UI."""
    from .map_renderer import render_region_map

    site_memorials, site_aliases, site_traces, site_endonyms = _build_region_memory_payloads(world)
    return render_region_map(
        info,
        center_loc.id,
        site_memorials=site_memorials,
        site_aliases=site_aliases,
        site_traces=site_traces,
        site_endonyms=site_endonyms,
    )


def _render_location_detail_for_location(
    world: World,
    info: Any,
    loc: Any,
    *,
    include_observation_notes: bool = False,
) -> str:
    """Render a location detail panel using the same enrichment path as the interactive UI."""
    from .map_renderer import render_location_detail

    memorials, aliases, live_traces, generated_endonym = _build_detail_memory_payload(world, loc)
    connected_routes = None
    recent_events = None
    rumor_lines = None
    if include_observation_notes:
        connected_routes, recent_events, rumor_lines = _build_detail_observation_payload(world, loc)
    return render_location_detail(
        info,
        loc.id,
        memorials=memorials,
        aliases=aliases,
        live_traces=live_traces,
        generated_endonym=generated_endonym,
        connected_routes=connected_routes,
        recent_events=recent_events,
        rumor_lines=rumor_lines,
    )


def render_world_map_views_for_location(
    world: World,
    location_id: str,
    *,
    include_overview: bool = True,
    include_observation_notes: bool = False,
) -> dict[str, str]:
    """Return stable world-map overview/region/detail renderings for one location."""
    from .map_renderer import build_map_info, render_world_overview

    loc = world.get_location_by_id(location_id)
    if loc is None:
        raise ValueError(f"Unknown location id: {location_id}")

    info = build_map_info(world)
    rendered = {
        "region": _render_region_map_for_location(world, info, loc),
        "detail": _render_location_detail_for_location(
            world,
            info,
            loc,
            include_observation_notes=include_observation_notes,
        ),
    }
    if include_overview:
        rendered["overview"] = render_world_overview(info)
    return rendered


def _show_detail_for_location(
    world: World,
    info: Any,
    loc: Any,
    ctx: UIContext | None = None,
) -> None:
    """Render the detail panel for a single location."""
    ctx = _default_ctx(ctx)
    out = ctx.out
    inp = ctx.inp
    out.print_line()
    out.print_line(
        _render_location_detail_for_location(
            world,
            info,
            loc,
            include_observation_notes=True,
        )
    )
    inp.pause()


def _region_drill_loop(
    world: World,
    info: Any,
    center_loc: Any,
    ctx: UIContext | None = None,
) -> None:
    """Region map loop allowing navigation to nearby sites."""
    ctx = _default_ctx(ctx)
    out = ctx.out

    cell_by_id = {c.location_id: c for c in info.cells.values()}

    while True:
        out.print_line()
        out.print_line(_render_region_map_for_location(world, info, center_loc))

        center_cell = None
        for cell in info.cells.values():
            if cell.location_id == center_loc.id:
                center_cell = cell
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
    """Three-layer map navigation: overview -> region -> detail."""
    from .atlas_renderer import (
        atlas_labeled_sites,
        render_atlas_compact,
        render_atlas_minimal,
        render_atlas_overview,
    )
    from .map_renderer import build_map_info

    ctx = _default_ctx(ctx)
    out = ctx.out
    inp = ctx.inp
    world = sim.world
    info = build_map_info(world)
    atlas_mode = "auto"

    def _resolved_mode() -> str:
        if atlas_mode != "auto":
            return atlas_mode
        width = 80
        try:
            width = int(out.get_terminal_width())
        except Exception:
            width = shutil.get_terminal_size(fallback=(80, 24)).columns
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

        labeled = atlas_labeled_sites(info)
        out.print_line()
        out.print_heading(f"  {tr('atlas_site_list')}:")
        for i, (loc_id, name) in enumerate(labeled, 1):
            cell = None
            for candidate in info.cells.values():
                if candidate.location_id == loc_id:
                    cell = candidate
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
                loc = world.get_location_by_id(loc_id)
                if loc is not None:
                    _region_drill_loop(world, info, loc, ctx=ctx)

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

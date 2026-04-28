"""Interactive world-map screen navigation."""

from __future__ import annotations

import shutil
from typing import Any

from ..i18n import tr, tr_term
from ..simulator import Simulator
from ..world import World
from .screen_input import _get_numeric_choice
from .screen_map_payloads import (
    _render_location_detail_for_location,
    _render_region_map_for_location,
)
from .ui_context import UIContext, _default_ctx


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


def _visible_locations(world: World, info: Any, center_loc: Any, radius: int = 2) -> list[Any]:
    cell_by_id = {c.location_id: c for c in info.cells.values()}
    center_cell = cell_by_id.get(center_loc.id)
    if center_cell is None:
        return []

    x_min = max(0, center_cell.x - radius)
    x_max = min(info.width - 1, center_cell.x + radius)
    y_min = max(0, center_cell.y - radius)
    y_max = min(info.height - 1, center_cell.y + radius)

    visible_locs = []
    for loc in sorted(world.grid.values(), key=lambda lc: lc.canonical_name):
        cell = cell_by_id.get(loc.id)
        if cell and x_min <= cell.x <= x_max and y_min <= cell.y <= y_max:
            visible_locs.append(loc)
    return visible_locs


def _print_location_choices(locations: list[Any], ctx: UIContext, *, mark_location_id: str | None = None) -> None:
    for i, loc in enumerate(locations, 1):
        marker = "@" if loc.id == mark_location_id else " "
        ctx.out.print_line(f"  {marker}{i}. {loc.canonical_name} ({tr_term(loc.region_type)})")


def _choose_location(locations: list[Any], ctx: UIContext) -> Any | None:
    idx = _get_numeric_choice(
        f"  {tr('enter_location_number')}", len(locations), ctx=ctx,
    )
    if idx is None:
        return None
    return locations[idx]


def _region_drill_loop(
    world: World,
    info: Any,
    center_loc: Any,
    ctx: UIContext | None = None,
) -> None:
    """Region map loop allowing navigation to nearby sites."""
    ctx = _default_ctx(ctx)
    out = ctx.out

    while True:
        out.print_line()
        out.print_line(_render_region_map_for_location(world, info, center_loc))

        visible_locs = _visible_locations(world, info, center_loc)
        if not visible_locs:
            break

        out.print_line()
        _print_location_choices(visible_locs, ctx, mark_location_id=center_loc.id)

        sub = ctx.choose_key(
            tr("map_nav_prompt"),
            [
                ("detail", tr("map_nav_detail")),
                ("recenter", tr("map_nav_recenter")),
                ("back", tr("back_to_main")),
            ],
        )

        if sub == "detail":
            loc = _choose_location(visible_locs, ctx)
            if loc is not None:
                _show_detail_for_location(world, info, loc, ctx=ctx)

        elif sub == "recenter":
            loc = _choose_location(visible_locs, ctx)
            if loc is not None:
                center_loc = loc
        else:
            break


def _resolved_atlas_mode(atlas_mode: str, out: Any) -> str:
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


def _render_atlas_text(info: Any, render_mode: str) -> str:
    from .atlas_renderer import (
        render_atlas_compact,
        render_atlas_minimal,
        render_atlas_overview,
    )

    if render_mode == "compact":
        return render_atlas_compact(info)
    if render_mode == "minimal":
        return render_atlas_minimal(info)
    return render_atlas_overview(info)


def _print_atlas_site_list(info: Any, ctx: UIContext) -> list[tuple[str, str]]:
    from .atlas_renderer import _overlay_suffix, atlas_labeled_sites

    labeled = atlas_labeled_sites(info)
    ctx.out.print_line()
    ctx.out.print_heading(f"  {tr('atlas_site_list')}:")
    for i, (loc_id, name) in enumerate(labeled, 1):
        cell = next(
            (candidate for candidate in info.cells.values() if candidate.location_id == loc_id),
            None,
        )
        overlay = ""
        if cell:
            ov = _overlay_suffix(cell)
            overlay = f" [{ov}]" if ov else ""
        ctx.out.print_line(f"    {i:>2}. {name}{overlay}")
    return labeled


def _print_map_legend(ctx: UIContext) -> None:
    out = ctx.out
    out.print_line()
    out.print_heading(f"  {tr('map_semantic_legend_title')}")
    out.print_error(f"    !  {tr('map_legend_danger_high')}")
    out.print_warning(f"    $  {tr('map_legend_traffic_high')}")
    out.print_highlighted(f"    ?  {tr('map_legend_rumor_high')}")
    out.print_dim(f"    m  {tr('map_legend_memorial')} / a  {tr('map_legend_alias')}")
    out.print_dim(f"  {tr('map_nav_keys_hint')}")
    out.print_line()


def _all_locations(world: World) -> list[Any]:
    return sorted(world.grid.values(), key=lambda loc: loc.canonical_name)


def _choose_from_all_locations(world: World, ctx: UIContext) -> Any | None:
    locations = _all_locations(world)
    ctx.out.print_line()
    for i, loc in enumerate(locations, 1):
        ctx.out.print_line(f"  {i}. {loc.canonical_name} ({tr_term(loc.region_type)})")
    return _choose_location(locations, ctx)


def _show_world_map(sim: Simulator, ctx: UIContext | None = None) -> None:
    """Three-layer map navigation: overview -> region -> detail."""
    from .map_renderer import build_map_info

    ctx = _default_ctx(ctx)
    out = ctx.out
    inp = ctx.inp
    world = sim.world
    info = build_map_info(world)
    atlas_mode = "auto"

    while True:
        out.print_line()
        render_mode = _resolved_atlas_mode(atlas_mode, out)
        atlas_text = _render_atlas_text(info, render_mode)

        panel_title = f"{tr('world_map')} ({tr('atlas_mode_' + render_mode)})"
        out.print_panel(panel_title, atlas_text)
        labeled = _print_atlas_site_list(info, ctx)
        _print_map_legend(ctx)

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
            center_loc = _choose_from_all_locations(world, ctx)
            if center_loc is not None:
                _region_drill_loop(world, info, center_loc, ctx=ctx)

        elif action == "detail":
            loc = _choose_from_all_locations(world, ctx)
            if loc is not None:
                _show_detail_for_location(world, info, loc, ctx=ctx)

        elif action == "mode":
            atlas_mode = ctx.choose_key(
                tr("atlas_mode_prompt"),
                [
                    ("auto", tr("atlas_mode_auto")),
                    ("wide", tr("atlas_mode_wide")),
                    ("compact", tr("atlas_mode_compact")),
                    ("minimal", tr("atlas_mode_minimal")),
                ],
            )

        elif action == "legacy":
            out.print_line()
            from .map_renderer import render_map_ascii
            out.print_line(render_map_ascii(info))
            inp.pause()

        else:
            break

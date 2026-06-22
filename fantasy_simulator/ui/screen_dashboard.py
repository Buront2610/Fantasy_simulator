"""Observer dashboard screen."""

from __future__ import annotations

from ..i18n import tr
from ..simulator import Simulator
from .screen_history import _show_character_story
from .screen_map_navigation import _show_detail_for_location
from .ui_context import UIContext, _default_ctx
from .view_models import FollowUpActionView, WorldDashboardView, build_world_dashboard_view


def _show_world_dashboard(sim: Simulator, ctx: UIContext | None = None) -> None:
    """Render a compact world-state dashboard for observer play."""
    ctx = _default_ctx(ctx)
    view = build_world_dashboard_view(
        sim.world,
        current_month=sim.current_month,
        current_day=sim.current_day,
        pending_choice_count=len(sim.get_pending_adventure_choices()),
    )
    _render_world_dashboard(view, ctx=ctx)
    _handle_dashboard_follow_up(sim, view, ctx)


def _render_world_dashboard(view: WorldDashboardView, ctx: UIContext) -> None:
    out = ctx.out
    out.print_line()
    out.print_heading(f"  {tr('dashboard_title', world=view.world_name)}")
    out.print_line(
        f"  {tr('simulation_date_label', year=view.year, month=view.month_label, day=view.day)}  |  "
        f"{view.alive_count} {tr('alive')}  |  "
        f"{view.deceased_count} {tr('status_dead')}  |  "
        f"{tr('dashboard_active_adventures', count=view.active_adventure_count)}  |  "
        f"{tr('dashboard_pending_choices', count=view.pending_choice_count)}"
    )
    _render_section(tr("dashboard_major_events"), view.major_events, ctx=ctx)
    _render_section(tr("dashboard_watched_actors"), view.watched_actors, ctx=ctx)
    _render_section(tr("dashboard_hot_rumors"), view.hot_rumors, ctx=ctx)
    _render_section(tr("dashboard_dangerous_locations"), view.dangerous_locations, ctx=ctx)
    if view.era_status is not None:
        _render_section(tr("dashboard_era_status"), [view.era_status.text], ctx=ctx)
    if view.current_route_closures:
        _render_section(
            tr("dashboard_current_route_closures"),
            [item.text for item in view.current_route_closures],
            ctx=ctx,
        )
    if view.current_occupations:
        _render_section(
            tr("dashboard_current_occupations"),
            [item.text for item in view.current_occupations],
            ctx=ctx,
        )
    if view.active_wars:
        _render_section(tr("dashboard_active_wars"), [item.text for item in view.active_wars], ctx=ctx)
    if view.world_changes:
        lines = [
            f"{tr(f'world_change_category_{item.category}')}: {item.count}"
            for item in view.world_changes
        ]
        _render_section(tr("dashboard_world_changes"), lines, ctx=ctx)
    if view.world_change_entries:
        lines = [
            f"{tr(f'world_change_category_{item.category}')}: {item.text}"
            for item in view.world_change_entries[:5]
        ]
        _render_section(tr("dashboard_recent_world_changes"), lines, ctx=ctx)
    if view.follow_up_actions:
        _render_section(
            tr("dashboard_follow_up"),
            [item.label for item in view.follow_up_actions],
            ctx=ctx,
        )


def _handle_dashboard_follow_up(sim: Simulator, view: WorldDashboardView, ctx: UIContext) -> None:
    if not view.follow_up_actions:
        ctx.inp.pause()
        return
    action_key = ctx.choose_key(
        tr("dashboard_follow_up_prompt"),
        [(str(index), item.label) for index, item in enumerate(view.follow_up_actions, 1)]
        + [("back", tr("back_to_main"))],
    )
    if action_key == "back":
        return
    _open_dashboard_follow_up(sim, view.follow_up_actions[int(action_key) - 1], ctx)


def _open_dashboard_follow_up(sim: Simulator, action: FollowUpActionView, ctx: UIContext) -> None:
    world = sim.world
    if action.target_type == "character":
        character = world.get_character_by_id(action.target_id)
        if character is not None:
            _show_character_story(sim, character.char_id, ctx=ctx)
            return
    if action.location_id:
        from .map_renderer import build_map_info

        loc = world.get_location_by_id(action.location_id)
        if loc is not None:
            _show_detail_for_location(world, build_map_info(world), loc, ctx=ctx)
            return
    ctx.out.print_dim(f"  {tr('dashboard_follow_up_unavailable')}")
    ctx.inp.pause()


def _render_section(title: str, lines: list[str], ctx: UIContext) -> None:
    out = ctx.out
    out.print_line()
    out.print_highlighted(f"  {title}")
    if not lines:
        out.print_dim(f"    {tr('dashboard_empty_section')}")
        return
    for line in lines[:5]:
        out.print_line(f"    - {line}")

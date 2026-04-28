"""World-map render payload helpers."""

from __future__ import annotations

from typing import Any

from ..i18n import tr
from ..world import World
from .presenters import RumorPresenter
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

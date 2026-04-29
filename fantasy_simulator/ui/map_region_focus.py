"""Focus-summary selection for zoomed region maps."""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

from ..i18n import tr, tr_term
from .map_route_helpers import (
    pick_blocked_route_notice,
    pick_standout_route,
    region_reachability_tier,
    route_endpoint_name,
    route_other_endpoint,
)
from .map_view_models import MapCellInfo, RouteRenderInfo


def _pick_region_danger_target(
    visible_cells: List[MapCellInfo],
    center_cell: MapCellInfo,
    connected_open_ids: Set[str],
    connected_blocked_ids: Set[str],
) -> Optional[MapCellInfo]:
    danger_candidates = [
        cell for cell in visible_cells
        if cell.location_id != center_cell.location_id and cell.danger_band == "high"
    ]
    if not danger_candidates:
        return None

    def priority(cell: MapCellInfo) -> Tuple[int, int, int, str]:
        reachability = region_reachability_tier(
            cell.location_id,
            connected_open_ids,
            connected_blocked_ids,
        )
        distance = abs(cell.x - center_cell.x) + abs(cell.y - center_cell.y)
        return (reachability, -cell.danger, distance, cell.canonical_name.lower())

    return min(danger_candidates, key=priority)


def _pick_region_rumor_target(
    visible_cells: List[MapCellInfo],
    center_cell: MapCellInfo,
    connected_open_ids: Set[str],
    connected_blocked_ids: Set[str],
) -> Optional[MapCellInfo]:
    rumor_candidates = [cell for cell in visible_cells if cell.rumor_heat_band == "high"]
    if not rumor_candidates:
        return None

    def priority(cell: MapCellInfo) -> Tuple[int, int, int, str]:
        reachability = region_reachability_tier(
            cell.location_id,
            connected_open_ids,
            connected_blocked_ids,
        )
        distance = abs(cell.x - center_cell.x) + abs(cell.y - center_cell.y)
        return (reachability, -cell.rumor_heat, distance, cell.canonical_name.lower())

    return min(rumor_candidates, key=priority)


def _has_world_memory(
    cell: MapCellInfo,
    memorials_by_site: Dict[str, List[str]],
    aliases_by_site: Dict[str, List[str]],
    traces_by_site: Dict[str, List[str]],
) -> bool:
    return bool(
        memorials_by_site.get(cell.location_id)
        or aliases_by_site.get(cell.location_id)
        or traces_by_site.get(cell.location_id)
    )


def _cell_has_landmark_indicators(
    cell: MapCellInfo,
    memorials_by_site: Dict[str, List[str]],
    aliases_by_site: Dict[str, List[str]],
    traces_by_site: Dict[str, List[str]],
) -> bool:
    return bool(
        cell.has_memorial
        or cell.has_alias
        or cell.recent_death_site
        or _has_world_memory(cell, memorials_by_site, aliases_by_site, traces_by_site)
    )


def _landmark_focus_text(
    cell: MapCellInfo,
    memorials_by_site: Dict[str, List[str]],
    aliases_by_site: Dict[str, List[str]],
    traces_by_site: Dict[str, List[str]],
    endonyms_by_site: Dict[str, str],
) -> Optional[str]:
    if memorials_by_site.get(cell.location_id) or cell.has_memorial:
        return tr("map_region_focus_landmark_memorial", location=cell.canonical_name)
    if aliases_by_site.get(cell.location_id) or cell.has_alias:
        return tr("map_region_focus_landmark_alias", location=cell.canonical_name)
    if traces_by_site.get(cell.location_id):
        return tr("map_region_focus_landmark_trace", location=cell.canonical_name)
    if endonyms_by_site.get(cell.location_id):
        return tr(
            "map_region_focus_landmark_endonym",
            location=cell.canonical_name,
            endonym=endonyms_by_site[cell.location_id],
        )
    if cell.recent_death_site:
        return tr("map_region_focus_landmark_death", location=cell.canonical_name)
    return None


def _pick_landmark_target(
    visible_cells: List[MapCellInfo],
    center_location_id: str,
    memorials_by_site: Dict[str, List[str]],
    aliases_by_site: Dict[str, List[str]],
    traces_by_site: Dict[str, List[str]],
    endonyms_by_site: Dict[str, str],
) -> Optional[MapCellInfo]:
    center_memory_target = next(
        (
            cell for cell in visible_cells
            if cell.location_id == center_location_id
            and _has_world_memory(cell, memorials_by_site, aliases_by_site, traces_by_site)
        ),
        None,
    )
    if center_memory_target is not None:
        return center_memory_target
    return next(
        (
            cell for cell in visible_cells
            if _cell_has_landmark_indicators(cell, memorials_by_site, aliases_by_site, traces_by_site)
            or endonyms_by_site.get(cell.location_id)
        ),
        None,
    )


def region_focus_lines(
    visible_cells: List[MapCellInfo],
    center_cell: MapCellInfo,
    region_routes: List[RouteRenderInfo],
    cells_by_id: Dict[str, MapCellInfo],
    connected_open_ids: Set[str],
    connected_blocked_ids: Set[str],
    memorials: Dict[str, List[str]],
    aliases: Dict[str, List[str]],
    traces: Dict[str, List[str]],
    endonyms: Dict[str, str],
) -> List[str]:
    center_location_id = center_cell.location_id
    standout_lines: List[str] = []
    standout_route = pick_standout_route(region_routes, center_location_id, cells_by_id)
    if standout_route is not None:
        other_id = route_other_endpoint(standout_route, center_location_id)
        standout_lines.append(
            tr(
                "map_region_focus_route",
                destination=route_endpoint_name(cells_by_id, other_id),
                route_type=tr_term(standout_route.route_type),
                blocked=f" {tr('route_blocked')}" if standout_route.blocked else "",
            ).rstrip()
        )

    danger_target = _pick_region_danger_target(
        visible_cells,
        center_cell,
        connected_open_ids,
        connected_blocked_ids,
    )
    rumor_target = _pick_region_rumor_target(
        visible_cells,
        center_cell,
        connected_open_ids,
        connected_blocked_ids,
    )
    blocked_notice = pick_blocked_route_notice(region_routes, center_location_id, cells_by_id)
    if blocked_notice is not None:
        blocked_destination = route_endpoint_name(
            cells_by_id,
            route_other_endpoint(blocked_notice, center_location_id),
        )
        standout_lines.append(tr("map_region_focus_blocked", destination=blocked_destination))

    if danger_target is not None:
        standout_lines.append(tr("map_region_focus_danger", location=danger_target.canonical_name))

    if rumor_target is not None:
        standout_lines.append(tr("map_region_focus_rumor", location=rumor_target.canonical_name))

    landmark_target = _pick_landmark_target(
        visible_cells,
        center_location_id,
        memorials,
        aliases,
        traces,
        endonyms,
    )
    if landmark_target is not None:
        landmark_text = _landmark_focus_text(landmark_target, memorials, aliases, traces, endonyms)
        if landmark_text:
            standout_lines.append(landmark_text)
    return standout_lines

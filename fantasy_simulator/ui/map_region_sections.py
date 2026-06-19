"""Text sections for zoomed region maps."""

from __future__ import annotations

from typing import Dict, List, Set

from ..i18n import tr, tr_term
from .map_overlays import _overlay_suffix
from .map_route_helpers import route_endpoint_name
from .map_view_models import LocalMapCue, MapCellInfo, RouteRenderInfo
from .ui_helpers import fit_display_width


_DANGER_MARKERS: Dict[str, str] = {"low": " ", "medium": ".", "high": "!"}
_TRAFFIC_MARKERS: Dict[str, str] = {"low": " ", "medium": "o", "high": "O"}
_RUMOR_MARKERS: Dict[str, str] = {"low": " ", "medium": "~", "high": "?"}
_MAX_REGION_STANDOUT_ITEMS = 4
_OPEN_ROUTE_MARKER = "<->"
_BLOCKED_ROUTE_MARKER = "x->"
_LOCAL_CUE_CATEGORY_ORDER = ("site", "terrain", "memory", "route")
_REGION_LINE_WIDTH_BUDGET = 57


def append_region_focus(lines: List[str], standout_lines: List[str]) -> None:
    if not standout_lines:
        return
    lines.append("")
    lines.append(f"  {tr('map_region_focus')}:")
    for item in standout_lines[:_MAX_REGION_STANDOUT_ITEMS]:
        lines.append(f"    - {item}")
    lines.append("")


def append_nearby_sites(
    lines: List[str],
    visible_cells: List[MapCellInfo],
    center_location_id: str,
    connected_open_ids: Set[str],
    connected_blocked_ids: Set[str],
) -> None:
    lines.append(f"  {tr('map_region_nearby')}:")

    for cell in visible_cells:
        marker = "@" if cell.location_id == center_location_id else " "
        if cell.location_id in connected_open_ids:
            conn = _OPEN_ROUTE_MARKER
        elif cell.location_id in connected_blocked_ids:
            conn = _BLOCKED_ROUTE_MARKER
        else:
            conn = "   "
        overlay = _overlay_suffix(cell)
        overlay_str = f" [{overlay}]" if overlay else ""
        danger_str = _DANGER_MARKERS.get(cell.danger_band, " ")
        traffic_str = _TRAFFIC_MARKERS.get(cell.traffic_band, " ")
        rumor_str = _RUMOR_MARKERS.get(cell.rumor_heat_band, " ")
        lines.append(
            f"   {marker} {conn} {cell.canonical_name}"
            f" ({tr_term(cell.region_type)})"
            f" D:{danger_str} T:{traffic_str} R:{rumor_str}{overlay_str}"
        )


def append_region_routes(
    lines: List[str],
    region_routes: List[RouteRenderInfo],
    cells_by_id: Dict[str, MapCellInfo],
) -> None:
    if not region_routes:
        return
    lines.append(f"  {tr('map_region_routes')}:")
    for route in region_routes:
        blocked = f" {tr('route_blocked')}" if route.blocked else ""
        from_name = route_endpoint_name(cells_by_id, route.from_site_id)
        to_name = route_endpoint_name(cells_by_id, route.to_site_id)
        lines.append(
            f"    {from_name} <-> {to_name}"
            f" ({tr_term(route.route_type)}){blocked}"
        )


def _format_local_cue_groups(cues: List[LocalMapCue]) -> str:
    groups: Dict[str, List[str]] = {category: [] for category in _LOCAL_CUE_CATEGORY_ORDER}
    for cue in sorted(cues, key=lambda item: item.priority):
        groups.setdefault(cue.category, []).append(cue.label)
    parts = []
    for category in _LOCAL_CUE_CATEGORY_ORDER:
        labels = groups.get(category, [])
        if labels:
            parts.append(f"{tr(f'map_cue_category_{category}')}: {_format_cue_labels(labels)}")
    return "; ".join(parts)


def _format_cue_labels(labels: List[str]) -> str:
    if len(labels) <= 2:
        return ", ".join(labels)
    return f"{labels[0]}, +{len(labels) - 1}"


def append_region_local_cues(lines: List[str], visible_cells: List[MapCellInfo]) -> None:
    cue_cells = [cell for cell in visible_cells if cell.local_feature_cues]
    if not cue_cells:
        return
    lines.append(f"  {tr('map_region_local_cues')}:")
    for cell in cue_cells:
        text = f"    {cell.canonical_name}: {_format_local_cue_groups(list(cell.local_feature_cues))}"
        lines.append(fit_display_width(text, _REGION_LINE_WIDTH_BUDGET))


def append_region_landmarks(
    lines: List[str],
    visible_cells: List[MapCellInfo],
    memorials: Dict[str, List[str]],
    aliases: Dict[str, List[str]],
    traces: Dict[str, List[str]],
    endonyms: Dict[str, str],
) -> None:
    has_memory = False
    for cell in visible_cells:
        loc_id = cell.location_id
        mem_items = memorials.get(loc_id, [])
        ali_items = aliases.get(loc_id, [])
        tra_items = traces.get(loc_id, [])
        endonym = endonyms.get(loc_id, "")
        if not mem_items and not ali_items and not tra_items and not endonym:
            continue
        if not has_memory:
            lines.append("")
            lines.append(f"  {tr('map_region_landmarks')}:")
            has_memory = True
        lines.append(f"    {cell.canonical_name}:")
        if endonym:
            lines.append(f"      {tr('map_landmark_endonym')}: {endonym}")
        if ali_items:
            lines.append(f"      {tr('map_landmark_alias')}: {', '.join(ali_items[:3])}")
        for mem in mem_items[:2]:
            lines.append(f"      {tr('map_landmark_memorial')}: {mem}")
        for tra in tra_items[:2]:
            lines.append(f"      {tr('map_landmark_trace')}: {tra}")

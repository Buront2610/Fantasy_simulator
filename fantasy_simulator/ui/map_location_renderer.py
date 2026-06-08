"""Single-location detail renderer for map observation."""

from __future__ import annotations

from typing import List, Optional

from ..i18n import tr, tr_term
from .atlas_canvas import _ROUTE_LINE, _bresenham
from .map_view_models import LocalMapCue, MapCellInfo, MapRenderInfo, RouteRenderInfo
from .ui_helpers import fit_display_width


def _fit(text: str, width: int) -> str:
    return fit_display_width(text, width)


def _band_label(band: str) -> str:
    return tr(f"map_band_{band}")


def _terrain_percent(value: int) -> int:
    return round(max(0, min(255, value)) * 100 / 255)


def _terrain_value_band(value: int, low_key: str, middle_key: str, high_key: str) -> str:
    if value < 86:
        return tr(low_key)
    if value < 171:
        return tr(middle_key)
    return tr(high_key)


def _terrain_metric_line(label_key: str, value: int, low_key: str, middle_key: str, high_key: str) -> str:
    label = tr(label_key)
    band = _terrain_value_band(value, low_key, middle_key, high_key)
    return f" {label}: {band} ({_terrain_percent(value)}%)"


def _append_terrain_metric(
    lines: List[str],
    width: int,
    label_key: str,
    value: int,
    low_key: str,
    middle_key: str,
    high_key: str,
) -> None:
    metric = _terrain_metric_line(label_key, value, low_key, middle_key, high_key)
    lines.append(f"  |{_fit(metric, width)}|")


_LOCAL_CUE_CATEGORY_ORDER = ("site", "terrain", "memory", "route")
_DETAIL_ROUTE_SKETCH_WIDTH = 31
_DETAIL_ROUTE_SKETCH_HEIGHT = 9
_DETAIL_ROUTE_CENTER = (15, 4)


def _format_local_cue_groups(cues: List[LocalMapCue]) -> str:
    groups: dict[str, List[str]] = {category: [] for category in _LOCAL_CUE_CATEGORY_ORDER}
    for cue in sorted(cues, key=lambda item: item.priority):
        groups.setdefault(cue.category, []).append(cue.label)
    parts = []
    for category in _LOCAL_CUE_CATEGORY_ORDER:
        labels = groups.get(category, [])
        if labels:
            parts.append(f"{tr(f'map_cue_category_{category}')}: {', '.join(labels)}")
    return "; ".join(parts)


def _site_ascii_lines(cell: MapCellInfo) -> List[str]:
    if cell.region_type == "city":
        return [
            "       ____||____        ________       ",
            "  ____/ []  []  \\______/ [] []  \\____  ",
            " | []  []  []    |  $  []   []   []  | ",
            " |      ____      |____     ____      | ",
            " | []  | [] |  o  | [] |   | [] |  []| ",
            " |_____|____|_____|____|___|____|____| ",
            "       |  G |===== main road =====| G | ",
            "  _____|____|_____________________|___|_",
            "       /      market square       \\    ",
        ]
    if cell.region_type == "village":
        return [
            "        _       _          B",
            "   ____/ \\__ __/ \\____    []",
            "  | []  []  |  []  [] |",
            "  |   o     |   ..    |====",
            "  |____   __|__   ____|",
            "       |_|     |_|",
        ]
    if cell.region_type == "dungeon":
        return [
            "          /\\",
            "     ____/  \\____",
            "    /  []    []   \\",
            "   /__[]______[]__\\",
            "      ||  ||  ||",
            "      xx  ||  xx",
        ]
    if cell.region_type == "mountain":
        return [
            "          /\\        /\\",
            "     /\\  /  \\__/\\  /  \\",
            "    /  \\/  ||  \\/  /\\",
            "        /__||__\\",
            "           ||",
        ]
    if cell.region_type == "forest":
        return [
            "      ^^   ^^   ^^",
            "    ^^    --     ^^",
            "      ^^   []   ^^",
            "    ^^    ..     ^^",
            "          ||",
        ]
    return [
        "       .     .      .",
        "    .       --       .",
        "       .    []    .",
        "    .______/  \\____.",
        "          ||",
    ]


def _local_symbol_line(cell: MapCellInfo, width: int) -> List[str]:
    symbols: List[str] = []
    tags = set(cell.local_feature_tags)
    if "gate" in tags:
        symbols.append(f"G={tr('map_feature_gate')}")
    if "market" in tags:
        symbols.append(f"$={tr('map_feature_market')}")
    if "notice_board" in tags:
        symbols.append(f"B={tr('map_feature_notice_board')}")
    if cell.has_memorial or "memorial" in tags:
        symbols.append(f"M={tr('map_feature_memorial')}")
    if cell.rumor_heat_band == "high":
        symbols.append(f"?={tr('map_legend_rumor_high')}")
    if cell.danger_band == "high":
        symbols.append(f"!={tr('map_legend_danger_high')}")
    if not symbols:
        return []
    legend = f" {tr('map_detail_aa_legend')}: {' / '.join(symbols)}"
    return [f"  |{_fit(legend, width)}|"]


def _connected_detail_routes(info: MapRenderInfo, cell: MapCellInfo) -> list[tuple[RouteRenderInfo, MapCellInfo]]:
    cells_by_id = {candidate.location_id: candidate for candidate in info.cells.values()}
    connected: list[tuple[RouteRenderInfo, MapCellInfo]] = []
    for route in info.routes:
        if route.from_site_id == cell.location_id:
            other = cells_by_id.get(route.to_site_id)
        elif route.to_site_id == cell.location_id:
            other = cells_by_id.get(route.from_site_id)
        else:
            other = None
        if other is not None:
            connected.append((route, other))
    return connected


def _detail_route_endpoint(cell: MapCellInfo, other: MapCellInfo, route_index: int) -> tuple[int, int]:
    center_x, center_y = _DETAIL_ROUTE_CENTER
    dx = other.x - cell.x
    dy = other.y - cell.y
    scale = max(abs(dx), abs(dy), 1)
    target_x = center_x + round((dx / scale) * ((_DETAIL_ROUTE_SKETCH_WIDTH - 3) / 2))
    target_y = center_y + round((dy / scale) * ((_DETAIL_ROUTE_SKETCH_HEIGHT - 3) / 2))
    fan_offset = -1 if route_index % 2 == 0 else 1
    if dx == 0 and dy != 0:
        target_x += fan_offset * 4
    elif dy == 0 and dx != 0:
        target_y += fan_offset * 2
    target_x = max(1, min(_DETAIL_ROUTE_SKETCH_WIDTH - 2, target_x))
    target_y = max(1, min(_DETAIL_ROUTE_SKETCH_HEIGHT - 2, target_y))
    if (target_x, target_y) == _DETAIL_ROUTE_CENTER:
        target_x = min(_DETAIL_ROUTE_SKETCH_WIDTH - 2, target_x + 1)
    return target_x, target_y


def _detail_route_char(route_type: str, blocked: bool, ddx: int, ddy: int) -> str:
    chars = _ROUTE_LINE.get(route_type, ("-", "|", "/", "\\"))
    if blocked:
        chars = ("x", "x", "x", "x")
    if ddy == 0:
        return chars[0]
    if ddx == 0:
        return chars[1]
    if (ddx > 0) != (ddy > 0):
        return chars[2]
    return chars[3]


def _detail_route_marker(cell: MapCellInfo) -> str:
    if cell.site_type == "city" or cell.region_type == "city":
        return "C"
    if cell.site_type == "dungeon" or cell.region_type == "dungeon":
        return "D"
    if cell.region_type == "mountain":
        return "^"
    if cell.region_type == "forest":
        return "T"
    return "o"


def _detail_route_sketch_lines(info: MapRenderInfo, cell: MapCellInfo) -> list[str]:
    connected = _connected_detail_routes(info, cell)
    if not connected:
        return []

    canvas: list[list[str]] = [
        [" " for _ in range(_DETAIL_ROUTE_SKETCH_WIDTH)]
        for _ in range(_DETAIL_ROUTE_SKETCH_HEIGHT)
    ]
    center_x, center_y = _DETAIL_ROUTE_CENTER
    canvas[center_y][center_x] = "@"
    for route_index, (route, other) in enumerate(connected[:8]):
        target = _detail_route_endpoint(cell, other, route_index)
        path = _bresenham(center_x, center_y, target[0], target[1])
        for index, (px, py) in enumerate(path[1:], start=1):
            if not (0 <= px < _DETAIL_ROUTE_SKETCH_WIDTH and 0 <= py < _DETAIL_ROUTE_SKETCH_HEIGHT):
                continue
            if (px, py) == target:
                canvas[py][px] = "x" if getattr(route, "blocked", False) else _detail_route_marker(other)
                continue
            prev_x, prev_y = path[index - 1]
            canvas[py][px] = _detail_route_char(
                getattr(route, "route_type", "road"),
                getattr(route, "blocked", False),
                px - prev_x,
                py - prev_y,
            )
    return ["".join(row).rstrip().ljust(_DETAIL_ROUTE_SKETCH_WIDTH) for row in canvas]


def _append_detail_route_sketch(lines: List[str], info: MapRenderInfo, cell: MapCellInfo, width: int) -> None:
    sketch = _detail_route_sketch_lines(info, cell)
    if not sketch:
        return
    title = f" {tr('map_detail_route_sketch')}"
    lines.append(f"  |{_fit(title, width)}|")
    lines.append(f"  |{_fit('  +' + '-' * _DETAIL_ROUTE_SKETCH_WIDTH + '+', width)}|")
    for row in sketch:
        lines.append(f"  |{_fit(f'  |{row}|', width)}|")
    lines.append(f"  |{_fit('  +' + '-' * _DETAIL_ROUTE_SKETCH_WIDTH + '+', width)}|")


def _append_site_ascii(lines: List[str], info: MapRenderInfo, cell: MapCellInfo, width: int, border: str) -> None:
    title = f" {tr('map_detail_aa_title')}"
    lines.append(f"  |{_fit(title, width)}|")
    for art_line in _site_ascii_lines(cell):
        lines.append(f"  |{_fit(f' {art_line}', width)}|")
    _append_detail_route_sketch(lines, info, cell, width)
    lines.extend(_local_symbol_line(cell, width))
    lines.append(border)


def _append_state_lines(lines: List[str], cell: MapCellInfo, width: int) -> None:
    safety_label = tr("map_safety")
    danger_label = tr("map_danger")
    traffic_label = tr("map_traffic")
    pop_label = tr("map_population")
    prosperity_label = tr("map_detail_prosperity")
    mood_label = tr("map_detail_mood")
    rumor_label = tr("map_detail_rumor_heat")
    control_label = tr("map_detail_control")
    cues_label = tr("map_detail_local_cues")

    lines.append(f"  |{_fit(f' {safety_label}: {cell.safety_label}', width)}|")
    lines.append(f"  |{_fit(f' {danger_label}: {cell.danger:>3} ({_band_label(cell.danger_band)})', width)}|")
    lines.append(
        f"  |{_fit(f' {traffic_label}: {cell.traffic_indicator} ({_band_label(cell.traffic_band)})', width)}|"
    )
    lines.append(f"  |{_fit(f' {pop_label}: {cell.population}', width)}|")
    if cell.controlling_faction_name:
        lines.append(f"  |{_fit(f' {control_label}: {cell.controlling_faction_name}', width)}|")
    if cell.local_feature_cues:
        cues = _format_local_cue_groups(list(cell.local_feature_cues))
        lines.append(f"  |{_fit(f' {cues_label}: {cues}', width)}|")
    lines.append(f"  |{_fit(f' {prosperity_label}: {cell.prosperity_label} ({cell.prosperity})', width)}|")
    lines.append(f"  |{_fit(f' {mood_label}: {cell.mood_label} ({cell.mood})', width)}|")
    lines.append(f"  |{_fit(f' {rumor_label}: {cell.rumor_heat} ({_band_label(cell.rumor_heat_band)})', width)}|")


def _append_overlay_markers(lines: List[str], cell: MapCellInfo, width: int, border: str) -> None:
    overlay_items: List[str] = []
    if cell.has_memorial:
        overlay_items.append(tr("map_legend_memorial"))
    if cell.has_alias:
        overlay_items.append(tr("map_legend_alias"))
    if cell.recent_death_site:
        overlay_items.append(tr("map_legend_recent_death"))
    if overlay_items:
        markers_label = tr("map_detail_markers")
        overlay_line = ", ".join(overlay_items)
        lines.append(f"  |{_fit(f' {markers_label}: {overlay_line}', width)}|")
        lines.append(border)


def _append_name_lines(
    lines: List[str],
    width: int,
    *,
    generated_endonym: Optional[str],
    name_etymology_line: Optional[str],
    aliases: Optional[List[str]],
) -> None:
    if generated_endonym:
        endonym_label = tr("location_endonym_label")
        lines.append(f"  |{_fit(f' {endonym_label}: {generated_endonym}', width)}|")
    if name_etymology_line:
        etymology_label = tr("location_etymology_label")
        lines.append(f"  |{_fit(f' {etymology_label}: {name_etymology_line}', width)}|")
    if aliases:
        aliases_label = tr("location_aliases_label")
        aliases_line = ", ".join(aliases)
        lines.append(f"  |{_fit(f' {aliases_label}: {aliases_line}', width)}|")


def _append_labeled_list(lines: List[str], width: int, label: str, items: List[str], *, bullet: str = "") -> None:
    lines.append(f"  |{_fit(f' {label}:', width)}|")
    for item in items[:5]:
        prefix = f"   {bullet}" if bullet else "   "
        lines.append(f"  |{_fit(f'{prefix}{item}', width)}|")


def _append_detail_lists(
    lines: List[str],
    width: int,
    *,
    memorials: Optional[List[str]],
    live_traces: Optional[List[str]],
    connected_routes: Optional[List[str]],
    recent_events: Optional[List[str]],
    rumor_lines: Optional[List[str]],
) -> None:
    if memorials:
        _append_labeled_list(lines, width, tr("location_memorials_label"), memorials)
    if live_traces:
        _append_labeled_list(lines, width, tr("location_live_traces_label"), live_traces, bullet="- ")
    if connected_routes:
        _append_labeled_list(lines, width, tr("map_region_routes"), connected_routes, bullet="- ")
    if recent_events:
        _append_labeled_list(lines, width, tr("location_recent_events_label"), recent_events, bullet="- ")
    if rumor_lines:
        _append_labeled_list(lines, width, tr("rumor_section_title"), rumor_lines, bullet="- ")


def render_location_detail(
    info: MapRenderInfo,
    location_id: str,
    memorials: Optional[List[str]] = None,
    aliases: Optional[List[str]] = None,
    live_traces: Optional[List[str]] = None,
    generated_endonym: Optional[str] = None,
    name_etymology_line: Optional[str] = None,
    recent_events: Optional[List[str]] = None,
    rumor_lines: Optional[List[str]] = None,
    connected_routes: Optional[List[str]] = None,
) -> str:
    """Render a detailed single-site view with AA panel."""
    cell: Optional[MapCellInfo] = None
    for candidate in info.cells.values():
        if candidate.location_id == location_id:
            cell = candidate
            break
    if cell is None:
        return f"  {tr('map_detail_not_found', location=location_id)}"

    width = 50
    border = "  +" + "-" * width + "+"
    lines: List[str] = [border]

    title = f" {cell.icon} {cell.canonical_name} ({tr_term(cell.region_type)})"
    lines.append(f"  |{_fit(title, width)}|")
    lines.append(border)
    _append_site_ascii(lines, info, cell, width, border)

    terrain_label = tr("map_terrain")
    biome_name = tr_term(cell.terrain_biome)
    lines.append(f"  |{_fit(f' {terrain_label}: {biome_name} ({cell.terrain_glyph})', width)}|")
    _append_terrain_metric(
        lines,
        width,
        'map_detail_elevation',
        cell.terrain_elevation,
        'map_elevation_lowland',
        'map_elevation_midland',
        'map_elevation_highland',
    )
    _append_terrain_metric(
        lines,
        width,
        'map_detail_moisture',
        cell.terrain_moisture,
        'map_moisture_dry',
        'map_moisture_balanced',
        'map_moisture_wet',
    )
    _append_terrain_metric(
        lines,
        width,
        'map_detail_temperature',
        cell.terrain_temperature,
        'map_temperature_cold',
        'map_temperature_temperate',
        'map_temperature_hot',
    )
    lines.append(border)

    _append_state_lines(lines, cell, width)
    lines.append(border)

    _append_overlay_markers(lines, cell, width, border)
    _append_name_lines(
        lines,
        width,
        generated_endonym=generated_endonym,
        name_etymology_line=name_etymology_line,
        aliases=aliases,
    )
    _append_detail_lists(
        lines,
        width,
        memorials=memorials,
        live_traces=live_traces,
        connected_routes=connected_routes,
        recent_events=recent_events,
        rumor_lines=rumor_lines,
    )

    if (
        generated_endonym
        or name_etymology_line
        or aliases
        or memorials
        or live_traces
        or connected_routes
        or recent_events
        or rumor_lines
    ):
        lines.append(border)

    return "\n".join(lines)

"""Single-location detail renderer for map observation."""

from __future__ import annotations

from typing import List, Optional

from ..i18n import tr, tr_term
from .map_view_models import LocalMapCue, MapCellInfo, MapRenderInfo
from .ui_helpers import fit_display_width


def _fit(text: str, width: int) -> str:
    return fit_display_width(text, width)


def _band_label(band: str) -> str:
    return tr(f"map_band_{band}")


_LOCAL_CUE_CATEGORY_ORDER = ("site", "terrain", "memory", "route")


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
            "        ____||____        ________",
            "   ____/  []  [] \\______/ [] []  \\",
            "  |  []  []  []   |  $  []    [] |",
            "  |  []      []   |      o       |",
            "  |_____    ______|_____    ______|",
            "        |  |            |  |",
            "        |__|____________|__|",
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


def _append_site_ascii(lines: List[str], cell: MapCellInfo, width: int, border: str) -> None:
    title = f" {tr('map_detail_aa_title')}"
    lines.append(f"  |{_fit(title, width)}|")
    for art_line in _site_ascii_lines(cell):
        lines.append(f"  |{_fit(f' {art_line}', width)}|")
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
    _append_site_ascii(lines, cell, width, border)

    terrain_label = tr("map_terrain")
    biome_name = tr_term(cell.terrain_biome)
    lines.append(f"  |{_fit(f' {terrain_label}: {biome_name} ({cell.terrain_glyph})', width)}|")
    elev_label = tr("map_detail_elevation")
    moist_label = tr("map_detail_moisture")
    temp_label = tr("map_detail_temperature")
    elev_line = (
        f" {elev_label}:{cell.terrain_elevation}"
        f" {moist_label}:{cell.terrain_moisture}"
        f" {temp_label}:{cell.terrain_temperature}"
    )
    lines.append(f"  |{_fit(elev_line, width)}|")
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

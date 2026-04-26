"""
map_renderer.py - Map data extraction and ASCII rendering.

This module decouples the *data* that a map carries (``MapCellInfo``,
``MapRenderInfo``) from the *presentation* logic that turns that data
into an ASCII grid.

Domain code (``world.py``) now only needs to call ``build_map_info()``
to produce a renderer-agnostic snapshot.  The UI layer picks the
renderer it needs.

PR-G2 introduces a three-layer observation UI:

1. **World overview** (``render_world_overview``) — compact terrain
   glyph grid with overlay markers and legend.
2. **Region map** (``render_region_map``) — zoomed view around a
   selected site showing neighbours, routes, and overlays.
3. **Location detail** (``render_location_detail``) — single-site
   AA panel with memorials, traces, and stats.

The legacy ``render_map_ascii`` is preserved for backward compatibility.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from ..i18n import tr, tr_term
from ..narrative.constants import EVENT_KINDS_FATAL
from .ui_helpers import fit_display_width

if TYPE_CHECKING:
    from ..terrain import AtlasLayout, Site
    from ..world import World


# ------------------------------------------------------------------
# Intermediate representations
# ------------------------------------------------------------------

@dataclass
class MapCellInfo:
    """Renderer-agnostic snapshot of one map cell.

    All fields are plain values — no references to ``LocationState``
    or ``World``.  This makes the data trivially serialisable and
    testable without domain objects.

    The current ASCII renderer uses a subset of these fields.
    Additional fields (``prosperity``, ``prosperity_label``,
    ``mood``, ``mood_label``, ``rumor_heat``, ``road_condition``)
    are carried so that future renderers (Rich panels, AA maps,
    colour-coded overlays) can visualise richer world state without
    needing to touch domain code again.
    """

    location_id: str
    canonical_name: str
    region_type: str
    icon: str
    safety_label: str
    danger: int
    traffic_indicator: str
    population: int
    x: int
    y: int
    highlighted: bool = False
    # Extended fields for future renderers ---------------------------------
    prosperity: int = 50
    prosperity_label: str = ""
    mood: int = 50
    mood_label: str = ""
    rumor_heat: int = 0
    road_condition: int = 50
    # vNext render hints (banded/boolean overlay fields)
    danger_band: str = "medium"
    traffic_band: str = "medium"
    rumor_heat_band: str = "low"
    has_memorial: bool = False
    has_alias: bool = False
    recent_death_site: bool = False
    # PR-G: terrain overlay fields
    terrain_biome: str = "plains"
    terrain_glyph: str = ","
    terrain_elevation: int = 128
    terrain_moisture: int = 128
    terrain_temperature: int = 128
    has_site: bool = True
    site_type: str = ""
    site_importance: int = 50
    # PR-G2: pre-computed atlas coordinates (-1 = compute on the fly)
    atlas_x: int = -1
    atlas_y: int = -1


@dataclass
class RouteRenderInfo:
    """Renderer-agnostic snapshot of a route between two sites."""
    route_id: str
    from_site_id: str
    to_site_id: str
    route_type: str
    blocked: bool = False


@dataclass
class TerrainCellRenderInfo:
    """Renderer-agnostic snapshot of a pure terrain cell (no site)."""
    x: int
    y: int
    biome: str
    glyph: str
    elevation: int = 128
    moisture: int = 128
    temperature: int = 128


@dataclass
class MapRenderInfo:
    """Everything a renderer needs to draw the world map.

    ``cells`` is keyed by ``(x, y)`` grid coordinates and includes
    both site cells and terrain-only cells.
    ``terrain_cells`` holds render info for every terrain coordinate.
    ``routes`` holds route overlay data.
    """

    world_name: str
    year: int
    width: int
    height: int
    cells: Dict[Tuple[int, int], MapCellInfo] = field(default_factory=dict)
    terrain_cells: Dict[Tuple[int, int], TerrainCellRenderInfo] = field(default_factory=dict)
    routes: List[RouteRenderInfo] = field(default_factory=list)
    atlas_layout: Optional["AtlasLayout"] = None


# ------------------------------------------------------------------
# Data extraction (domain → intermediate)
# ------------------------------------------------------------------

def build_map_info(
    world: "World",
    highlight_location: Optional[str] = None,
) -> MapRenderInfo:
    """Extract a ``MapRenderInfo`` snapshot from a live ``World``.

    This is the *only* function that touches ``World`` / ``LocationState``
    attributes.  Renderers only consume the intermediate representation.
    """
    from ..terrain import AtlasLayout, BIOME_GLYPHS

    info = MapRenderInfo(
        world_name=world.name,
        year=world.year,
        width=world.width,
        height=world.height,
        atlas_layout=(
            AtlasLayout.from_dict(world.atlas_layout.to_dict())
            if world.atlas_layout is not None else None
        ),
    )

    death_site_location_ids = {
        rec.location_id for rec in world.event_records[-120:]
        if rec.kind in EVENT_KINDS_FATAL and rec.location_id
    }

    # Build site coordinate lookup
    site_at: Dict[Tuple[int, int], "Site"] = {}
    if world.sites:
        for site in world.sites:
            site_at[(site.x, site.y)] = site

    # Populate terrain cell render info for every terrain coordinate
    if world.terrain_map is not None:
        for (tx, ty), tcell in world.terrain_map.cells.items():
            info.terrain_cells[(tx, ty)] = TerrainCellRenderInfo(
                x=tx, y=ty,
                biome=tcell.biome,
                glyph=tcell.glyph,
                elevation=tcell.elevation,
                moisture=tcell.moisture,
                temperature=tcell.temperature,
            )

    # Populate route render info
    for route in world.routes:
        info.routes.append(RouteRenderInfo(
            route_id=route.route_id,
            from_site_id=route.from_site_id,
            to_site_id=route.to_site_id,
            route_type=route.route_type,
            blocked=route.blocked,
        ))

    alive_counts_by_location: Dict[str, int] = {}
    for character in world.characters:
        if character.alive:
            alive_counts_by_location[character.location_id] = (
                alive_counts_by_location.get(character.location_id, 0) + 1
            )

    for (x, y), loc in world.grid.items():
        is_highlight = (
            highlight_location is not None
            and (loc.id == highlight_location or loc.canonical_name == highlight_location)
        )
        population = alive_counts_by_location.get(loc.id, 0)
        danger_band = "low" if loc.danger < 34 else "high" if loc.danger >= 67 else "medium"
        traffic_band = "low" if loc.traffic < 34 else "high" if loc.traffic >= 67 else "medium"
        rumor_heat_band = "low" if loc.rumor_heat < 34 else "high" if loc.rumor_heat >= 67 else "medium"

        # Terrain overlay fields
        terrain_biome = "plains"
        terrain_glyph = ","
        terrain_elevation = 128
        terrain_moisture = 128
        terrain_temperature = 128
        if world.terrain_map is not None:
            tcell = world.terrain_map.get(x, y)
            if tcell is not None:
                terrain_biome = tcell.biome
                terrain_glyph = BIOME_GLYPHS.get(tcell.biome, "?")
                terrain_elevation = tcell.elevation
                terrain_moisture = tcell.moisture
                terrain_temperature = tcell.temperature

        site = site_at.get((x, y))
        has_site = site is not None
        site_type = site.site_type if site else loc.region_type
        site_importance = site.importance if site else 50

        info.cells[(x, y)] = MapCellInfo(
            location_id=loc.id,
            canonical_name=loc.canonical_name,
            region_type=loc.region_type,
            icon="*" if is_highlight else loc.icon,
            safety_label=loc.safety_label,
            danger=loc.danger,
            traffic_indicator=loc.traffic_indicator,
            population=population,
            x=x,
            y=y,
            highlighted=is_highlight,
            prosperity=loc.prosperity,
            prosperity_label=loc.prosperity_label,
            mood=loc.mood,
            mood_label=loc.mood_label,
            rumor_heat=loc.rumor_heat,
            road_condition=loc.road_condition,
            danger_band=danger_band,
            traffic_band=traffic_band,
            rumor_heat_band=rumor_heat_band,
            has_memorial=bool(loc.memorial_ids),
            has_alias=bool(loc.aliases),
            recent_death_site=loc.id in death_site_location_ids,
            terrain_biome=terrain_biome,
            terrain_glyph=terrain_glyph,
            terrain_elevation=terrain_elevation,
            terrain_moisture=terrain_moisture,
            terrain_temperature=terrain_temperature,
            has_site=has_site,
            site_type=site_type,
            site_importance=site_importance,
            atlas_x=site.atlas_x if site else -1,
            atlas_y=site.atlas_y if site else -1,
        )
    return info


# ------------------------------------------------------------------
# ASCII renderer (intermediate → string)
# ------------------------------------------------------------------

def _fit(text: str, width: int) -> str:
    """Shorthand for ``fit_display_width`` inside the renderer."""
    return fit_display_width(text, width)


def render_map_ascii(info: MapRenderInfo) -> str:
    """Render a ``MapRenderInfo`` as a stable ASCII grid.

    Cells that contain a site (``info.cells``) are rendered with full
    detail (name, type, safety, danger, traffic, population).  Cells
    that have terrain but no site (``info.terrain_cells``) are
    rendered with their biome glyph and biome name.  Cells with
    neither are shown as ``?`` placeholders.
    """
    cell_width = 20
    inner_width = info.width * cell_width + (info.width - 1)
    border = "  +" + "-" * inner_width + "+"
    header = f" {tr('map_title')}: {info.world_name} | {tr('map_year')}: {info.year}"
    lines: List[str] = [
        border,
        f"  |{_fit(header, inner_width)}|",
        border,
    ]

    for y in range(info.height):
        row_names: List[str] = []
        row_types: List[str] = []
        row_safety: List[str] = []
        row_danger: List[str] = []
        row_traffic: List[str] = []
        row_pops: List[str] = []

        for x in range(info.width):
            cell = info.cells.get((x, y))
            if cell is not None:
                # Site cell — full detail
                region_name = tr_term(cell.region_type)
                row_names.append(_fit(f" {cell.icon} {cell.canonical_name}", cell_width))
                row_types.append(_fit(f" {tr('map_type')}: {region_name}", cell_width))
                row_safety.append(_fit(f" {tr('map_safety')}: {cell.safety_label}", cell_width))
                row_danger.append(_fit(f" {tr('map_danger')}: {cell.danger:>3}", cell_width))
                row_traffic.append(_fit(f" {tr('map_traffic')}: {cell.traffic_indicator}", cell_width))
                row_pops.append(_fit(f" {tr('map_population')}: {cell.population}", cell_width))
                continue

            # Terrain-only cell — show biome glyph and name
            tcell = info.terrain_cells.get((x, y))
            if tcell is not None:
                biome_name = tr_term(tcell.biome)
                row_names.append(_fit(f" {tcell.glyph} ({biome_name})", cell_width))
                row_types.append(_fit(f" {tr('map_terrain')}: {biome_name}", cell_width))
                blank = " " * cell_width
                row_safety.append(blank)
                row_danger.append(blank)
                row_traffic.append(blank)
                row_pops.append(blank)
                continue

            # No data at all — placeholder
            blank = " " * cell_width
            row_names.append(_fit(" ? ???", cell_width))
            row_types.append(blank)
            row_safety.append(blank)
            row_danger.append(blank)
            row_traffic.append(blank)
            row_pops.append(blank)

        lines.append("  |" + "|".join(row_names) + "|")
        lines.append("  |" + "|".join(row_types) + "|")
        lines.append("  |" + "|".join(row_safety) + "|")
        lines.append("  |" + "|".join(row_danger) + "|")
        lines.append("  |" + "|".join(row_traffic) + "|")
        lines.append("  |" + "|".join(row_pops) + "|")
        lines.append(border)

    return "\n".join(lines)


# ------------------------------------------------------------------
# Overlay markers — colour-independent symbol design
# ------------------------------------------------------------------

#: Overlay marker for danger band
_DANGER_MARKERS: Dict[str, str] = {"low": " ", "medium": ".", "high": "!"}
#: Overlay marker for traffic band
_TRAFFIC_MARKERS: Dict[str, str] = {"low": " ", "medium": "o", "high": "O"}
#: Overlay marker for rumor heat band
_RUMOR_MARKERS: Dict[str, str] = {"low": " ", "medium": "~", "high": "?"}
_MAX_REGION_STANDOUT_ITEMS = 4
_OPEN_ROUTE_MARKER = "<->"
_BLOCKED_ROUTE_MARKER = "x->"
_UNKNOWN_ROUTE_TYPE_PRIORITY = 99
_REACHABILITY_OPEN = 0
_REACHABILITY_VISIBLE = 1
_REACHABILITY_BLOCKED = 2
_ROUTE_TYPE_PRIORITY: Dict[str, int] = {
    "road": 0,
    "mountain_pass": 1,
    "river": 2,
    "trail": 3,
}


def _band_label(band: str) -> str:
    return tr(f"map_band_{band}")


def _overlay_suffix(cell: MapCellInfo) -> str:
    """Build a compact overlay suffix string for a site cell.

    The suffix encodes danger / traffic / rumor / memorial / alias /
    death in 1-6 chars so a colourless terminal can still convey meaning.
    """
    parts: List[str] = []
    if cell.danger_band == "high":
        parts.append("!")
    if cell.traffic_band == "high":
        parts.append("$")
    if cell.rumor_heat_band == "high":
        parts.append("?")
    if cell.has_memorial:
        parts.append("m")
    if cell.has_alias:
        parts.append("a")
    if cell.recent_death_site:
        parts.append("+")
    return "".join(parts)


def _route_endpoint_name(cells_by_id: Dict[str, MapCellInfo], location_id: str) -> str:
    """Return a human-readable site name for a route endpoint."""
    cell = cells_by_id.get(location_id)
    return cell.canonical_name if cell is not None else location_id


def _route_other_endpoint(route: RouteRenderInfo, center_location_id: str) -> str:
    """Return the endpoint on the far side of a route from the current center."""
    if route.from_site_id == center_location_id:
        return route.to_site_id
    return route.from_site_id


def _pick_standout_route(
    region_routes: List[RouteRenderInfo],
    center_location_id: str,
    cells_by_id: Dict[str, MapCellInfo],
) -> Optional[RouteRenderInfo]:
    """Pick the single route worth calling out in the compact region summary."""
    open_routes = [route for route in region_routes if not route.blocked]
    if not open_routes:
        return None
    return min(
        open_routes,
        key=lambda route: (
            _ROUTE_TYPE_PRIORITY.get(route.route_type, _UNKNOWN_ROUTE_TYPE_PRIORITY),
            _route_endpoint_name(cells_by_id, _route_other_endpoint(route, center_location_id)).lower(),
        ),
    )


def _pick_blocked_route_notice(
    region_routes: List[RouteRenderInfo],
    center_location_id: str,
    cells_by_id: Dict[str, MapCellInfo],
) -> Optional[RouteRenderInfo]:
    """Pick one blocked route to surface separately in the region summary."""
    blocked_routes = [route for route in region_routes if route.blocked]
    if not blocked_routes:
        return None
    return min(
        blocked_routes,
        key=lambda route: (
            _ROUTE_TYPE_PRIORITY.get(route.route_type, _UNKNOWN_ROUTE_TYPE_PRIORITY),
            _route_endpoint_name(cells_by_id, _route_other_endpoint(route, center_location_id)).lower(),
        ),
    )


def _pick_region_danger_target(
    visible_cells: List[MapCellInfo],
    center_cell: MapCellInfo,
    connected_open_ids: Set[str],
    connected_blocked_ids: Set[str],
) -> Optional[MapCellInfo]:
    """Return one danger target using decision-oriented region priorities."""
    danger_candidates = [
        cell for cell in visible_cells
        if cell.location_id != center_cell.location_id and cell.danger_band == "high"
    ]
    if not danger_candidates:
        return None

    def priority(cell: MapCellInfo) -> Tuple[int, int, int, str]:
        """Rank candidates by (reachability, negative cell.danger, distance, name)."""
        reachability = _region_reachability_tier(
            cell.location_id,
            connected_open_ids,
            connected_blocked_ids,
        )
        distance = abs(cell.x - center_cell.x) + abs(cell.y - center_cell.y)
        return (
            reachability,
            -cell.danger,
            distance,
            cell.canonical_name.lower(),
        )

    return min(danger_candidates, key=priority)


def _pick_region_rumor_target(
    visible_cells: List[MapCellInfo],
    center_cell: MapCellInfo,
    connected_open_ids: Set[str],
    connected_blocked_ids: Set[str],
) -> Optional[MapCellInfo]:
    """Return one rumor hotspot using the same local-decision priorities."""
    rumor_candidates = [cell for cell in visible_cells if cell.rumor_heat_band == "high"]
    if not rumor_candidates:
        return None

    def priority(cell: MapCellInfo) -> Tuple[int, int, int, str]:
        """Rank candidates by (reachability, negative cell.rumor_heat, distance, name)."""
        reachability = _region_reachability_tier(
            cell.location_id,
            connected_open_ids,
            connected_blocked_ids,
        )
        distance = abs(cell.x - center_cell.x) + abs(cell.y - center_cell.y)
        return (
            reachability,
            -cell.rumor_heat,
            distance,
            cell.canonical_name.lower(),
        )

    return min(rumor_candidates, key=priority)


def _region_reachability_tier(
    location_id: str,
    connected_open_ids: Set[str],
    connected_blocked_ids: Set[str],
) -> int:
    """Return region summary reachability tier for a visible site."""
    if location_id in connected_open_ids:
        # 0 = directly reachable by an open route from the current center.
        return _REACHABILITY_OPEN
    if location_id not in connected_blocked_ids:
        # 1 = visible in the region, but not directly route-linked from center.
        return _REACHABILITY_VISIBLE
    # 2 = route-linked from center, but only through a blocked route.
    return _REACHABILITY_BLOCKED


def _has_world_memory(
    cell: MapCellInfo,
    memorials_by_site: Dict[str, List[str]],
    aliases_by_site: Dict[str, List[str]],
    traces_by_site: Dict[str, List[str]],
) -> bool:
    """Return whether a site has explicit world-memory entries to show."""
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
    """Return whether a site should be called out as a landmark."""
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
    """Build a typed landmark summary line for one site."""
    # Memorials / aliases may come from explicit detail payloads or from the
    # cell's baked overlay flags. Live traces only exist in explicit world-memory
    # payloads, while recent death is an event-derived overlay on the cell.
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
    """Prefer explicit memory on the center site, then any landmark signal nearby."""
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


# ------------------------------------------------------------------
# PR-G2 Layer 1: World Overview
# ------------------------------------------------------------------

def render_world_overview(info: MapRenderInfo) -> str:
    """Render a compact terrain-glyph world map with overlay markers.

    Each terrain cell is shown as its biome glyph (1 char).  Cells
    that contain a site are normally shown using the site's first
    letter in uppercase; when overlays are present, the site's glyph
    is replaced by the first overlay marker.  Highlighted cells always
    show ``*`` regardless of overlays.

    A legend is appended so the map is self-documenting.
    """
    lines: List[str] = []
    header = f"  === {tr('map_overview_title')}: {info.world_name} ({tr('map_year')}: {info.year}) ==="
    lines.append(header)
    lines.append("")

    # Column numbers header
    col_hdr = "    " + "".join(f"{x % 10}" for x in range(info.width))
    lines.append(col_hdr)
    lines.append("   +" + "-" * info.width + "+")

    for y in range(info.height):
        row_chars: List[str] = []
        for x in range(info.width):
            cell = info.cells.get((x, y))
            if cell is not None:
                # Site cell: highlight always wins, then overlay, then first letter
                overlay = _overlay_suffix(cell)
                if cell.highlighted:
                    row_chars.append("*")
                elif overlay:
                    # Show first overlay marker as the cell char
                    row_chars.append(overlay[0])
                else:
                    row_chars.append(cell.canonical_name[0].upper() if cell.canonical_name else "@")
            else:
                tcell = info.terrain_cells.get((x, y))
                if tcell is not None:
                    row_chars.append(tcell.glyph)
                else:
                    row_chars.append(" ")
        lines.append(f"  {y % 10}|{''.join(row_chars)}|")

    lines.append("   +" + "-" * info.width + "+")

    # --- Site list with overlays ---
    lines.append("")
    lines.append(f"  {tr('map_overview_sites')}:")
    site_cells = sorted(info.cells.values(), key=lambda c: (c.y, c.x))
    cells_by_id: Dict[str, MapCellInfo] = {
        c.location_id: c for c in info.cells.values()
    }
    for cell in site_cells:
        overlay = _overlay_suffix(cell)
        overlay_str = f" [{overlay}]" if overlay else ""
        pop_str = f" pop:{cell.population}" if cell.population else ""
        lines.append(
            f"    ({cell.x},{cell.y}) {cell.canonical_name}"
            f" - {tr_term(cell.region_type)}{overlay_str}{pop_str}"
        )

    # --- Route summary ---
    if info.routes:
        lines.append("")
        lines.append(f"  {tr('map_overview_routes')}:")
        for r in info.routes:
            blocked = f" {tr('route_blocked')}" if r.blocked else ""
            from_name = _route_endpoint_name(cells_by_id, r.from_site_id)
            to_name = _route_endpoint_name(cells_by_id, r.to_site_id)
            lines.append(
                f"    {from_name} <-> {to_name}"
                f" ({tr_term(r.route_type)}){blocked}"
            )

    # --- Legend ---
    lines.append("")
    lines.append(f"  {tr('map_legend_title')}:")
    lines.append(f"    {tr('map_legend_terrain')}:")
    from ..terrain import BIOME_GLYPHS
    for biome, glyph in BIOME_GLYPHS.items():
        lines.append(f"      {glyph} = {tr_term(biome)}")
    lines.append(f"    {tr('map_legend_overlays')}:")
    lines.append(f"      ! = {tr('map_legend_danger_high')}")
    lines.append(f"      $ = {tr('map_legend_traffic_high')}")
    lines.append(f"      ? = {tr('map_legend_rumor_high')}")
    lines.append(f"      m = {tr('map_legend_memorial')}")
    lines.append(f"      a = {tr('map_legend_alias')}")
    lines.append(f"      + = {tr('map_legend_recent_death')}")
    lines.append(f"      * = {tr('map_legend_highlighted')}")

    return "\n".join(lines)


# ------------------------------------------------------------------
# PR-G2 Layer 2: Region Map
# ------------------------------------------------------------------

RegionBounds = Tuple[int, int, int, int]


def _find_region_center_cell(info: MapRenderInfo, center_location_id: str) -> Optional[MapCellInfo]:
    """Return the selected centre cell, if present."""
    for cell in info.cells.values():
        if cell.location_id == center_location_id:
            return cell
    return None


def _region_bounds(info: MapRenderInfo, center_cell: MapCellInfo, radius: int) -> RegionBounds:
    """Return inclusive map bounds for a region excerpt."""
    cx, cy = center_cell.x, center_cell.y
    return (
        max(0, cx - radius),
        min(info.width - 1, cx + radius),
        max(0, cy - radius),
        min(info.height - 1, cy + radius),
    )


def _visible_region_cells(info: MapRenderInfo, bounds: RegionBounds) -> List[MapCellInfo]:
    """Return site cells inside the region bounds in render order."""
    x_min, x_max, y_min, y_max = bounds
    return [
        cell for cell in sorted(info.cells.values(), key=lambda c: (c.y, c.x))
        if x_min <= cell.x <= x_max and y_min <= cell.y <= y_max
    ]


def _build_region_route_layer(info: MapRenderInfo, bounds: RegionBounds) -> Dict[Tuple[int, int], str]:
    """Build route glyphs for routes whose endpoints are both visible."""
    from .atlas_renderer import _bresenham, _ROUTE_LINE

    x_min, x_max, y_min, y_max = bounds
    rw = x_max - x_min + 1
    rh = y_max - y_min + 1
    route_layer: Dict[Tuple[int, int], str] = {}
    site_positions: Set[Tuple[int, int]] = set()
    for cell in info.cells.values():
        if x_min <= cell.x <= x_max and y_min <= cell.y <= y_max:
            site_positions.add((cell.x - x_min, cell.y - y_min))

    cell_pos: Dict[str, Tuple[int, int]] = {
        c.location_id: (c.x, c.y) for c in info.cells.values()
    }
    for route in info.routes:
        fp = cell_pos.get(route.from_site_id)
        tp = cell_pos.get(route.to_site_id)
        if not fp or not tp:
            continue
        if not (x_min <= fp[0] <= x_max and y_min <= fp[1] <= y_max):
            continue
        if not (x_min <= tp[0] <= x_max and y_min <= tp[1] <= y_max):
            continue
        path = _bresenham(fp[0] - x_min, fp[1] - y_min, tp[0] - x_min, tp[1] - y_min)
        chars = _ROUTE_LINE.get(route.route_type, ("-", "|", "/", "\\"))
        if route.blocked:
            chars = ("x", "x", "x", "x")
        for i, (px, py) in enumerate(path):
            if (px, py) in site_positions or not (0 <= px < rw and 0 <= py < rh):
                continue
            if i > 0:
                ddx = px - path[i - 1][0]
                ddy = py - path[i - 1][1]
            elif i < len(path) - 1:
                ddx = path[i + 1][0] - px
                ddy = path[i + 1][1] - py
            else:
                ddx, ddy = 1, 0
            if ddy == 0:
                ch = chars[0]
            elif ddx == 0:
                ch = chars[1]
            elif (ddx > 0) != (ddy > 0):
                ch = chars[2]
            else:
                ch = chars[3]
            route_layer[(px, py)] = ch
    return route_layer


def _append_region_grid(
    lines: List[str],
    info: MapRenderInfo,
    center_location_id: str,
    bounds: RegionBounds,
    route_layer: Dict[Tuple[int, int], str],
) -> None:
    """Append the region map grid."""
    x_min, x_max, y_min, y_max = bounds
    col_nums = "".join(f"{x % 10}" for x in range(x_min, x_max + 1))
    lines.append(f"      {col_nums}")
    region_border = "     +" + "-" * (x_max - x_min + 1) + "+"
    lines.append(region_border)

    for y in range(y_min, y_max + 1):
        row_chars: List[str] = []
        for x in range(x_min, x_max + 1):
            cell = info.cells.get((x, y))
            if cell is not None:
                if cell.location_id == center_location_id:
                    row_chars.append("@")
                else:
                    row_chars.append(cell.canonical_name[0].upper() if cell.canonical_name else "o")
            elif (x - x_min, y - y_min) in route_layer:
                row_chars.append(route_layer[(x - x_min, y - y_min)])
            else:
                tcell = info.terrain_cells.get((x, y))
                row_chars.append(tcell.glyph if tcell else " ")
        lines.append(f"    {y % 10}|{''.join(row_chars)}|")

    lines.append(region_border)


def _center_route_connections(
    routes: List[RouteRenderInfo],
    center_location_id: str,
) -> Tuple[Set[str], Set[str]]:
    """Return open and blocked route destinations connected to the centre."""
    connected_open_ids: Set[str] = set()
    connected_blocked_ids: Set[str] = set()
    for route in routes:
        if route.from_site_id == center_location_id:
            if route.blocked:
                connected_blocked_ids.add(route.to_site_id)
            else:
                connected_open_ids.add(route.to_site_id)
        elif route.to_site_id == center_location_id:
            if route.blocked:
                connected_blocked_ids.add(route.from_site_id)
            else:
                connected_open_ids.add(route.from_site_id)
    return connected_open_ids, connected_blocked_ids


def _center_region_routes(routes: List[RouteRenderInfo], center_location_id: str) -> List[RouteRenderInfo]:
    """Return routes directly connected to the centre site."""
    return [
        route for route in routes
        if route.from_site_id == center_location_id or route.to_site_id == center_location_id
    ]


def _region_focus_lines(
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
    """Build the standout focus lines for a region."""
    center_location_id = center_cell.location_id
    standout_lines: List[str] = []
    standout_route = _pick_standout_route(region_routes, center_location_id, cells_by_id)
    if standout_route is not None:
        other_id = _route_other_endpoint(standout_route, center_location_id)
        standout_lines.append(
            tr(
                "map_region_focus_route",
                destination=_route_endpoint_name(cells_by_id, other_id),
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
    blocked_notice = _pick_blocked_route_notice(region_routes, center_location_id, cells_by_id)
    if blocked_notice is not None:
        blocked_destination = _route_endpoint_name(
            cells_by_id,
            _route_other_endpoint(blocked_notice, center_location_id),
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


def _append_region_focus(lines: List[str], standout_lines: List[str]) -> None:
    """Append the focus section when there is anything to show."""
    if not standout_lines:
        return
    lines.append("")
    lines.append(f"  {tr('map_region_focus')}:")
    for item in standout_lines[:_MAX_REGION_STANDOUT_ITEMS]:
        lines.append(f"    - {item}")
    lines.append("")


def _append_nearby_sites(
    lines: List[str],
    visible_cells: List[MapCellInfo],
    center_location_id: str,
    connected_open_ids: Set[str],
    connected_blocked_ids: Set[str],
) -> None:
    """Append nearby site detail lines."""
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


def _append_region_routes(
    lines: List[str],
    region_routes: List[RouteRenderInfo],
    cells_by_id: Dict[str, MapCellInfo],
) -> None:
    """Append route detail lines."""
    if not region_routes:
        return
    lines.append(f"  {tr('map_region_routes')}:")
    for route in region_routes:
        blocked = f" {tr('route_blocked')}" if route.blocked else ""
        from_name = _route_endpoint_name(cells_by_id, route.from_site_id)
        to_name = _route_endpoint_name(cells_by_id, route.to_site_id)
        lines.append(
            f"    {from_name} <-> {to_name}"
            f" ({tr_term(route.route_type)}){blocked}"
        )


def _append_region_landmarks(
    lines: List[str],
    visible_cells: List[MapCellInfo],
    memorials: Dict[str, List[str]],
    aliases: Dict[str, List[str]],
    traces: Dict[str, List[str]],
    endonyms: Dict[str, str],
) -> None:
    """Append native names and world-memory landmark context."""
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


def render_region_map(
    info: MapRenderInfo,
    center_location_id: str,
    radius: int = 2,
    *,
    site_memorials: Optional[Dict[str, List[str]]] = None,
    site_aliases: Optional[Dict[str, List[str]]] = None,
    site_traces: Optional[Dict[str, List[str]]] = None,
    site_endonyms: Optional[Dict[str, str]] = None,
) -> str:
    """Render a zoomed region map around a selected site.

    Shows a (2*radius+1) square excerpt of the terrain grid centred
    on the site's coordinates, with route connections and per-site
    status summaries.
    """
    center_cell = _find_region_center_cell(info, center_location_id)
    if center_cell is None:
        return f"  {tr('map_region_not_found', location=center_location_id)}"

    lines: List[str] = []
    lines.append(
        f"  === {tr('map_region_title')}: {center_cell.canonical_name} ==="
    )
    lines.append("")

    cells_by_id: Dict[str, MapCellInfo] = {
        c.location_id: c for c in info.cells.values()
    }
    bounds = _region_bounds(info, center_cell, radius)
    route_layer = _build_region_route_layer(info, bounds)
    _append_region_grid(lines, info, center_location_id, bounds, route_layer)

    connected_open_ids, connected_blocked_ids = _center_route_connections(info.routes, center_location_id)
    region_routes = _center_region_routes(info.routes, center_location_id)
    visible_cells = _visible_region_cells(info, bounds)

    memorials = site_memorials or {}
    aliases = site_aliases or {}
    traces = site_traces or {}
    endonyms = site_endonyms or {}
    standout_lines = _region_focus_lines(
        visible_cells,
        center_cell,
        region_routes,
        cells_by_id,
        connected_open_ids,
        connected_blocked_ids,
        memorials,
        aliases,
        traces,
        endonyms,
    )
    _append_region_focus(lines, standout_lines)
    _append_nearby_sites(lines, visible_cells, center_location_id, connected_open_ids, connected_blocked_ids)
    _append_region_routes(lines, region_routes, cells_by_id)
    _append_region_landmarks(lines, visible_cells, memorials, aliases, traces, endonyms)

    return "\n".join(lines)


# ------------------------------------------------------------------
# PR-G2 Layer 3: Location Detail
# ------------------------------------------------------------------

def render_location_detail(
    info: MapRenderInfo,
    location_id: str,
    memorials: Optional[List[str]] = None,
    aliases: Optional[List[str]] = None,
    live_traces: Optional[List[str]] = None,
    generated_endonym: Optional[str] = None,
    recent_events: Optional[List[str]] = None,
    rumor_lines: Optional[List[str]] = None,
    connected_routes: Optional[List[str]] = None,
) -> str:
    """Render a detailed single-site view with AA panel.

    Shows terrain, stats, overlays, memorials, aliases, and recent
    traces for one location.
    """
    cell: Optional[MapCellInfo] = None
    for c in info.cells.values():
        if c.location_id == location_id:
            cell = c
            break
    if cell is None:
        return f"  {tr('map_detail_not_found', location=location_id)}"

    w = 50
    border = "  +" + "-" * w + "+"
    lines: List[str] = [border]

    # Header
    title = f" {cell.icon} {cell.canonical_name} ({tr_term(cell.region_type)})"
    lines.append(f"  |{_fit(title, w)}|")
    lines.append(border)

    # Terrain info
    terrain_label = tr('map_terrain')
    biome_name = tr_term(cell.terrain_biome)
    lines.append(f"  |{_fit(f' {terrain_label}: {biome_name} ({cell.terrain_glyph})', w)}|")
    elev_label = tr('map_detail_elevation')
    moist_label = tr('map_detail_moisture')
    temp_label = tr('map_detail_temperature')
    elev_line = (
        f" {elev_label}:{cell.terrain_elevation}"
        f" {moist_label}:{cell.terrain_moisture}"
        f" {temp_label}:{cell.terrain_temperature}"
    )
    lines.append(f"  |{_fit(elev_line, w)}|")
    lines.append(border)

    # Stats
    safety_label = tr('map_safety')
    danger_label = tr('map_danger')
    traffic_label = tr('map_traffic')
    pop_label = tr('map_population')
    prosperity_label = tr('map_detail_prosperity')
    mood_label = tr('map_detail_mood')
    rumor_label = tr('map_detail_rumor_heat')

    lines.append(f"  |{_fit(f' {safety_label}: {cell.safety_label}', w)}|")
    lines.append(f"  |{_fit(f' {danger_label}: {cell.danger:>3} ({_band_label(cell.danger_band)})', w)}|")
    lines.append(f"  |{_fit(f' {traffic_label}: {cell.traffic_indicator} ({_band_label(cell.traffic_band)})', w)}|")
    lines.append(f"  |{_fit(f' {pop_label}: {cell.population}', w)}|")
    lines.append(f"  |{_fit(f' {prosperity_label}: {cell.prosperity_label} ({cell.prosperity})', w)}|")
    lines.append(f"  |{_fit(f' {mood_label}: {cell.mood_label} ({cell.mood})', w)}|")
    lines.append(f"  |{_fit(f' {rumor_label}: {cell.rumor_heat} ({_band_label(cell.rumor_heat_band)})', w)}|")
    lines.append(border)

    # Overlays
    overlay_items: List[str] = []
    if cell.has_memorial:
        overlay_items.append(tr("map_legend_memorial"))
    if cell.has_alias:
        overlay_items.append(tr("map_legend_alias"))
    if cell.recent_death_site:
        overlay_items.append(tr("map_legend_recent_death"))
    if overlay_items:
        overlay_line = ", ".join(overlay_items)
        markers_label = tr('map_detail_markers')
        lines.append(f"  |{_fit(f' {markers_label}: {overlay_line}', w)}|")
        lines.append(border)

    if generated_endonym:
        endonym_label = tr('location_endonym_label')
        lines.append(f"  |{_fit(f' {endonym_label}: {generated_endonym}', w)}|")

    # Aliases
    if aliases:
        aliases_label = tr('location_aliases_label')
        aliases_str = ", ".join(aliases)
        lines.append(f"  |{_fit(f' {aliases_label}: {aliases_str}', w)}|")

    # Memorials
    if memorials:
        mem_label = tr('location_memorials_label')
        lines.append(f"  |{_fit(f' {mem_label}:', w)}|")
        for mem in memorials[:5]:
            lines.append(f"  |{_fit(f'   {mem}', w)}|")

    # Live traces
    if live_traces:
        traces_label = tr('location_live_traces_label')
        lines.append(f"  |{_fit(f' {traces_label}:', w)}|")
        for trace in live_traces[:5]:
            lines.append(f"  |{_fit(f'   - {trace}', w)}|")

    if connected_routes:
        routes_label = tr('map_region_routes')
        lines.append(f"  |{_fit(f' {routes_label}:', w)}|")
        for route in connected_routes[:5]:
            lines.append(f"  |{_fit(f'   - {route}', w)}|")

    if recent_events:
        events_label = tr('location_recent_events_label')
        lines.append(f"  |{_fit(f' {events_label}:', w)}|")
        for event in recent_events[:5]:
            lines.append(f"  |{_fit(f'   - {event}', w)}|")

    if rumor_lines:
        rumors_label = tr('rumor_section_title')
        lines.append(f"  |{_fit(f' {rumors_label}:', w)}|")
        for rumor in rumor_lines[:5]:
            lines.append(f"  |{_fit(f'   - {rumor}', w)}|")

    if (
        generated_endonym
        or aliases
        or memorials
        or live_traces
        or connected_routes
        or recent_events
        or rumor_lines
    ):
        lines.append(border)

    return "\n".join(lines)

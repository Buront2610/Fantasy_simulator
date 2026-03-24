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
from .ui_helpers import fit_display_width

if TYPE_CHECKING:
    from ..terrain import Site
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
    from ..terrain import BIOME_GLYPHS

    info = MapRenderInfo(
        world_name=world.name,
        year=world.year,
        width=world.width,
        height=world.height,
    )

    death_site_location_ids = {
        rec.location_id for rec in world.event_records[-120:]
        if rec.kind in ("death", "battle_fatal", "adventure_death") and rec.location_id
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

    for (x, y), loc in world.grid.items():
        is_highlight = (
            highlight_location is not None
            and (loc.id == highlight_location or loc.canonical_name == highlight_location)
        )
        population = len(world.get_characters_at_location(loc.id))
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
            lines.append(
                f"    {r.from_site_id} <-> {r.to_site_id}"
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

def render_region_map(
    info: MapRenderInfo,
    center_location_id: str,
    radius: int = 2,
) -> str:
    """Render a zoomed region map around a selected site.

    Shows a (2*radius+1) square excerpt of the terrain grid centred
    on the site's coordinates, with route connections and per-site
    status summaries.
    """
    # Find the centre cell
    center_cell: Optional[MapCellInfo] = None
    for cell in info.cells.values():
        if cell.location_id == center_location_id:
            center_cell = cell
            break
    if center_cell is None:
        return f"  {tr('map_region_not_found', location=center_location_id)}"

    cx, cy = center_cell.x, center_cell.y
    lines: List[str] = []
    lines.append(
        f"  === {tr('map_region_title')}: {center_cell.canonical_name} ==="
    )
    lines.append("")

    # Build the zoomed grid
    x_min = max(0, cx - radius)
    x_max = min(info.width - 1, cx + radius)
    y_min = max(0, cy - radius)
    y_max = min(info.height - 1, cy + radius)

    # Build a mini-canvas for route lines
    rw = x_max - x_min + 1
    rh = y_max - y_min + 1
    route_layer: Dict[Tuple[int, int], str] = {}
    site_positions: Set[Tuple[int, int]] = set()
    for cell in info.cells.values():
        if x_min <= cell.x <= x_max and y_min <= cell.y <= y_max:
            site_positions.add((cell.x - x_min, cell.y - y_min))

    for route in info.routes:
        fp = tp = None
        for c in info.cells.values():
            if c.location_id == route.from_site_id:
                fp = (c.x, c.y)
            if c.location_id == route.to_site_id:
                tp = (c.x, c.y)
        if not fp or not tp:
            continue
        # Both endpoints must be in the visible region
        if not (x_min <= fp[0] <= x_max and y_min <= fp[1] <= y_max):
            continue
        if not (x_min <= tp[0] <= x_max and y_min <= tp[1] <= y_max):
            continue
        from .atlas_renderer import _bresenham
        path = _bresenham(fp[0] - x_min, fp[1] - y_min, tp[0] - x_min, tp[1] - y_min)
        ch = "x" if route.blocked else "-"
        for px, py in path:
            if (px, py) not in site_positions and 0 <= px < rw and 0 <= py < rh:
                route_layer[(px, py)] = ch

    # Column header
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

    # --- Nearby sites detail ---
    lines.append("")
    lines.append(f"  {tr('map_region_nearby')}:")

    # Collect routes from centre
    connected_ids = set()
    for route in info.routes:
        if route.from_site_id == center_location_id:
            connected_ids.add(route.to_site_id)
        elif route.to_site_id == center_location_id:
            connected_ids.add(route.from_site_id)

    for cell in sorted(info.cells.values(), key=lambda c: (c.y, c.x)):
        if not (x_min <= cell.x <= x_max and y_min <= cell.y <= y_max):
            continue
        marker = "@" if cell.location_id == center_location_id else " "
        conn = "<->" if cell.location_id in connected_ids else "   "
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

    # --- Routes in this region ---
    region_routes = [
        r for r in info.routes
        if r.from_site_id == center_location_id or r.to_site_id == center_location_id
    ]
    if region_routes:
        lines.append("")
        lines.append(f"  {tr('map_region_routes')}:")
        for r in region_routes:
            blocked = f" {tr('route_blocked')}" if r.blocked else ""
            lines.append(
                f"    {r.from_site_id} <-> {r.to_site_id}"
                f" ({tr_term(r.route_type)}){blocked}"
            )

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
    lines.append(f"  |{_fit(f' {danger_label}: {cell.danger:>3} ({cell.danger_band})', w)}|")
    lines.append(f"  |{_fit(f' {traffic_label}: {cell.traffic_indicator} ({cell.traffic_band})', w)}|")
    lines.append(f"  |{_fit(f' {pop_label}: {cell.population}', w)}|")
    lines.append(f"  |{_fit(f' {prosperity_label}: {cell.prosperity_label} ({cell.prosperity})', w)}|")
    lines.append(f"  |{_fit(f' {mood_label}: {cell.mood_label} ({cell.mood})', w)}|")
    lines.append(f"  |{_fit(f' {rumor_label}: {cell.rumor_heat} ({cell.rumor_heat_band})', w)}|")
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

    if aliases or memorials or live_traces:
        lines.append(border)

    return "\n".join(lines)

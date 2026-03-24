"""
map_renderer.py - Map data extraction and ASCII rendering.

This module decouples the *data* that a map carries (``MapCellInfo``,
``MapRenderInfo``) from the *presentation* logic that turns that data
into an ASCII grid.

Domain code (``world.py``) now only needs to call ``build_map_info()``
to produce a renderer-agnostic snapshot.  The UI layer picks the
renderer it needs — currently ``render_map_ascii()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

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

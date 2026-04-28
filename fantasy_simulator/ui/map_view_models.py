"""Renderer-agnostic map view models and extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from ..narrative.constants import EVENT_KINDS_FATAL

if TYPE_CHECKING:
    from ..terrain import AtlasLayout, Site
    from ..world import World


@dataclass
class MapCellInfo:
    """Renderer-agnostic snapshot of one map cell."""

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
    prosperity: int = 50
    prosperity_label: str = ""
    mood: int = 50
    mood_label: str = ""
    rumor_heat: int = 0
    road_condition: int = 50
    danger_band: str = "medium"
    traffic_band: str = "medium"
    rumor_heat_band: str = "low"
    has_memorial: bool = False
    has_alias: bool = False
    recent_death_site: bool = False
    terrain_biome: str = "plains"
    terrain_glyph: str = ","
    terrain_elevation: int = 128
    terrain_moisture: int = 128
    terrain_temperature: int = 128
    has_site: bool = True
    site_type: str = ""
    site_importance: int = 50
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
    """Renderer-agnostic snapshot of a pure terrain cell with no site."""

    x: int
    y: int
    biome: str
    glyph: str
    elevation: int = 128
    moisture: int = 128
    temperature: int = 128


@dataclass
class MapRenderInfo:
    """Everything a renderer needs to draw the world map."""

    world_name: str
    year: int
    width: int
    height: int
    cells: Dict[Tuple[int, int], MapCellInfo] = field(default_factory=dict)
    terrain_cells: Dict[Tuple[int, int], TerrainCellRenderInfo] = field(default_factory=dict)
    routes: List[RouteRenderInfo] = field(default_factory=list)
    atlas_layout: Optional["AtlasLayout"] = None


def _band(value: int) -> str:
    if value < 34:
        return "low"
    if value >= 67:
        return "high"
    return "medium"


def build_map_info(
    world: "World",
    highlight_location: Optional[str] = None,
) -> MapRenderInfo:
    """Extract a renderer-agnostic map snapshot from a live world."""
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
    site_at: Dict[Tuple[int, int], "Site"] = {
        (site.x, site.y): site for site in world.sites
    }

    if world.terrain_map is not None:
        for (tx, ty), tcell in world.terrain_map.cells.items():
            info.terrain_cells[(tx, ty)] = TerrainCellRenderInfo(
                x=tx,
                y=ty,
                biome=tcell.biome,
                glyph=tcell.glyph,
                elevation=tcell.elevation,
                moisture=tcell.moisture,
                temperature=tcell.temperature,
            )

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
        info.cells[(x, y)] = MapCellInfo(
            location_id=loc.id,
            canonical_name=loc.canonical_name,
            region_type=loc.region_type,
            icon="*" if is_highlight else loc.icon,
            safety_label=loc.safety_label,
            danger=loc.danger,
            traffic_indicator=loc.traffic_indicator,
            population=alive_counts_by_location.get(loc.id, 0),
            x=x,
            y=y,
            highlighted=is_highlight,
            prosperity=loc.prosperity,
            prosperity_label=loc.prosperity_label,
            mood=loc.mood,
            mood_label=loc.mood_label,
            rumor_heat=loc.rumor_heat,
            road_condition=loc.road_condition,
            danger_band=_band(loc.danger),
            traffic_band=_band(loc.traffic),
            rumor_heat_band=_band(loc.rumor_heat),
            has_memorial=bool(loc.memorial_ids),
            has_alias=bool(loc.aliases),
            recent_death_site=loc.id in death_site_location_ids,
            terrain_biome=terrain_biome,
            terrain_glyph=terrain_glyph,
            terrain_elevation=terrain_elevation,
            terrain_moisture=terrain_moisture,
            terrain_temperature=terrain_temperature,
            has_site=site is not None,
            site_type=site.site_type if site else loc.region_type,
            site_importance=site.importance if site else 50,
            atlas_x=site.atlas_x if site else -1,
            atlas_y=site.atlas_y if site else -1,
        )
    return info

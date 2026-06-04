"""Renderer-agnostic map view models and extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

from ..content.setting_bundle_inspection import setting_entry_key
from ..narrative.constants import EVENT_KINDS_FATAL
from ..observation import build_world_change_report_projection

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
    recent_world_change_count: int = 0
    recent_world_change_categories: Tuple[str, ...] = ()
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
    controlling_faction_id: str = ""
    controlling_faction_name: str = ""


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


def _recent_death_site_ids(world: "World") -> set[str]:
    return {
        rec.location_id for rec in world.event_records[-120:]
        if rec.kind in EVENT_KINDS_FATAL and rec.location_id
    }


def _recent_world_change_overlays(world: "World") -> tuple[Dict[str, int], Dict[str, List[str]]]:
    counts: Dict[str, int] = {}
    categories_by_location: Dict[str, List[str]] = {}
    projection = build_world_change_report_projection(
        event_records=world.event_records[-120:],
    )
    for entry in projection.entries:
        for location_id in entry.location_ids:
            counts[location_id] = counts.get(location_id, 0) + 1
            categories = categories_by_location.setdefault(location_id, [])
            if entry.category not in categories:
                categories.append(entry.category)
    return counts, categories_by_location


def _copy_terrain_cells(info: MapRenderInfo, world: "World") -> None:
    if world.terrain_map is None:
        return
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


def _copy_routes(info: MapRenderInfo, world: "World") -> None:
    for route in world.routes:
        info.routes.append(RouteRenderInfo(
            route_id=route.route_id,
            from_site_id=route.from_site_id,
            to_site_id=route.to_site_id,
            route_type=route.route_type,
            blocked=route.blocked,
        ))


def _terrain_snapshot(world: "World", x: int, y: int) -> tuple[str, str, int, int, int]:
    from ..terrain import BIOME_GLYPHS

    if world.terrain_map is None:
        return "plains", ",", 128, 128, 128
    tcell = world.terrain_map.get(x, y)
    if tcell is None:
        return "plains", ",", 128, 128, 128
    return (
        tcell.biome,
        BIOME_GLYPHS.get(tcell.biome, "?"),
        tcell.elevation,
        tcell.moisture,
        tcell.temperature,
    )


def _alive_counts_by_location(world: "World") -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for character in world.characters:
        if character.alive:
            counts[character.location_id] = counts.get(character.location_id, 0) + 1
    return counts


def _faction_display_name(world: "World", faction_id: str | None) -> str:
    if not faction_id:
        return ""
    bundle = getattr(world, "_setting_bundle", None) or getattr(world, "setting_bundle", None)
    world_definition = getattr(bundle, "world_definition", None)
    faction_entries = getattr(world_definition, "faction_entries", None)
    if callable(faction_entries):
        faction_key = setting_entry_key(faction_id)
        for entry in faction_entries():
            display_name = getattr(entry, "display_name", "")
            if faction_id == display_name or faction_key == getattr(entry, "key", ""):
                return display_name
    return faction_id


def build_map_info(
    world: "World",
    highlight_location: Optional[str] = None,
) -> MapRenderInfo:
    """Extract a renderer-agnostic map snapshot from a live world."""
    from ..terrain import AtlasLayout

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

    death_site_location_ids = _recent_death_site_ids(world)
    world_change_counts, world_change_categories = _recent_world_change_overlays(world)
    site_at: Dict[Tuple[int, int], "Site"] = {
        (site.x, site.y): site for site in world.sites
    }

    _copy_terrain_cells(info, world)
    _copy_routes(info, world)
    alive_counts_by_location = _alive_counts_by_location(world)

    for (x, y), loc in world.grid.items():
        is_highlight = (
            highlight_location is not None
            and (loc.id == highlight_location or loc.canonical_name == highlight_location)
        )
        terrain_biome, terrain_glyph, terrain_elevation, terrain_moisture, terrain_temperature = _terrain_snapshot(
            world,
            x,
            y,
        )

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
            recent_world_change_count=world_change_counts.get(loc.id, 0),
            recent_world_change_categories=tuple(world_change_categories.get(loc.id, [])),
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
            controlling_faction_id=loc.controlling_faction_id or "",
            controlling_faction_name=_faction_display_name(world, loc.controlling_faction_id),
        )
    return info

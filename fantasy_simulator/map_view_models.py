"""Renderer-agnostic map view models and extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from .content.setting_bundle_inspection import setting_entry_key
from .map_place_profile import PlaceVisualProfile, build_place_visual_profile
from .narrative.constants import EVENT_KINDS_FATAL
from .observation import build_world_change_report_projection

if TYPE_CHECKING:
    from .terrain import AtlasLayout, Site
    from .world import World
    from .world_location_state import LocationState


@dataclass
class LocalMapCue:
    """Structured local map cue for filtering or visual emphasis."""

    tag: str
    category: str
    label: str
    priority: int
    causes: Tuple[str, ...] = ()
    culture_key: str = ""
    culture_label: str = ""


@dataclass(frozen=True)
class _LocalFeatureDerivation:
    """Internal cause ledger for a local map feature."""

    tag: str
    causes: Tuple[str, ...] = ()
    culture_key: str = ""
    culture_label: str = ""


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
    local_feature_tags: Tuple[str, ...] = ()
    local_feature_labels: Tuple[str, ...] = ()
    local_feature_cues: Tuple[LocalMapCue, ...] = ()
    visual_profile: PlaceVisualProfile = field(default_factory=PlaceVisualProfile)


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
    from .terrain import BIOME_GLYPHS

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


_LOCAL_FEATURE_DEFINITIONS = (
    ("gate", "site", 10),
    ("market", "site", 20),
    ("tower", "site", 25),
    ("bridge", "site", 30),
    ("shrine", "site", 35),
    ("inn", "site", 40),
    ("guild", "site", 45),
    ("mill", "site", 50),
    ("dock", "site", 55),
    ("forge", "site", 60),
    ("warehouse", "site", 65),
    ("stable", "site", 70),
    ("barracks", "site", 75),
    ("graveyard", "site", 80),
    ("library", "site", 85),
    ("ruined_house", "site", 90),
    ("workshop", "site", 95),
    ("farmstead", "site", 100),
    ("watch_camp", "site", 105),
    ("arena", "site", 110),
    ("notice_board", "site", 115),
    ("river", "terrain", 130),
    ("accident_site", "memory", 140),
    ("memorial", "memory", 150),
    ("trace", "memory", 160),
    ("blocked_route", "route", 170),
)
_INFERRED_BUILDING_RULES = (
    ("tower", ("tower", "watch", "keep", "fortress", "outpost")),
    ("mill", ("mill", "brook")),
    ("dock", ("port", "harbor", "harbour", "dock", "marsh")),
    ("forge", ("mine", "iron", "forge")),
    ("warehouse", ("port", "harbor", "harbour", "crossroads")),
    ("stable", ("crossroads", "outpost", "keep", "gate")),
    ("barracks", ("keep", "fortress", "outpost", "watch")),
    ("graveyard", ("ruin", "warrens", "grave")),
    ("library", ("monastery", "capital", "library")),
    ("ruined_house", ("ruin", "ashen")),
    ("workshop", ("guild", "mine", "town")),
    ("farmstead", ("farm", "mill", "vale", "plains")),
    ("watch_camp", ("watch", "outpost", "pass")),
)
_CULTURE_BUILDING_RULES = (
    (
        "aethic_common",
        (
            ("guild", ("city", "town", "capital", "market", "crossroads", "port")),
            ("inn", ("city", "town", "crossroads", "road", "port", "harbor", "harbour")),
            ("stable", ("city", "town", "crossroads", "road", "keep", "gate")),
            ("warehouse", ("city", "town", "market", "crossroads", "port", "harbor", "harbour")),
            ("notice_board", ("city", "town", "crossroads", "keep", "gate")),
        ),
    ),
    (
        "khazic",
        (
            ("forge", ("mountain", "mine", "pass", "summit", "iron", "stone")),
            ("warehouse", ("mine", "pass", "hold", "mountain", "iron")),
            ("barracks", ("keep", "outpost", "pass", "summit", "mountain")),
            ("workshop", ("mine", "hold", "mountain", "iron", "stone")),
        ),
    ),
    (
        "quenic",
        (
            ("shrine", ("monastery", "forest", "cove", "ley", "skyveil", "elderroot")),
            ("library", ("monastery", "court", "skyveil", "elderroot", "cove")),
            ("tower", ("monastery", "ley", "skyveil", "ridge")),
        ),
    ),
    (
        "sindral",
        (
            ("shrine", ("forest", "vale", "thornwood", "ashen", "verdant")),
            ("farmstead", ("vale", "forest", "plains", "verdant")),
            ("mill", ("vale", "river", "brook", "forest")),
        ),
    ),
    (
        "orcish_steppe",
        (
            ("watch_camp", ("plains", "outpost", "warrens", "swamp", "frontier", "pass")),
            ("barracks", ("outpost", "warrens", "frontier", "plains")),
            ("stable", ("plains", "steppe", "outpost", "frontier")),
            ("tower", ("outpost", "watch", "frontier")),
        ),
    ),
    (
        "proto_quenic",
        (
            ("graveyard", ("ruin", "ridge", "crater", "sunken", "dragonbone")),
            ("ruined_house", ("ruin", "crater", "sunken", "warrens")),
            ("library", ("ruin", "sunken", "dragonbone", "ancient")),
            ("shrine", ("ridge", "crater", "dragonbone", "ancient")),
        ),
    ),
    (
        "elder_speech",
        (
            ("library", ("monastery", "ruin", "ley", "ancient")),
            ("shrine", ("monastery", "ley", "ancient")),
            ("tower", ("monastery", "sky", "ley")),
        ),
    ),
)
_LOCAL_FEATURE_TAGS = {tag for tag, _category, _priority in _LOCAL_FEATURE_DEFINITIONS}


def _blocked_route_site_ids(world: "World") -> Set[str]:
    site_ids: Set[str] = set()
    for route in world.routes:
        if getattr(route, "blocked", False):
            site_ids.add(route.from_site_id)
            site_ids.add(route.to_site_id)
    return site_ids


def _site_seed(world: "World", location_id: str) -> object | None:
    bundle = getattr(world, "_setting_bundle", None) or getattr(world, "setting_bundle", None)
    world_definition = getattr(bundle, "world_definition", None)
    site_seed_by_id = getattr(world_definition, "site_seed_by_id", None)
    if callable(site_seed_by_id):
        return site_seed_by_id(location_id)
    return None


def _language_display_name(world: "World", language_key: str) -> str:
    if not language_key:
        return ""
    bundle = getattr(world, "_setting_bundle", None) or getattr(world, "setting_bundle", None)
    world_definition = getattr(bundle, "world_definition", None)
    for language in getattr(world_definition, "languages", ()):
        if getattr(language, "language_key", "") == language_key:
            return getattr(language, "display_name", "") or language_key
    return language_key


def _culture_display_name(world: "World", location_id: str, language_key: str) -> str:
    if not language_key:
        return ""
    bundle = getattr(world, "_setting_bundle", None) or getattr(world, "setting_bundle", None)
    world_definition = getattr(bundle, "world_definition", None)
    communities = [
        community for community in getattr(world_definition, "language_communities", ())
        if getattr(community, "language_key", "") == language_key
        and location_id in getattr(community, "regions", ())
    ]
    if communities:
        community = max(communities, key=lambda item: getattr(item, "priority", 0))
        return getattr(community, "display_name", "") or language_key
    return _language_display_name(world, language_key)


def _add_local_feature(
    features: Dict[str, Dict[str, object]],
    tag: str,
    cause: str,
    *,
    culture_key: str = "",
    culture_label: str = "",
) -> None:
    if tag not in _LOCAL_FEATURE_TAGS:
        return
    entry = features.setdefault(tag, {"causes": [], "culture_key": "", "culture_label": ""})
    causes = entry["causes"]
    if isinstance(causes, list) and cause not in causes:
        causes.append(cause)
    if culture_key and not entry["culture_key"]:
        entry["culture_key"] = culture_key
        entry["culture_label"] = culture_label


def _finalize_local_features(features: Dict[str, Dict[str, object]]) -> Dict[str, _LocalFeatureDerivation]:
    finalized: Dict[str, _LocalFeatureDerivation] = {}
    for tag, entry in features.items():
        raw_causes = entry.get("causes", ())
        causes = tuple(str(cause) for cause in raw_causes) if isinstance(raw_causes, list) else ()
        finalized[tag] = _LocalFeatureDerivation(
            tag=tag,
            causes=causes,
            culture_key=str(entry.get("culture_key", "")),
            culture_label=str(entry.get("culture_label", "")),
        )
    return finalized


def _local_feature_tags(
    world: "World",
    loc: "LocationState",
    site_type: str,
    terrain_biome: str,
    blocked_route_site_ids: Set[str],
) -> Tuple[str, ...]:
    derivations = _local_feature_derivations(world, loc, site_type, terrain_biome, blocked_route_site_ids)
    return _ordered_feature_tags(derivations)


def _local_feature_derivations(
    world: "World",
    loc: "LocationState",
    site_type: str,
    terrain_biome: str,
    blocked_route_site_ids: Set[str],
) -> Dict[str, _LocalFeatureDerivation]:
    features: Dict[str, Dict[str, object]] = {}
    values: list[str] = []
    seed = _site_seed(world, loc.id)
    site_seed_tags = [str(tag).strip() for tag in getattr(seed, "tags", ()) if str(tag).strip()]
    for tag in site_seed_tags:
        values.append(tag)
        _add_local_feature(features, tag, "authored")
    language_key = str(getattr(seed, "language_key", "") or "")
    culture_label = _culture_display_name(world, loc.id, language_key)
    for tag in _culture_building_tags(loc, site_type, site_seed_tags, terrain_biome, language_key):
        values.append(tag)
        _add_local_feature(
            features,
            tag,
            "culture",
            culture_key=language_key,
            culture_label=culture_label,
        )
    for tag in _inferred_building_tags(loc, site_type, values, terrain_biome):
        values.append(tag)
        _add_local_feature(features, tag, "inferred")
    if terrain_biome == "river":
        _add_local_feature(features, "river", "terrain")
    if loc.memorial_ids:
        _add_local_feature(features, "memorial", "memory")
    if loc.live_traces:
        _add_local_feature(features, "trace", "memory")
    if loc.id in blocked_route_site_ids:
        _add_local_feature(features, "blocked_route", "route")
    return _finalize_local_features(features)


def _ordered_feature_tags(derivations: Dict[str, _LocalFeatureDerivation]) -> Tuple[str, ...]:
    return tuple(tag for tag, _category, _priority in _LOCAL_FEATURE_DEFINITIONS if tag in derivations)


def _culture_building_tags(
    loc: "LocationState",
    site_type: str,
    tags: list[str],
    terrain_biome: str,
    language_key: str,
) -> list[str]:
    if not language_key:
        return []
    tag_text = " ".join(tags).lower()
    site_text = f"{site_type} {loc.region_type} {loc.canonical_name} {terrain_biome} {tag_text}".lower()
    culture_rules = dict(_CULTURE_BUILDING_RULES).get(language_key, ())
    return [
        tag for tag, tokens in culture_rules
        if tag in tags or _contains_any(site_text, tokens)
    ]


def _inferred_building_tags(
    loc: "LocationState",
    site_type: str,
    tags: list[str],
    terrain_biome: str,
) -> list[str]:
    tag_set = set(tags)
    site_text = f"{site_type} {loc.region_type} {loc.canonical_name}".lower()
    inferred: list[str] = []
    if terrain_biome == "river" or "river" in tag_set or any(token in site_text for token in ("brook", "marsh")):
        inferred.append("bridge")
    if "market" in tag_set:
        inferred.append("warehouse")
    inferred.extend(
        tag
        for tag, tokens in _INFERRED_BUILDING_RULES
        if tag in tag_set or _contains_any(site_text, tokens)
    )
    return list(dict.fromkeys(inferred))


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    return any(token in text for token in tokens)


def _local_feature_labels(feature_tags: Tuple[str, ...]) -> Tuple[str, ...]:
    from .i18n import tr

    return tuple(tr(f"map_feature_{tag}") for tag in feature_tags)


def _local_feature_cues(
    feature_tags: Tuple[str, ...],
    derivations: Dict[str, _LocalFeatureDerivation] | None = None,
) -> Tuple[LocalMapCue, ...]:
    from .i18n import tr

    tags = set(feature_tags)
    derivations = derivations or {}
    return tuple(
        LocalMapCue(
            tag=tag,
            category=category,
            label=tr(f"map_feature_{tag}"),
            priority=priority,
            causes=derivations.get(tag, _LocalFeatureDerivation(tag)).causes,
            culture_key=derivations.get(tag, _LocalFeatureDerivation(tag)).culture_key,
            culture_label=derivations.get(tag, _LocalFeatureDerivation(tag)).culture_label,
        )
        for tag, category, priority in _LOCAL_FEATURE_DEFINITIONS
        if tag in tags
    )


def _build_cell_info(
    world: "World",
    loc: "LocationState",
    x: int,
    y: int,
    is_highlight: bool,
    site: Optional["Site"],
    alive_counts_by_location: Dict[str, int],
    death_site_location_ids: set[str],
    world_change_counts: Dict[str, int],
    world_change_categories: Dict[str, List[str]],
    blocked_route_site_ids: Set[str],
) -> MapCellInfo:
    terrain_biome, terrain_glyph, terrain_elevation, terrain_moisture, terrain_temperature = _terrain_snapshot(
        world,
        x,
        y,
    )
    site_type = site.site_type if site else loc.region_type
    local_feature_derivations = _local_feature_derivations(
        world,
        loc,
        site_type,
        terrain_biome,
        blocked_route_site_ids,
    )
    local_feature_tags = _ordered_feature_tags(local_feature_derivations)
    local_feature_cues = _local_feature_cues(local_feature_tags, local_feature_derivations)
    cell = MapCellInfo(
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
        site_type=site_type,
        site_importance=site.importance if site else 50,
        atlas_x=site.atlas_x if site else -1,
        atlas_y=site.atlas_y if site else -1,
        controlling_faction_id=loc.controlling_faction_id or "",
        controlling_faction_name=_faction_display_name(world, loc.controlling_faction_id),
        local_feature_tags=local_feature_tags,
        local_feature_labels=_local_feature_labels(local_feature_tags),
        local_feature_cues=local_feature_cues,
    )
    cell.visual_profile = build_place_visual_profile(cell)
    return cell


def build_map_info(
    world: "World",
    highlight_location: Optional[str] = None,
) -> MapRenderInfo:
    """Extract a renderer-agnostic map snapshot from a live world."""
    from .terrain import AtlasLayout

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
    blocked_route_site_ids = _blocked_route_site_ids(world)

    for (x, y), loc in world.grid.items():
        is_highlight = (
            highlight_location is not None
            and (loc.id == highlight_location or loc.canonical_name == highlight_location)
        )
        site = site_at.get((x, y))
        info.cells[(x, y)] = _build_cell_info(
            world,
            loc,
            x,
            y,
            is_highlight,
            site,
            alive_counts_by_location,
            death_site_location_ids,
            world_change_counts,
            world_change_categories,
            blocked_route_site_ids,
        )
    return info

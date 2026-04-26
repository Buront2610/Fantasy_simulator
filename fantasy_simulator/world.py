"""
world.py - World map, LocationState dataclass, and the World class.
"""

from __future__ import annotations

import random
from collections import deque
from copy import deepcopy
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .event_models import WorldEventRecord
from .i18n import tr
from .language.engine import LanguageEngine, fallback_evolution_targets
from .language.state import LanguageEvolutionRecord, LanguageRuntimeState
from .rule_override_resolution import (
    clone_default_event_impact_rules,
    clone_default_propagation_rules,
)
from .world_language import (
    advance_world_languages_for_year,
    apply_evolution_record as apply_language_evolution_record,
    build_language_engine,
    evolution_records_for_language,
    language_status as build_language_status,
    location_endonym as resolve_location_endonym,
    refresh_world_generated_endonyms,
    resolve_language_display_name,
)
from .world_event_log import (
    append_display_event_log_entry,
    compatibility_event_log_view,
    rebuild_display_event_log,
    trim_event_log_entries,
)
from .world_bundle_transition import (
    apply_setting_bundle as apply_world_setting_bundle,
    set_setting_bundle_metadata,
    topology_signature,
)
from .world_location_references import LocationReferenceResolver
from .world_memory import (
    add_alias as add_location_alias,
    add_live_trace as add_location_live_trace,
    link_memorial_record,
    memorials_for_location,
    rebuild_location_memorial_ids,
)
from .world_load_normalizer import (
    ensure_unique_event_record_ids,
    normalize_after_load as normalize_loaded_world_state,
    rebuild_recent_event_ids,
)
from .world_reference_repair import (
    backfill_watched_actor_tags,
    normalize_world_references_after_structure_change,
    repair_world_location_references,
)
from .world_persistence import (
    hydrate_world_state,
    serialize_world_state,
)
from .world_route_graph import (
    ObservableRouteList,
    rebuild_route_index,
    replace_routes,
    routes_for_site,
)
from .world_event_state import (
    apply_event_impact_to_location,
    append_canonical_event_record,
)
from .world_event_index import EventHistoryIndex
from .world_calendar import (
    advance_calendar_position as advance_calendar_position_for_calendar,
    apply_calendar_definition_history,
    calendar_definition_by_key_ref,
    calendar_definition_for_date_ref,
    clamp_calendar_position as clamp_calendar_position_for_calendar,
    default_season,
    remaining_days_in_year as remaining_days_in_year_for_calendar,
    season_for_date as season_for_calendar_date,
    season_for_month as season_for_calendar,
    months_elapsed_between as months_elapsed_between_for_calendar,
)
from .world_state_propagation import (
    decay_toward_baseline,
    propagate_state_changes,
)
from .world_topology_state import (
    WorldTopologyState,
    build_atlas_layout_from_topology,
    build_topology_from_locations,
    overlay_serialized_route_state,
    validate_topology_integrity,
)
from .world_topology import (
    PROPAGATION_TOPOLOGY_TRAVEL,
    PROPAGATION_TOPOLOGY_GRID,
    grid_neighbor_ids,
    route_neighbor_ids,
)
from .content.setting_bundle import (
    CalendarDefinition,
    SettingBundle,
    default_aethoria_bundle,
)
from .content.world_data import (
    fallback_location_id,
    get_location_state_defaults,
)
from .terrain import (
    AtlasLayout,
    RouteEdge,
    Site,
    TerrainMap,
)

if TYPE_CHECKING:
    from .adventure import AdventureRun
    from .character import Character
    from .rumor import Rumor


def _clamp_state(value: int) -> int:
    return max(0, min(100, int(value)))


def _clone_calendar(calendar: CalendarDefinition) -> CalendarDefinition:
    return CalendarDefinition.from_dict(calendar.to_dict())


def _clone_setting_bundle(bundle: SettingBundle) -> SettingBundle:
    return SettingBundle.from_dict(bundle.to_dict())


def _string_list_payload(payload: Any, *, field_name: str) -> List[str]:
    if payload is None:
        return []
    if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
        raise ValueError(f"{field_name} must be a list of strings")
    return list(payload)


def _trace_list_payload(payload: Any, *, field_name: str) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ValueError(f"{field_name} must be a list of dicts")
    return [deepcopy(item) for item in payload]


@dataclass(slots=True)
class MemorialRecord:
    """A permanent memorial created when a character dies at a location.

    PR-F: world memory.  Memorial IDs are stored in
    ``LocationState.memorial_ids``; full records live in
    ``World.memorials`` keyed by ``memorial_id``.
    """

    memorial_id: str
    character_id: str
    character_name: str
    location_id: str
    year: int
    cause: str    # e.g. "adventure_death", "battle_fatal"
    epitaph: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memorial_id": self.memorial_id,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "location_id": self.location_id,
            "year": self.year,
            "cause": self.cause,
            "epitaph": self.epitaph,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemorialRecord":
        return cls(
            memorial_id=data["memorial_id"],
            character_id=data["character_id"],
            character_name=data["character_name"],
            location_id=data["location_id"],
            year=data["year"],
            cause=data["cause"],
            epitaph=data["epitaph"],
        )


@dataclass(slots=True)
class CalendarChangeRecord:
    """A dated calendar-definition transition for future world-timeline features."""

    year: int
    month: int
    day: int
    calendar: CalendarDefinition

    def to_dict(self) -> Dict[str, Any]:
        return {
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "calendar": self.calendar.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarChangeRecord":
        return cls(
            year=int(data.get("year", 0)),
            month=max(1, int(data.get("month", 1))),
            day=max(1, int(data.get("day", 1))),
            calendar=CalendarDefinition.from_dict(data.get("calendar", {})),
        )


PROSPERITY_LABELS = [
    (0, 20, "ruined"),
    (20, 45, "declining"),
    (45, 75, "stable"),
    (75, 101, "thriving"),
]

SAFETY_LABELS = [
    (0, 20, "lawless"),
    (20, 45, "dangerous"),
    (45, 75, "tense"),
    (75, 101, "peaceful"),
]

MOOD_LABELS = [
    (0, 20, "grieving"),
    (20, 45, "anxious"),
    (45, 75, "calm"),
    (75, 101, "festive"),
]


def _band_name(value: int, bands: List[Tuple[int, int, str]]) -> str:
    for lo, hi, name in bands:
        if lo <= value < hi:
            return name
    return bands[-1][2]


def _traffic_indicator(value: int) -> str:
    if value >= 70:
        return "+++"
    if value >= 40:
        return "++"
    if value > 0:
        return "+"
    return "-"


@dataclass(slots=True)
class LocationState:
    """A single cell on the world grid with persistent state."""

    id: str
    canonical_name: str
    description: str
    region_type: str
    x: int
    y: int
    prosperity: int
    safety: int
    mood: int
    danger: int
    traffic: int
    rumor_heat: int
    road_condition: int
    visited: bool = False
    controlling_faction_id: Optional[str] = None
    recent_event_ids: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    generated_endonym: str = ""
    memorial_ids: List[str] = field(default_factory=list)
    live_traces: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "prosperity",
            "safety",
            "mood",
            "danger",
            "traffic",
            "rumor_heat",
            "road_condition",
        ):
            setattr(self, field_name, _clamp_state(getattr(self, field_name)))

    @property
    def name(self) -> str:
        """Compatibility alias for older callers."""
        return self.canonical_name

    @property
    def icon(self) -> str:
        icons_ascii = {
            "city": "C",
            "village": "V",
            "forest": "F",
            "dungeon": "D",
            "mountain": "M",
            "plains": "P",
            "sea": "~",
        }
        return icons_ascii.get(self.region_type, "?")

    @property
    def prosperity_label(self) -> str:
        band = _band_name(self.prosperity, PROSPERITY_LABELS)
        return tr(f"location_prosperity_{band}")

    @property
    def safety_label(self) -> str:
        band = _band_name(self.safety, SAFETY_LABELS)
        return tr(f"location_safety_{band}")

    @property
    def mood_label(self) -> str:
        band = _band_name(self.mood, MOOD_LABELS)
        return tr(f"location_mood_{band}")

    @property
    def traffic_indicator(self) -> str:
        return _traffic_indicator(self.traffic)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "canonical_name": self.canonical_name,
            "name": self.canonical_name,
            "description": self.description,
            "region_type": self.region_type,
            "x": self.x,
            "y": self.y,
            "prosperity": self.prosperity,
            "safety": self.safety,
            "mood": self.mood,
            "danger": self.danger,
            "traffic": self.traffic,
            "rumor_heat": self.rumor_heat,
            "road_condition": self.road_condition,
            "visited": self.visited,
            "controlling_faction_id": self.controlling_faction_id,
            "recent_event_ids": list(self.recent_event_ids),
            "aliases": list(self.aliases),
            "generated_endonym": self.generated_endonym,
            "memorial_ids": list(self.memorial_ids),
            "live_traces": [deepcopy(trace) for trace in self.live_traces],
        }

    @classmethod
    def from_default_entry(cls, entry: Tuple[str, str, str, str, int, int]) -> "LocationState":
        loc_id, canonical_name, description, region_type, x, y = entry
        defaults = get_location_state_defaults(loc_id, region_type)
        return cls(
            id=loc_id,
            canonical_name=canonical_name,
            description=description,
            region_type=region_type,
            x=x,
            y=y,
            **defaults,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocationState":
        loc_id = data.get("id")
        if not loc_id:
            name = data.get("canonical_name") or data.get("name", "")
            loc_id = fallback_location_id(name)
        canonical_name = data.get("canonical_name") or data.get("name", "")
        region_type = data["region_type"]
        defaults = get_location_state_defaults(loc_id, region_type)
        return cls(
            id=loc_id,
            canonical_name=canonical_name,
            description=data["description"],
            region_type=region_type,
            x=data["x"],
            y=data["y"],
            prosperity=data.get("prosperity", defaults["prosperity"]),
            safety=data.get("safety", defaults["safety"]),
            mood=data.get("mood", defaults["mood"]),
            danger=data.get("danger", defaults["danger"]),
            traffic=data.get("traffic", defaults["traffic"]),
            rumor_heat=data.get("rumor_heat", defaults["rumor_heat"]),
            road_condition=data.get("road_condition", defaults["road_condition"]),
            visited=data.get("visited", False),
            controlling_faction_id=data.get("controlling_faction_id"),
            recent_event_ids=_string_list_payload(data.get("recent_event_ids", []), field_name="recent_event_ids"),
            aliases=_string_list_payload(data.get("aliases", []), field_name="aliases"),
            generated_endonym=str(data.get("generated_endonym", "")),
            memorial_ids=_string_list_payload(data.get("memorial_ids", []), field_name="memorial_ids"),
            live_traces=_trace_list_payload(data.get("live_traces", []), field_name="live_traces"),
        )


class World:
    """Represents the entire game world."""

    WATCHED_ACTOR_TAG_PREFIX = "watched_actor:"
    WATCHED_ACTOR_INFERRED_TAG = "watched_actor_inferred"
    LANGUAGE_SHIFT_CANDIDATES: Dict[str, List[str]] = fallback_evolution_targets()

    def __init__(
        self,
        name: str = "Aethoria",
        lore: str | None = None,
        width: int = 5,
        height: int = 5,
        year: int = 1000,
        *,
        _skip_defaults: bool = False,
    ) -> None:
        self._setting_bundle: SettingBundle = default_aethoria_bundle(
            display_name=name,
            lore_text=lore,
        )
        self._location_reference_resolver = LocationReferenceResolver.from_site_seeds(
            self._setting_bundle.world_definition.site_seeds
        )
        self._language_engine: LanguageEngine | None = None
        self.calendar_baseline: CalendarDefinition = _clone_calendar(
            self._setting_bundle.world_definition.calendar
        )
        self.width: int = width
        self.height: int = height
        self.year: int = year
        self.grid: Dict[Tuple[int, int], LocationState] = {}
        self.characters: List[Character] = []
        self._char_index: Dict[str, Character] = {}
        self._adventure_index: Dict[str, AdventureRun] = {}
        self._location_name_index: Dict[str, LocationState] = {}
        self._location_id_index: Dict[str, LocationState] = {}
        # Event storage contract:
        # - event_records is the canonical structured history for all new reads.
        # - _display_event_log holds only display-only legacy lines.
        # - event_log projects from canonical history when records exist.
        self._display_event_log: List[str] = []
        self.event_records: List[WorldEventRecord] = []
        self._event_index = EventHistoryIndex()
        self.event_impact_rules: Dict[str, Dict[str, int]] = clone_default_event_impact_rules()
        self.propagation_rules: Dict[str, Dict[str, Any]] = clone_default_propagation_rules()
        self.rumors: List[Rumor] = []
        self.rumor_archive: List[Rumor] = []
        self.active_adventures: List[AdventureRun] = []
        self.completed_adventures: List[AdventureRun] = []
        # PR-F: keyed by memorial_id
        self.memorials: Dict[str, MemorialRecord] = {}
        # Future-facing trace of in-world calendar transitions.
        self.calendar_history: List[CalendarChangeRecord] = []
        self.language_origin_year: int = year
        self.language_evolution_history: List[LanguageEvolutionRecord] = []
        self._language_runtime_states: Dict[str, LanguageRuntimeState] = {}
        # PR-G: terrain / site / route layers
        self.terrain_map: Optional[TerrainMap] = None
        self.sites: List[Site] = []
        self._routes: ObservableRouteList = ObservableRouteList(on_change=self._mark_routes_dirty)
        self._site_index: Dict[str, Site] = {}
        self._routes_by_site: Dict[str, List[RouteEdge]] = {}
        self._routes_dirty: bool = True
        self._route_graph_explicit: bool = False
        # PR-G2: persistent macro geography layer
        self.atlas_layout: Optional[AtlasLayout] = None
        if not _skip_defaults:
            self._build_default_map()

    @property
    def name(self) -> str:
        """Compatibility alias for the bundle-backed world display name."""
        return self._setting_bundle.world_definition.display_name

    @name.setter
    def name(self, value: str) -> None:
        self._setting_bundle.world_definition.display_name = value

    @property
    def event_log(self) -> List[str]:
        """Compatibility event log view.

        Once canonical ``event_records`` exist, the compatibility log is
        projected on demand so we do not retain a second long-lived copy of the
        same history in memory. The returned value is a read-only view so direct
        list mutation cannot silently diverge from canonical history.
        """
        return compatibility_event_log_view(
            self._display_event_log,
            self.event_records,
            max_event_log=self.MAX_EVENT_LOG,
            translate=tr,
        )

    @event_log.setter
    def event_log(self, value: List[str]) -> None:
        self._display_event_log = trim_event_log_entries(value, max_event_log=self.MAX_EVENT_LOG)

    @property
    def routes(self) -> ObservableRouteList:
        return self._routes

    @routes.setter
    def routes(self, value: List[RouteEdge]) -> None:
        current_routes = getattr(self, "_routes", [])
        self._routes = replace_routes(
            current_routes,
            value,
            on_change=self._mark_routes_dirty,
        )
        self._routes_dirty = True

    @property
    def lore(self) -> str:
        """Compatibility alias for the bundle-backed world lore."""
        return self._setting_bundle.world_definition.lore_text

    @lore.setter
    def lore(self, value: str) -> None:
        self._setting_bundle.world_definition.lore_text = value

    @property
    def setting_bundle(self) -> SettingBundle:
        """Return a defensive copy; use apply_setting_bundle() to replace it."""
        return _clone_setting_bundle(self._setting_bundle)

    @setting_bundle.setter
    def setting_bundle(self, value: SettingBundle) -> None:
        self.apply_setting_bundle(value)

    def _set_setting_bundle_metadata(self, bundle: SettingBundle) -> None:
        set_setting_bundle_metadata(
            self,
            bundle,
            clone_bundle=_clone_setting_bundle,
            clone_calendar=_clone_calendar,
        )

    def apply_setting_bundle(self, bundle: SettingBundle) -> None:
        apply_world_setting_bundle(
            self,
            bundle,
            clone_bundle=_clone_setting_bundle,
            clone_calendar=_clone_calendar,
        )

    @staticmethod
    def _topology_signature(bundle: SettingBundle) -> Tuple[Tuple[Any, ...], Tuple[Any, ...]]:
        return topology_signature(bundle)

    def _refresh_locations_from_site_seeds(self) -> None:
        """Refresh static location metadata when bundle lore changes but topology does not."""
        for seed in self._setting_bundle.world_definition.site_seeds:
            existing = self._location_id_index.get(seed.location_id)
            if existing is None:
                continue
            replacement = self._location_state_from_site_seed(seed)
            self._copy_location_runtime_state(existing, replacement)
            self._register_location(replacement)

    @property
    def language_engine(self) -> LanguageEngine:
        if self._language_engine is None:
            self._language_engine = build_language_engine(
                self._setting_bundle.world_definition,
                self._language_runtime_states,
            )
        return self._language_engine

    def naming_rules_for_identity(
        self,
        *,
        race: str | None = None,
        tribe: str | None = None,
        region: str | None = None,
    ):
        return self.language_engine.naming_rules_for_identity(race=race, tribe=tribe, region=region)

    def resolve_language_for_identity(
        self,
        *,
        race: str | None = None,
        tribe: str | None = None,
        region: str | None = None,
    ) -> str | None:
        return resolve_language_display_name(
            self.language_engine,
            race=race,
            tribe=tribe,
            region=region,
        )

    def describe_language_lineage(self, language_key: str) -> List[str]:
        return self.language_engine.describe_language_lineage(language_key)

    def location_endonym(self, location_id: str) -> str | None:
        return resolve_location_endonym(
            self._setting_bundle.world_definition,
            self.language_engine,
            location_id,
        )

    def language_status(self) -> List[Dict[str, Any]]:
        return build_language_status(
            self._setting_bundle.world_definition,
            self.language_engine,
            self.language_evolution_history,
        )

    def language_evolution_records(self, language_key: str) -> List[LanguageEvolutionRecord]:
        return evolution_records_for_language(self.language_evolution_history, language_key)

    def _register_location(self, loc: LocationState) -> None:
        existing_at_coord = self.grid.get((loc.x, loc.y))
        if existing_at_coord is not None and existing_at_coord is not loc:
            self._location_name_index.pop(existing_at_coord.canonical_name, None)
            self._location_id_index.pop(existing_at_coord.id, None)

        existing_by_id = self._location_id_index.get(loc.id)
        if existing_by_id is not None and existing_by_id is not loc:
            self.grid.pop((existing_by_id.x, existing_by_id.y), None)
            self._location_name_index.pop(existing_by_id.canonical_name, None)

        self.grid[(loc.x, loc.y)] = loc
        self._location_name_index[loc.canonical_name] = loc
        self._location_id_index[loc.id] = loc

    def _clear_world_structure(self) -> None:
        """Reset world structures derived from the active location grid."""
        self.grid.clear()
        self._location_id_index.clear()
        self._location_name_index.clear()
        self.terrain_map = None
        self.sites = []
        self.routes = []
        self._routes_dirty = True
        self._route_graph_explicit = False
        self._site_index = {}
        self._routes_by_site = {}
        self.atlas_layout = None

    def _copy_location_runtime_state(self, source: LocationState, target: LocationState) -> None:
        """Preserve mutable location state across structural rebuilds."""
        structural_aliases = list(target.aliases)
        structural_endonym = target.generated_endonym
        target.prosperity = source.prosperity
        target.safety = source.safety
        target.mood = source.mood
        target.danger = source.danger
        target.traffic = source.traffic
        target.rumor_heat = source.rumor_heat
        target.road_condition = source.road_condition
        target.visited = source.visited
        target.controlling_faction_id = source.controlling_faction_id
        target.recent_event_ids = list(source.recent_event_ids)
        target.aliases = list(dict.fromkeys(structural_aliases + list(source.aliases)))
        target.generated_endonym = structural_endonym
        target.memorial_ids = list(source.memorial_ids)
        target.live_traces = [dict(trace) for trace in source.live_traces]

    def _refresh_generated_endonyms(
        self,
        stale_endonyms_by_location_id: Dict[str, str] | None = None,
    ) -> None:
        refresh_world_generated_endonyms(
            self,
            stale_endonyms_by_location_id=stale_endonyms_by_location_id,
        )

    def _derive_language_evolution_record(self, language_key: str, year: int) -> LanguageEvolutionRecord | None:
        return self.language_engine.derive_evolution_record(
            language_key,
            year=year,
            evolution_history=self.language_evolution_history,
        )

    def _apply_language_evolution_record(self, record: LanguageEvolutionRecord) -> bool:
        updated_runtime_states = apply_language_evolution_record(
            self.language_engine,
            self._language_runtime_states,
            record,
        )
        if updated_runtime_states is None:
            return False
        self._language_runtime_states = updated_runtime_states
        return True

    def _maybe_evolve_languages_for_year(self, year: int) -> None:
        advance_world_languages_for_year(self, year)

    def _build_default_map(self, previous_locations: Optional[List[LocationState]] = None) -> None:
        """Rebuild the world from the active setting bundle's site seeds.

        Only locations whose ``(x, y)`` fall within ``self.width x
        self.height`` are registered.  This means ``World(width=3,
        height=3)`` will contain only the locations that fit.
        """
        if previous_locations is None:
            previous_locations = list(self.grid.values())
        preserved_by_id: Dict[str, LocationState] = {}
        for location in previous_locations:
            normalized_id = self.normalize_location_id(
                location.id,
                location_name=location.canonical_name,
            )
            if normalized_id is not None and normalized_id not in preserved_by_id:
                preserved_by_id[normalized_id] = location
        self._clear_world_structure()
        for seed in self._setting_bundle.world_definition.site_seeds:
            x, y = seed.x, seed.y
            if 0 <= x < self.width and 0 <= y < self.height:
                location = self._location_state_from_site_seed(seed)
                previous = preserved_by_id.get(location.id)
                if previous is not None:
                    self._copy_location_runtime_state(previous, location)
                self._register_location(location)
        self._build_terrain_from_grid(explicit_route_graph=True)

    def default_location_entries(self) -> List[Tuple[str, str, str, str, int, int]]:
        """Return in-bounds bundle-backed site seeds in the legacy tuple format."""
        return [
            seed.as_world_data_entry()
            for seed in self._setting_bundle.world_definition.site_seeds
            if 0 <= seed.x < self.width and 0 <= seed.y < self.height
        ]

    def _overlay_location_runtime_state_from_dict(self, data: Dict[str, Any]) -> None:
        """Overlay serialized runtime state onto an existing bundle-backed location."""
        restored = self._location_state_from_dict(data)
        current = self._location_id_index.get(restored.id)
        if current is None:
            return
        self._copy_location_runtime_state(restored, current)

    def _register_serialized_grid_locations(self, serialized_grid: List[Dict[str, Any]]) -> None:
        """Restore serialized locations as authoritative grid structure."""
        for loc_data in serialized_grid:
            self._register_location(self._location_state_from_dict(loc_data))

    def _overlay_serialized_grid_runtime_state(self, serialized_grid: List[Dict[str, Any]]) -> None:
        """Overlay serialized runtime state onto an already-built bundle-backed grid."""
        for loc_data in serialized_grid:
            self._overlay_location_runtime_state_from_dict(loc_data)

    def _serialized_grid_is_compatible_with_active_bundle(self, grid_data: List[Dict[str, Any]]) -> bool:
        """Return whether serialized locations can be mapped onto the active bundle."""
        if not grid_data:
            return True
        bundle_location_ids = {
            seed.location_id
            for seed in self._setting_bundle.world_definition.site_seeds
        }
        for loc_data in grid_data:
            canonical_name = loc_data.get("canonical_name") or loc_data.get("name", "")
            normalized_id = self.normalize_location_id(
                loc_data.get("id"),
                location_name=canonical_name,
            )
            if normalized_id not in bundle_location_ids:
                return False
        return True

    def _site_seed_tags(self, location_id: str) -> List[str]:
        """Return semantic tags for a location from the active setting bundle."""
        for seed in self._setting_bundle.world_definition.site_seeds:
            if seed.location_id == location_id:
                return list(seed.tags)
        return []

    def _bundle_location_id_for_name(self, name: str) -> str | None:
        """Resolve a location name through the active setting bundle."""
        return self._location_reference_resolver.bundle_location_id_for_name(name)

    def resolve_location_id_from_name(self, name: str) -> str:
        """Resolve a location name through the active bundle with slug fallback."""
        return self._location_reference_resolver.resolve_location_id_from_name(
            name,
            fallback_resolver=fallback_location_id,
        )

    def _legacy_location_id_aliases(self) -> Dict[str, str]:
        """Return legacy fallback-slug IDs that should map to canonical bundle IDs."""
        return self._location_reference_resolver.legacy_location_id_aliases()

    def normalize_location_id(
        self,
        location_id: Optional[str],
        *,
        location_name: str | None = None,
    ) -> Optional[str]:
        """Normalize persisted location IDs against the active bundle."""
        return self._location_reference_resolver.normalize_location_id(
            location_id,
            location_name=location_name,
            fallback_resolver=fallback_location_id,
        )

    def _repair_location_reference(
        self,
        location_id: Optional[str],
        *,
        location_name: str | None = None,
        required: bool = False,
        fallback_location_id: str | None = None,
    ) -> Optional[str]:
        """Resolve a location reference to a valid current-world location."""
        resolved_fallback = fallback_location_id
        if required and resolved_fallback is None and self._location_id_index:
            resolved_fallback = self._default_resident_location_id()
        return self._location_reference_resolver.repair_location_reference(
            location_id,
            known_location_ids=self._location_id_index,
            location_name=location_name,
            required=required,
            fallback_location_id=resolved_fallback,
            fallback_resolver=fallback_location_id,
        )

    def _repair_location_references(self) -> None:
        """Repair persisted location references against the active world structure."""
        fallback_location_id = None
        if self._location_id_index:
            fallback_location_id = self._default_resident_location_id()
        repair_world_location_references(
            characters=self.characters,
            event_records=self.event_records,
            rumors=self.rumors,
            rumor_archive=self.rumor_archive,
            active_adventures=self.active_adventures,
            completed_adventures=self.completed_adventures,
            memorials=self.memorials,
            repair_location_reference=self._repair_location_reference,
            fallback_location_id=fallback_location_id,
        )

    def _rebuild_location_memorial_ids(self) -> None:
        """Rebuild per-location memorial indices from canonical memorial records."""
        rebuild_location_memorial_ids(
            locations=self.grid.values(),
            location_index=self._location_id_index,
            memorials=self.memorials.values(),
        )

    def _normalize_references_after_bundle_change(self) -> None:
        """Repair references after replacing the active setting bundle."""
        normalize_world_references_after_structure_change(
            repair_location_references=self._repair_location_references,
            rebuild_location_memorial_ids=self._rebuild_location_memorial_ids,
            rebuild_char_index=self.rebuild_char_index,
            ensure_valid_character_locations=self.ensure_valid_character_locations,
            rebuild_adventure_index=self.rebuild_adventure_index,
            rebuild_recent_event_ids=self.rebuild_recent_event_ids,
            rebuild_compatibility_event_log=self.rebuild_compatibility_event_log,
            has_event_records=bool(self.event_records),
        )

    def location_state_defaults(self, location_id: str, region_type: str) -> Dict[str, int]:
        """Return location defaults using the active bundle's site tags."""
        return get_location_state_defaults(
            location_id,
            region_type,
            site_tags=self._site_seed_tags(location_id),
        )

    def _location_state_from_site_seed(self, seed: Any) -> LocationState:
        """Build a LocationState from a bundle site seed."""
        defaults = self.location_state_defaults(seed.location_id, seed.region_type)
        location = LocationState(
            id=seed.location_id,
            canonical_name=seed.name,
            description=seed.description,
            region_type=seed.region_type,
            x=seed.x,
            y=seed.y,
            **defaults,
        )
        endonym = self.location_endonym(seed.location_id)
        if endonym and endonym != location.canonical_name:
            location.generated_endonym = endonym
        return location

    def _build_terrain_from_grid(self, *, explicit_route_graph: Optional[bool] = None) -> None:
        """Generate terrain, sites, and routes from the current grid.

        Derives terrain biome from each ``LocationState.region_type``
        and creates provisional routes between adjacent sites only when no
        explicit route graph is defined for the current structure.
        """
        use_explicit_route_graph = (
            self._grid_matches_bundle_seeds()
            if explicit_route_graph is None
            else explicit_route_graph
        )
        location_ids = set(self._location_id_index)
        topology_state = build_topology_from_locations(
            width=self.width,
            height=self.height,
            locations=self.grid.values(),
            route_specs=(
                [
                    seed.to_dict()
                    for seed in self._setting_bundle.world_definition.route_seeds
                    if seed.from_site_id in location_ids and seed.to_site_id in location_ids
                ]
                if use_explicit_route_graph
                else None
            ),
            explicit_route_graph=use_explicit_route_graph,
        )
        self._apply_topology_state(topology_state)

    def _apply_topology_state(self, topology_state: WorldTopologyState) -> None:
        """Apply a reconstructed topology snapshot to the live world state."""
        self.terrain_map = topology_state.terrain_map
        self.sites = topology_state.sites
        self.routes = topology_state.routes
        self._rebuild_site_index()
        self._rebuild_route_index()
        self._route_graph_explicit = topology_state.route_graph_explicit
        self.atlas_layout = topology_state.atlas_layout

    def _build_atlas_layout_from_current_state(self) -> AtlasLayout:
        """Generate the persistent atlas layout from current terrain/site data."""
        return build_atlas_layout_from_topology(
            width=self.width,
            height=self.height,
            terrain_map=self.terrain_map,
            sites=self.sites,
            routes=self.routes,
        )

    def _rebuild_site_index(self) -> None:
        """Rebuild the site lookup index keyed by location_id."""
        self._site_index = {s.location_id: s for s in self.sites}

    def _mark_routes_dirty(self) -> None:
        """Mark cached route adjacency as stale after route mutations."""
        self._routes_dirty = True

    def _rebuild_route_index(self) -> None:
        """Rebuild route adjacency lists keyed by endpoint location id."""
        self._routes_by_site = rebuild_route_index(
            sites=self.sites,
            routes=self.routes,
            on_change=self._mark_routes_dirty,
        )
        self._routes_dirty = False

    def _ensure_route_index_current(self) -> None:
        """Keep the cached route adjacency in sync with direct route reassignment."""
        if self._routes_dirty:
            self._rebuild_route_index()

    def _validate_topology_integrity(self) -> None:
        """Validate that restored topology is coherent with the active grid."""
        validate_topology_integrity(
            sites=self.sites,
            routes=self.routes,
            location_index=self._location_id_index,
        )

    def get_site_by_id(self, location_id: str) -> Optional[Site]:
        """Return the Site record for a location, or None."""
        return self._site_index.get(location_id)

    def get_routes_for_site(self, location_id: str) -> List[RouteEdge]:
        """Return all routes connected to a site."""
        self._ensure_route_index_current()
        return routes_for_site(self._routes_by_site, location_id)

    def get_connected_site_ids(self, location_id: str) -> List[str]:
        """Return location_ids of sites reachable via routes from a site."""
        return sorted(
            route_neighbor_ids(location_id, routes=self.get_routes_for_site(location_id)),
        )

    def get_grid_neighboring_locations(self, location_id: str) -> List[LocationState]:
        """Return adjacency by physical map grid, regardless of route state."""
        neighbor_ids = grid_neighbor_ids(
            location_id,
            location_index=self._location_id_index,
            grid=self.grid,
        )
        return [
            self._location_id_index[neighbor_id]
            for neighbor_id in neighbor_ids
            if neighbor_id in self._location_id_index
        ]

    def get_travel_neighboring_locations(self, location_id: str) -> List[LocationState]:
        """Return neighbors reachable for travel using the travel topology contract."""
        if self.routes:
            neighbor_ids = self.get_connected_site_ids(location_id)
        elif self._route_graph_explicit:
            neighbor_ids = []
        else:
            neighbor_ids = grid_neighbor_ids(location_id, location_index=self._location_id_index, grid=self.grid)
        return [
            self._location_id_index[neighbor_id]
            for neighbor_id in neighbor_ids
            if neighbor_id in self._location_id_index
        ]

    def get_propagation_neighboring_locations(
        self,
        location_id: str,
        *,
        mode: str | None = None,
        include_blocked_routes: bool | None = None,
    ) -> List[LocationState]:
        """Return neighbors used for state propagation.

        The propagation topology is intentionally explicit so future worldgen
        and blocked-route features can vary travel and propagation semantics
        independently.
        """
        topology_rules = self.propagation_rules.get("topology", {})
        topology_mode = mode or str(topology_rules.get("mode", PROPAGATION_TOPOLOGY_TRAVEL))
        effective_include_blocked_routes = (
            bool(topology_rules.get("include_blocked_routes", False))
            if include_blocked_routes is None
            else include_blocked_routes
        )
        if topology_mode == PROPAGATION_TOPOLOGY_TRAVEL:
            if self.routes:
                neighbor_ids = sorted(
                    route_neighbor_ids(
                        location_id,
                        routes=self.get_routes_for_site(location_id),
                        include_blocked=effective_include_blocked_routes,
                    )
                )
            elif self._route_graph_explicit:
                neighbor_ids = []
            else:
                neighbor_ids = grid_neighbor_ids(location_id, location_index=self._location_id_index, grid=self.grid)
        elif topology_mode == PROPAGATION_TOPOLOGY_GRID:
            neighbor_ids = grid_neighbor_ids(location_id, location_index=self._location_id_index, grid=self.grid)
        else:
            raise ValueError(f"Unsupported propagation topology mode: {topology_mode}")
        return [
            self._location_id_index[neighbor_id]
            for neighbor_id in neighbor_ids
            if neighbor_id in self._location_id_index
        ]

    def reachable_location_ids(self, location_id: str) -> List[str]:
        """Return all reachable location_ids from ``location_id``."""
        if location_id not in self._location_id_index:
            return []

        visited = {location_id}
        queue = deque([location_id])
        reachable: List[str] = []

        while queue:
            current = queue.popleft()
            neighbor_ids = [
                loc.id for loc in self.get_travel_neighboring_locations(current)
            ]
            for neighbor_id in neighbor_ids:
                if neighbor_id in visited or neighbor_id not in self._location_id_index:
                    continue
                visited.add(neighbor_id)
                reachable.append(neighbor_id)
                queue.append(neighbor_id)

        return reachable

    def _location_ids_for_site_tag(self, tag: str) -> List[str]:
        """Return in-bounds location_ids for bundle site seeds carrying *tag*."""
        return [
            seed.location_id
            for seed in self._setting_bundle.world_definition.site_seeds
            if tag in seed.tags and seed.location_id in self._location_id_index
        ]

    def _default_resident_location_id(self) -> str:
        tagged_defaults = (
            self._location_ids_for_site_tag("default_resident")
            or self._location_ids_for_site_tag("capital")
        )
        if tagged_defaults:
            return sorted(tagged_defaults)[0]
        non_dungeons = sorted(
            loc.id for loc in self.grid.values() if loc.region_type != "dungeon"
        )
        if non_dungeons:
            return non_dungeons[0]
        all_locations = sorted(self._location_id_index)
        if all_locations:
            return all_locations[0]
        raise ValueError("World has no locations.")

    def mark_location_visited(self, location_id: str) -> None:
        """Mark a location as visited when it is meaningfully occupied or reached."""
        location = self._location_id_index.get(location_id)
        if location is not None:
            location.visited = True

    def ensure_valid_character_locations(self) -> None:
        """Repair invalid location references after loading legacy data."""
        if not self.characters:
            return
        if not self._location_id_index:
            for character in self.characters:
                character.location_id = ""
            return
        fallback = self._default_resident_location_id()
        for character in self.characters:
            if character.location_id not in self._location_id_index:
                character.location_id = fallback
            self.mark_location_visited(character.location_id)

    def add_character(self, character: Character, rng: Any = random) -> None:
        if character.location_id not in self._location_id_index:
            if not character.location_id:
                character.location_id = self._default_resident_location_id()
            else:
                options = [loc.id for loc in self.grid.values() if loc.region_type != "dungeon"]
                if options:
                    character.location_id = rng.choice(options)
                else:
                    character.location_id = self._default_resident_location_id()
        if character.char_id in self._char_index:
            raise ValueError(
                f"Duplicate character ID: {character.char_id!r} "
                f"(existing: {self._char_index[character.char_id].name!r}, "
                f"new: {character.name!r})"
            )
        self.characters.append(character)
        self._char_index[character.char_id] = character
        self.mark_location_visited(character.location_id)

    def rebuild_char_index(self) -> None:
        """Rebuild the character ID index after external mutations."""
        index: Dict[str, Character] = {}
        for c in self.characters:
            if c.char_id in index:
                raise ValueError(
                    f"Duplicate character ID during rebuild: {c.char_id!r} "
                    f"(existing: {index[c.char_id].name!r}, "
                    f"duplicate: {c.name!r})"
                )
            index[c.char_id] = c
        self._char_index = index

    def remove_character(self, char_id: str) -> None:
        self.characters = [c for c in self.characters if c.char_id != char_id]
        self._char_index.pop(char_id, None)

    def get_character_by_id(self, char_id: str) -> Optional[Character]:
        return self._char_index.get(char_id)

    def get_adventure_by_id(self, adventure_id: str) -> Optional[AdventureRun]:
        return self._adventure_index.get(adventure_id)

    def rebuild_adventure_index(self) -> None:
        """Rebuild the adventure ID index after loading or external mutations."""
        index: Dict[str, AdventureRun] = {}
        for run in self.active_adventures + self.completed_adventures:
            if run.adventure_id in index:
                raise ValueError(f"Duplicate adventure ID during rebuild: {run.adventure_id!r}")
            index[run.adventure_id] = run
        self._adventure_index = index

    def rebuild_recent_event_ids(self) -> None:
        """Rebuild derived per-location recent_event_ids from structured event records."""
        rebuild_recent_event_ids(
            locations=self.grid.values(),
            location_index=self._location_id_index,
            event_records=self.event_records,
        )

    def _ensure_unique_event_record_ids(self) -> None:
        """Fail fast when canonical history contains duplicate record IDs."""
        ensure_unique_event_record_ids(self.event_records)

    def normalize_after_load(self) -> None:
        """Rebuild derived indexes and repair invariants after deserialization."""
        normalize_loaded_world_state(
            event_records=self.event_records,
            repair_location_references=self._repair_location_references,
            rebuild_char_index=self.rebuild_char_index,
            backfill_watched_actor_tags=self._backfill_watched_actor_tags_after_load,
            ensure_valid_character_locations=self.ensure_valid_character_locations,
            rebuild_adventure_index=self.rebuild_adventure_index,
            rebuild_recent_event_ids_fn=self.rebuild_recent_event_ids,
            rebuild_location_memorial_ids_fn=self._rebuild_location_memorial_ids,
            rebuild_compatibility_event_log=self.rebuild_compatibility_event_log,
        )

    def _backfill_watched_actor_tags_after_load(self) -> None:
        """Freeze watched-actor report context for older untagged canonical records.

        Older schema-v8 saves may already store canonical event records but
        predate watched-actor tags. When such a snapshot is loaded, use the
        current watched roster as the best available approximation and stamp
        those tags onto untagged records once so future flag changes do not
        rewrite historical reports again.
        """
        watched_actor_ids = {
            character.char_id
            for character in self.characters
            if character.favorite or character.spotlighted or character.playable
        }
        backfill_watched_actor_tags(
            event_records=self.event_records,
            watched_actor_ids=watched_actor_ids,
            watched_actor_tag_prefix=self.WATCHED_ACTOR_TAG_PREFIX,
            inferred_tag=self.WATCHED_ACTOR_INFERRED_TAG,
        )

    def add_adventure(self, run: AdventureRun) -> None:
        self.active_adventures.append(run)
        self._adventure_index[run.adventure_id] = run

    def complete_adventure(self, adventure_id: str) -> None:
        remaining: List[AdventureRun] = []
        for run in self.active_adventures:
            if run.adventure_id == adventure_id:
                self.completed_adventures.append(run)
            else:
                remaining.append(run)
        self.active_adventures = remaining

    # ------------------------------------------------------------------
    # PR-F: World memory helpers
    # ------------------------------------------------------------------

    #: Maximum live traces kept per location (rolling window)
    MAX_LIVE_TRACES = 10
    #: Maximum aliases allowed per location
    MAX_ALIASES = 3

    def add_live_trace(
        self,
        location_id: str,
        year: int,
        char_name: str,
        text: str,
    ) -> None:
        """Record a visitor trace at a location (design §E-2).

        Traces are ephemeral footprints capped at ``MAX_LIVE_TRACES``
        per location.  Oldest entries are dropped when the cap is reached.
        """
        add_location_live_trace(
            location_index=self._location_id_index,
            location_id=location_id,
            year=year,
            char_name=char_name,
            text=text,
            max_live_traces=self.MAX_LIVE_TRACES,
        )

    def add_memorial(
        self,
        memorial_id: str,
        character_id: str,
        character_name: str,
        location_id: str,
        year: int,
        cause: str,
        epitaph: str,
    ) -> None:
        """Create a permanent memorial at a location (design §E-2).

        The memorial is stored in ``self.memorials`` and its ID is appended
        to ``LocationState.memorial_ids`` for quick lookup.
        """
        record = MemorialRecord(
            memorial_id=memorial_id,
            character_id=character_id,
            character_name=character_name,
            location_id=location_id,
            year=year,
            cause=cause,
            epitaph=epitaph,
        )
        link_memorial_record(
            memorials=self.memorials,
            location_index=self._location_id_index,
            record=record,
        )

    def add_alias(self, location_id: str, alias: str) -> None:
        """Append an alias to a location if not already present (design §E-2).

        Capped at ``MAX_ALIASES`` per location; duplicate strings are
        silently ignored.
        """
        add_location_alias(
            location_index=self._location_id_index,
            location_id=location_id,
            alias=alias,
            max_aliases=self.MAX_ALIASES,
        )

    def get_memorials_for_location(self, location_id: str) -> List[MemorialRecord]:
        """Return all ``MemorialRecord`` objects associated with a location."""
        return list(
            memorials_for_location(
                location_index=self._location_id_index,
                memorials=self.memorials,
                location_id=location_id,
            )
        )

    @property
    def location_names(self) -> List[str]:
        return sorted(loc.canonical_name for loc in self.grid.values())

    @property
    def location_ids(self) -> List[str]:
        return sorted(loc.id for loc in self.grid.values())

    def get_location_by_name(self, name: str) -> Optional[LocationState]:
        return self._location_name_index.get(name)

    def get_location_by_id(self, location_id: str) -> Optional[LocationState]:
        return self._location_id_index.get(location_id)

    def location_name(self, location_id: str) -> str:
        loc = self._location_id_index.get(location_id)
        if loc is not None:
            return loc.canonical_name
        return tr("unknown_location_with_id", location_id=location_id)

    def get_characters_at_location(self, location_id: str) -> List[Character]:
        return [c for c in self.characters if c.location_id == location_id and c.alive]

    def get_neighboring_locations(self, location_id: str) -> List[LocationState]:
        """Compatibility alias for travel adjacency."""
        return self.get_travel_neighboring_locations(location_id)

    def months_elapsed_between(
        self,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        *,
        start_day: int = 1,
        end_day: int = 1,
        start_calendar_key: str = "",
    ) -> int:
        """Return completed month boundaries between two in-world dates."""
        return months_elapsed_between_for_calendar(
            calendar_definition_for_date_ref_fn=self._calendar_definition_for_date_ref,
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
            start_day=start_day,
            end_day=end_day,
            start_calendar_key=start_calendar_key,
        )

    def random_location(self, exclude_dungeon: bool = False, rng: Any = random) -> LocationState:
        options = list(self.grid.values())
        if exclude_dungeon:
            options = [loc for loc in options if loc.region_type != "dungeon"]
        if not options:
            raise ValueError("World has no locations.")
        return rng.choice(options)

    def _base_calendar_ref(self) -> CalendarDefinition:
        return self._setting_bundle.world_definition.calendar

    @property
    def calendar_definition(self):
        return _clone_calendar(self._base_calendar_ref())

    @property
    def months_per_year(self) -> int:
        return self._base_calendar_ref().months_per_year

    @property
    def days_per_year(self) -> int:
        return self._base_calendar_ref().days_per_year

    def days_in_month(self, month: int) -> int:
        return self._base_calendar_ref().days_in_month(month)

    def month_display_name(self, month: int) -> str:
        return self._base_calendar_ref().month_display_name(month)

    def _calendar_definition_by_key_ref(self, calendar_key: str) -> CalendarDefinition:
        return calendar_definition_by_key_ref(
            base_calendar=self._base_calendar_ref(),
            calendar_baseline=self.calendar_baseline,
            calendar_history=self.calendar_history,
            calendar_key=calendar_key,
        )

    def calendar_definition_by_key(self, calendar_key: str) -> CalendarDefinition:
        return _clone_calendar(self._calendar_definition_by_key_ref(calendar_key))

    def _calendar_definition_for_date_ref(
        self,
        year: int,
        month: int = 1,
        day: int = 1,
        *,
        calendar_key: str = "",
    ) -> CalendarDefinition:
        return calendar_definition_for_date_ref(
            base_calendar=self._base_calendar_ref(),
            calendar_baseline=self.calendar_baseline,
            calendar_history=self.calendar_history,
            year=year,
            month=month,
            day=day,
            calendar_key=calendar_key,
        )

    def calendar_definition_for_date(
        self,
        year: int,
        month: int = 1,
        day: int = 1,
        *,
        calendar_key: str = "",
    ) -> CalendarDefinition:
        return _clone_calendar(
            self._calendar_definition_for_date_ref(
                year,
                month,
                day,
                calendar_key=calendar_key,
            )
        )

    def months_per_year_for_date(
        self, year: int, month: int = 1, day: int = 1, *, calendar_key: str = ""
    ) -> int:
        return self._calendar_definition_for_date_ref(
            year, month, day, calendar_key=calendar_key
        ).months_per_year

    def month_display_name_for_date(
        self, year: int, month: int, day: int = 1, *, calendar_key: str = ""
    ) -> str:
        calendar = self._calendar_definition_for_date_ref(year, month, day, calendar_key=calendar_key)
        return calendar.month_display_name(month)

    @staticmethod
    def get_season(month: int) -> str:
        """Return the default season mapping used by the built-in calendar."""
        return default_season(month)

    def season_for_month(self, month: int) -> str:
        """Return the season for a month in the active world definition.

        If the active calendar does not provide an explicit season tag for that
        month, the simulator falls back to the built-in ordinal month mapping
        used by the default Aethorian calendar.
        """
        return season_for_calendar(self._base_calendar_ref(), month)

    def season_for_date(
        self, year: int, month: int, day: int = 1, *, calendar_key: str = ""
    ) -> str:
        """Return the season for a historical date using the relevant calendar.

        Missing season tags fall back to the built-in ordinal month mapping so
        irregular calendars without explicit season metadata still resolve to a
        stable season label.
        """
        return season_for_calendar_date(
            base_calendar=self._base_calendar_ref(),
            calendar_baseline=self.calendar_baseline,
            calendar_history=self.calendar_history,
            year=year,
            month=month,
            day=day,
            calendar_key=calendar_key,
        )

    def clamp_calendar_position(self, month: int, day: int) -> Tuple[int, int]:
        """Clamp month/day into the active calendar's valid ranges."""
        return clamp_calendar_position_for_calendar(self._base_calendar_ref(), month, day)

    def apply_calendar_definition(
        self,
        calendar: CalendarDefinition,
        *,
        changed_year: Optional[int] = None,
        changed_month: int = 1,
        changed_day: int = 1,
    ) -> None:
        """Apply a new active calendar immediately and record its change date.

        This method is intentionally *not* a scheduler. It switches the active
        world calendar now. The optional ``changed_*`` fields exist only so
        imports, migrations, or timeline reconstruction can stamp the
        historical date of the transition in ``calendar_history``.
        """
        self._setting_bundle.world_definition.calendar = _clone_calendar(calendar)
        self.calendar_history = apply_calendar_definition_history(
            calendar=calendar,
            current_year=self.year,
            calendar_history=self.calendar_history,
            build_change_record=lambda year, month, day, changed_calendar: CalendarChangeRecord(
                year=year,
                month=month,
                day=day,
                calendar=changed_calendar,
            ),
            changed_year=changed_year,
            changed_month=changed_month,
            changed_day=changed_day,
        )

    def remaining_days_in_year(self, month: int, day: int) -> int:
        """Return how many in-world days remain including the current date."""
        return remaining_days_in_year_for_calendar(self._base_calendar_ref(), month, day)

    def advance_calendar_position(self, month: int, day: int, days: int = 1) -> Tuple[int, int, int]:
        """Advance a month/day position and return ``(month, day, year_delta)``."""
        return advance_calendar_position_for_calendar(
            self._base_calendar_ref(),
            month,
            day,
            days=days,
        )

    def advance_time(self, years: int = 1) -> None:
        for _ in range(max(0, int(years))):
            self.year += 1
            self._maybe_evolve_languages_for_year(self.year)

    def latest_absolute_day_before_or_on(self, year: int, month: int) -> int:
        """Return the latest known absolute day on or before a given report period."""
        matching_days = [
            record.absolute_day
            for record in self.event_records
            if record.absolute_day > 0 and (record.year, record.month) <= (year, month)
        ]
        return max(matching_days, default=0)

    MAX_EVENT_LOG = 2000

    def log_event(
        self,
        event_text: str,
        *,
        month: Optional[int] = None,
        day: Optional[int] = None,
    ) -> None:
        """Append a formatted compatibility display line for legacy CLI consumers.

        Contract (important):
        - This is a display-only runtime adapter and does **not** create
          canonical ``event_records`` entries.
        - New saves persist canonical ``event_records`` only.
        - Therefore, callers must use ``record_event()`` for durable history.

        When *month*/*day* are provided, the prefix includes intra-year date
        information so that the player-visible log reflects finer causality.
        """
        self._display_event_log = append_display_event_log_entry(
            self._display_event_log,
            event_text,
            translate=tr,
            year=self.year,
            max_event_log=self.MAX_EVENT_LOG,
            month=month,
            day=day,
        )

    MAX_EVENT_RECORDS = 5000

    def rebuild_compatibility_event_log(self) -> None:
        """Drop stale display-only lines when canonical history exists."""
        self._display_event_log = rebuild_display_event_log(
            self._display_event_log,
            self.event_records,
            max_event_log=self.MAX_EVENT_LOG,
        )

    def get_compatibility_event_log(self, last_n: Optional[int] = None) -> List[str]:
        """Return the legacy event-log adapter, projecting from records if needed."""
        log = list(self.event_log)
        if last_n is not None:
            return log[-last_n:]
        return list(log)

    def record_event(self, record: WorldEventRecord) -> WorldEventRecord:
        """Store a structured event record in the canonical world history.

        Returns the canonical stored record (may be a normalized copy).
        """
        self._event_index.ensure_current(self.event_records)
        actor_ids = [record.primary_actor_id] + list(record.secondary_actor_ids)
        watched_tags: List[str] = []
        for actor_id in actor_ids:
            if not actor_id:
                continue
            actor = self.get_character_by_id(actor_id)
            if actor is None:
                continue
            if actor.favorite or actor.spotlighted or actor.playable:
                watched_tags.append(f"{self.WATCHED_ACTOR_TAG_PREFIX}{actor_id}")
        if watched_tags:
            record.tags = list(dict.fromkeys(list(record.tags) + watched_tags))

        stored_record = append_canonical_event_record(
            record=record,
            event_records=self.event_records,
            location_index=self._location_id_index,
            grid=self.grid,
            max_event_records=self.MAX_EVENT_RECORDS,
            existing_record_ids=self._event_index.record_ids,
        )
        self._event_index.invalidate()
        self._display_event_log = []
        return stored_record

    def apply_event_impact(self, kind: str, location_id: Optional[str]) -> List[Dict[str, Any]]:
        """Update location state quantities based on an event kind (design §5.5).

        Returns a list of impact dicts recording the state changes applied,
        each containing ``target_type``, ``target_id``, ``attribute``,
        ``old_value``, ``new_value``, and ``delta``.
        """
        return apply_event_impact_to_location(
            kind=kind,
            location_id=location_id,
            location_index=self._location_id_index,
            clamp_state=_clamp_state,
            impact_rules=self.event_impact_rules,
        )

    # Annual decay rate: each year, event-driven deviations from baseline
    # decay by this fraction toward the region-type default, preventing
    # runaway accumulation of danger/traffic/mood changes over long runs.
    # Set high enough to counterbalance propagation from neighboring
    # high-danger/traffic locations (e.g. dungeons, mountains).
    _STATE_DECAY_RATE = 0.30

    def _decay_toward_baseline(self, months: int = 12) -> None:
        """Pull volatile state fields back toward their region-type defaults."""
        decay_toward_baseline(
            locations=self.grid.values(),
            months=months,
            months_per_year=self.months_per_year,
            state_decay_rate=self._STATE_DECAY_RATE,
            location_defaults=self.location_state_defaults,
            clamp_state=_clamp_state,
        )

    def propagate_state(self, months: int = 12) -> None:
        """Propagate location state using the configured propagation topology."""
        period_months = max(1, months)
        self._decay_toward_baseline(months=period_months)
        propagate_state_changes(
            locations=self.grid.values(),
            location_index=self._location_id_index,
            get_neighbors=self.get_propagation_neighboring_locations,
            months=period_months,
            months_per_year=self.months_per_year,
            clamp_state=_clamp_state,
            propagation_rules=self.propagation_rules,
        )

    def get_events_by_location(self, location_id: str) -> List[WorldEventRecord]:
        """Return all event records for a specific location."""
        return self._event_index.by_location_id(self.event_records, location_id)

    def get_events_by_actor(self, char_id: str) -> List[WorldEventRecord]:
        """Return all event records involving a specific character."""
        return self._event_index.by_actor_id(self.event_records, char_id)

    def get_events_by_year(self, year: int) -> List[WorldEventRecord]:
        """Return all event records for a specific year."""
        return self._event_index.by_year_value(self.event_records, year)

    def get_events_by_month(self, year: int, month: int) -> List[WorldEventRecord]:
        """Return all event records for a specific in-world month."""
        return self._event_index.by_month_value(self.event_records, year, month)

    def get_events_by_kind(self, kind: str) -> List[WorldEventRecord]:
        """Return all event records for a specific canonical event kind."""
        return self._event_index.by_kind_value(self.event_records, kind)

    def render_map(self, highlight_location: Optional[str] = None) -> str:
        """Return a stable ASCII grid of the world map.

        This is a backward-compatible wrapper.  Internally it delegates
        to :func:`ui.map_renderer.build_map_info` and
        :func:`ui.map_renderer.render_map_ascii` so that the rendering
        logic lives in the UI layer.
        """
        from .ui.map_renderer import build_map_info, render_map_ascii
        info = build_map_info(self, highlight_location)
        return render_map_ascii(info)

    def _grid_matches_bundle_seeds(self) -> bool:
        bundle_locations = sorted(
            (
                seed.location_id,
                seed.name,
                seed.description,
                seed.region_type,
                int(seed.x),
                int(seed.y),
            )
            for seed in self._setting_bundle.world_definition.site_seeds
            if 0 <= seed.x < self.width and 0 <= seed.y < self.height
        )
        current_locations = sorted(
            (
                loc.id,
                loc.canonical_name,
                loc.description,
                loc.region_type,
                int(loc.x),
                int(loc.y),
            )
            for loc in self.grid.values()
        )
        return bundle_locations == current_locations

    def _overlay_serialized_route_state(self, serialized_routes: List[Dict[str, Any]]) -> None:
        """Overlay mutable route state onto the canonical route graph."""
        overlay_serialized_route_state(self.routes, serialized_routes)

    def to_dict(self) -> Dict[str, Any]:
        return serialize_world_state(self)

    def _location_state_from_dict(self, data: Dict[str, Any]) -> LocationState:
        """Restore LocationState using the active bundle for missing defaults."""
        canonical_name = data.get("canonical_name") or data.get("name", "")
        loc_id = data.get("id")
        loc_id = self.normalize_location_id(loc_id, location_name=canonical_name)
        region_type = data["region_type"]
        defaults = self.location_state_defaults(loc_id, region_type)
        return LocationState(
            id=loc_id,
            canonical_name=canonical_name,
            description=data["description"],
            region_type=region_type,
            x=data["x"],
            y=data["y"],
            prosperity=data.get("prosperity", defaults["prosperity"]),
            safety=data.get("safety", defaults["safety"]),
            mood=data.get("mood", defaults["mood"]),
            danger=data.get("danger", defaults["danger"]),
            traffic=data.get("traffic", defaults["traffic"]),
            rumor_heat=data.get("rumor_heat", defaults["rumor_heat"]),
            road_condition=data.get("road_condition", defaults["road_condition"]),
            visited=data.get("visited", False),
            controlling_faction_id=data.get("controlling_faction_id"),
            recent_event_ids=_string_list_payload(data.get("recent_event_ids", []), field_name="recent_event_ids"),
            aliases=_string_list_payload(data.get("aliases", []), field_name="aliases"),
            generated_endonym=str(data.get("generated_endonym", "")),
            memorial_ids=_string_list_payload(data.get("memorial_ids", []), field_name="memorial_ids"),
            live_traces=_trace_list_payload(data.get("live_traces", []), field_name="live_traces"),
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "World":
        """Restore a World from a serialised dict.

        Uses ``_skip_defaults=True`` so construction stays inert until
        the active source of truth is known. If an embedded
        ``setting_bundle`` is present, world structure is rebuilt from
        its site seeds and the serialized grid is treated as runtime
        state to overlay onto those locations. Otherwise, the serialized
        grid remains the compatibility source for structure.

        If no terrain data is present in *data*, terrain/site/routes
        are derived from the loaded grid via ``_build_terrain_from_grid()``.
        """
        world = cls(
            name=data["name"],
            lore=data.get("lore"),
            width=data.get("width", 5),
            height=data.get("height", 5),
            year=data.get("year", 1000),
            _skip_defaults=True,
        )
        return hydrate_world_state(
            world,
            data,
            memorial_record_cls=MemorialRecord,
            world_event_record_cls=WorldEventRecord,
            calendar_change_record_cls=CalendarChangeRecord,
            clone_calendar=_clone_calendar,
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"World(name={self.name!r}, year={self.year}, characters={len(self.characters)})"

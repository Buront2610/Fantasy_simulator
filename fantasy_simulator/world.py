"""
world.py - World map, LocationState dataclass, and the World class.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .event_models import WorldEventRecord
from .i18n import tr
from .rule_override_resolution import (
    clone_default_event_impact_rules,
    clone_default_propagation_rules,
    resolve_event_impact_rule_overrides,
    resolve_propagation_rule_overrides,
)
from .world_event_log import format_event_log_entry, project_compatibility_event_log
from .world_event_state import (
    apply_event_impact_to_location,
    append_canonical_event_record,
)
from .world_state_propagation import (
    decay_toward_baseline,
    propagate_state_changes,
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
    bundle_from_dict_validated,
    default_aethoria_bundle,
    legacy_location_id_alias,
    validate_setting_bundle,
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
    assemble_atlas_layout_inputs,
    build_cached_world_structure,
    build_default_atlas_layout,
    normalize_route_payload,
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
    return [dict(item) for item in payload]


class ObservableRouteList(list[RouteEdge]):
    """List wrapper that marks cached route projections dirty on mutation."""

    def __init__(self, iterable: Optional[List[RouteEdge]] = None, *, on_change: Any = None) -> None:
        super().__init__(iterable or [])
        self._on_change = on_change

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def __setitem__(self, index: Any, value: Any) -> None:
        super().__setitem__(index, value)
        self._notify()

    def __delitem__(self, index: Any) -> None:
        super().__delitem__(index)
        self._notify()

    def append(self, value: RouteEdge) -> None:
        super().append(value)
        self._notify()

    def extend(self, values: List[RouteEdge]) -> None:
        super().extend(values)
        self._notify()

    def insert(self, index: int, value: RouteEdge) -> None:
        super().insert(index, value)
        self._notify()

    def pop(self, index: int = -1) -> RouteEdge:
        value = super().pop(index)
        self._notify()
        return value

    def remove(self, value: RouteEdge) -> None:
        super().remove(value)
        self._notify()

    def clear(self) -> None:
        super().clear()
        self._notify()


class ReadOnlyEventLog(list[str]):
    """List-like read-only view for compatibility event-log access."""

    def _readonly(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("event_log is a read-only view; use log_event() or record_event()")

    append = _readonly
    clear = _readonly
    extend = _readonly
    insert = _readonly
    pop = _readonly
    remove = _readonly
    reverse = _readonly
    sort = _readonly

    def __delitem__(self, _index: Any) -> None:
        self._readonly()

    def __iadd__(self, _other: Any) -> "ReadOnlyEventLog":
        self._readonly()
        return self

    def __imul__(self, _other: Any) -> "ReadOnlyEventLog":
        self._readonly()
        return self

    def __setitem__(self, _index: Any, _value: Any) -> None:
        self._readonly()


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
            "memorial_ids": list(self.memorial_ids),
            "live_traces": [dict(trace) for trace in self.live_traces],
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
            memorial_ids=_string_list_payload(data.get("memorial_ids", []), field_name="memorial_ids"),
            live_traces=_trace_list_payload(data.get("live_traces", []), field_name="live_traces"),
        )


class World:
    """Represents the entire game world."""

    WATCHED_ACTOR_TAG_PREFIX = "watched_actor:"
    WATCHED_ACTOR_INFERRED_TAG = "watched_actor_inferred"

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
        if self.event_records:
            return ReadOnlyEventLog(self._project_compatibility_event_log())
        return ReadOnlyEventLog(self._display_event_log)

    @event_log.setter
    def event_log(self, value: List[str]) -> None:
        trimmed = list(value)[-self.MAX_EVENT_LOG:]
        self._display_event_log = trimmed

    @property
    def routes(self) -> ObservableRouteList:
        return self._routes

    @routes.setter
    def routes(self, value: List[RouteEdge]) -> None:
        if hasattr(self, "_routes"):
            for route in self._routes:
                route._on_change = None
        wrapped = ObservableRouteList(list(value), on_change=self._mark_routes_dirty)
        self._routes = wrapped
        self._attach_route_observers()
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
        """Replace bundle-backed metadata without rebuilding world structure."""
        previous_calendar = None
        if hasattr(self, "_setting_bundle") and self._setting_bundle is not None:
            previous_calendar = self._setting_bundle.world_definition.calendar.to_dict()
        self._setting_bundle = _clone_setting_bundle(bundle)
        if hasattr(self, "lore"):
            self.lore = self._setting_bundle.world_definition.lore_text
        if hasattr(self, "calendar_baseline"):
            next_calendar = self._setting_bundle.world_definition.calendar
            if previous_calendar is None or previous_calendar != next_calendar.to_dict():
                self.calendar_baseline = _clone_calendar(next_calendar)
                if hasattr(self, "calendar_history"):
                    self.calendar_history = []
        self.event_impact_rules = resolve_event_impact_rule_overrides(
            self._setting_bundle.world_definition.event_impact_rules
        )
        self.propagation_rules = resolve_propagation_rule_overrides(
            self._setting_bundle.world_definition.propagation_rules
        )

    def apply_setting_bundle(self, bundle: SettingBundle) -> None:
        """Apply a bundle while keeping derived world structures consistent."""
        validate_setting_bundle(bundle, source="World.setting_bundle")
        previous_bundle = getattr(self, "_setting_bundle", None)
        previous_locations = list(getattr(self, "grid", {}).values())
        self._set_setting_bundle_metadata(bundle)
        if hasattr(self, "grid"):
            topology_changed = (
                previous_bundle is None
                or self._topology_signature(previous_bundle) != self._topology_signature(bundle)
            )
            if topology_changed:
                self._build_default_map(previous_locations=previous_locations)
                self._normalize_references_after_bundle_change()
            else:
                self._refresh_locations_from_site_seeds()

    @staticmethod
    def _topology_signature(bundle: SettingBundle) -> Tuple[Tuple[Any, ...], Tuple[Any, ...]]:
        world = bundle.world_definition
        site_signature = tuple(
            (seed.location_id, seed.region_type, seed.x, seed.y)
            for seed in world.site_seeds
        )
        route_signature = tuple(
            (
                seed.route_id,
                seed.from_site_id,
                seed.to_site_id,
                seed.route_type,
                int(seed.distance),
                bool(seed.blocked),
            )
            for seed in world.route_seeds
        )
        return site_signature, route_signature

    def _refresh_locations_from_site_seeds(self) -> None:
        """Refresh static location metadata when bundle lore changes but topology does not."""
        for seed in self._setting_bundle.world_definition.site_seeds:
            existing = self._location_id_index.get(seed.location_id)
            if existing is None:
                continue
            replacement = self._location_state_from_site_seed(seed)
            self._copy_location_runtime_state(existing, replacement)
            self._register_location(replacement)

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
        target.aliases = list(source.aliases)
        target.memorial_ids = list(source.memorial_ids)
        target.live_traces = [dict(trace) for trace in source.live_traces]

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
        for seed in self._setting_bundle.world_definition.site_seeds:
            if seed.name == name:
                return seed.location_id
        return None

    def resolve_location_id_from_name(self, name: str) -> str:
        """Resolve a location name through the active bundle with slug fallback."""
        return self._bundle_location_id_for_name(name) or fallback_location_id(name)

    def _legacy_location_id_aliases(self) -> Dict[str, str]:
        """Return legacy fallback-slug IDs that should map to canonical bundle IDs."""
        aliases: Dict[str, str] = {}
        for seed in self._setting_bundle.world_definition.site_seeds:
            legacy_id = legacy_location_id_alias(seed.name)
            if legacy_id != seed.location_id:
                aliases[legacy_id] = seed.location_id
        return aliases

    def normalize_location_id(
        self,
        location_id: Optional[str],
        *,
        location_name: str | None = None,
    ) -> Optional[str]:
        """Normalize persisted location IDs against the active bundle."""
        if location_id:
            aliased = self._legacy_location_id_aliases().get(location_id)
            if aliased is not None:
                return aliased
            bundle_location_ids = {
                seed.location_id
                for seed in self._setting_bundle.world_definition.site_seeds
            }
            if location_id in bundle_location_ids:
                return location_id
            if location_name is not None:
                bundle_location_id = self._bundle_location_id_for_name(location_name)
                if bundle_location_id is not None:
                    return bundle_location_id
            return location_id
        if location_name is not None:
            return self.resolve_location_id_from_name(location_name)
        return location_id

    def _repair_location_reference(
        self,
        location_id: Optional[str],
        *,
        location_name: str | None = None,
        required: bool = False,
        fallback_location_id: str | None = None,
    ) -> Optional[str]:
        """Resolve a location reference to a valid current-world location."""
        normalized = self.normalize_location_id(location_id, location_name=location_name)
        if normalized in self._location_id_index:
            return normalized
        if required:
            if fallback_location_id is not None:
                return fallback_location_id
            if self._location_id_index:
                return self._default_resident_location_id()
            return ""
        return None

    def _repair_location_references(self) -> None:
        """Repair persisted location references against the active world structure."""
        fallback_location_id = None
        if self._location_id_index:
            fallback_location_id = self._default_resident_location_id()
        for character in self.characters:
            character.location_id = (
                self._repair_location_reference(
                    character.location_id,
                    required=True,
                    fallback_location_id=fallback_location_id,
                )
                or ""
            )
        for record in self.event_records:
            record.location_id = self._repair_location_reference(record.location_id)
        for rumor in self.rumors:
            rumor.source_location_id = self._repair_location_reference(rumor.source_location_id)
        for rumor in self.rumor_archive:
            rumor.source_location_id = self._repair_location_reference(rumor.source_location_id)
        for run in self.active_adventures + self.completed_adventures:
            run.origin = (
                self._repair_location_reference(
                    run.origin,
                    required=True,
                    fallback_location_id=fallback_location_id,
                )
                or ""
            )
            run.destination = (
                self._repair_location_reference(
                    run.destination,
                    required=True,
                    fallback_location_id=fallback_location_id,
                )
                or ""
            )
        for memorial in self.memorials.values():
            memorial.location_id = (
                self._repair_location_reference(
                    memorial.location_id,
                    required=True,
                    fallback_location_id=fallback_location_id,
                )
                or ""
            )

    def _rebuild_location_memorial_ids(self) -> None:
        """Rebuild per-location memorial indices from canonical memorial records."""
        for location in self.grid.values():
            location.memorial_ids = []
        for memorial in self.memorials.values():
            location = self._location_id_index.get(memorial.location_id)
            if location is not None and memorial.memorial_id not in location.memorial_ids:
                location.memorial_ids.append(memorial.memorial_id)

    def _normalize_references_after_bundle_change(self) -> None:
        """Repair references after replacing the active setting bundle."""
        self._repair_location_references()
        self._rebuild_location_memorial_ids()
        self.rebuild_char_index()
        self.ensure_valid_character_locations()
        self.rebuild_adventure_index()
        self.rebuild_recent_event_ids()
        if self.event_records:
            self.rebuild_compatibility_event_log()

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
        return LocationState(
            id=seed.location_id,
            canonical_name=seed.name,
            description=seed.description,
            region_type=seed.region_type,
            x=seed.x,
            y=seed.y,
            **defaults,
        )

    def _build_terrain_from_grid(self, *, explicit_route_graph: Optional[bool] = None) -> None:
        """Generate terrain, sites, and routes from the current grid.

        Derives terrain biome from each ``LocationState.region_type``
        and creates provisional routes between adjacent sites only when no
        explicit route graph is defined for the current structure.
        """
        # Collect current grid as pseudo-location tuples for the builder
        location_tuples = [
            (loc.id, loc.canonical_name, loc.description,
             loc.region_type, loc.x, loc.y)
            for loc in self.grid.values()
        ]
        location_ids = {loc_id for loc_id, *_rest in location_tuples}
        use_explicit_route_graph = (
            self._grid_matches_bundle_seeds()
            if explicit_route_graph is None
            else explicit_route_graph
        )
        tmap, sites, routes, atlas_layout = build_cached_world_structure(
            width=self.width,
            height=self.height,
            locations=location_tuples,
            route_specs=(
                [
                    seed.to_dict()
                    for seed in self._setting_bundle.world_definition.route_seeds
                    if seed.from_site_id in location_ids and seed.to_site_id in location_ids
                ]
                if use_explicit_route_graph
                else None
            ),
        )
        self.terrain_map = tmap
        self.sites = sites
        self.routes = routes
        self._rebuild_site_index()
        self._rebuild_route_index()
        self._route_graph_explicit = use_explicit_route_graph
        self.atlas_layout = atlas_layout

    def _build_atlas_layout_from_current_state(self) -> AtlasLayout:
        """Generate the persistent atlas layout from current terrain/site data."""
        inputs = assemble_atlas_layout_inputs(
            width=self.width,
            height=self.height,
            sites=self.sites,
            routes=self.routes,
            terrain_cells=list(self.terrain_map.cells.values()) if self.terrain_map is not None else [],
        )
        return build_default_atlas_layout(inputs)

    def _rebuild_site_index(self) -> None:
        """Rebuild the site lookup index keyed by location_id."""
        self._site_index = {s.location_id: s for s in self.sites}

    def _mark_routes_dirty(self) -> None:
        """Mark cached route adjacency as stale after route mutations."""
        self._routes_dirty = True

    def _attach_route_observers(self) -> None:
        """Attach mutation hooks to each route in the active route collection."""
        for route in self.routes:
            route._on_change = self._mark_routes_dirty

    def _rebuild_route_index(self) -> None:
        """Rebuild route adjacency lists keyed by endpoint location id."""
        self._attach_route_observers()
        route_index: Dict[str, List[RouteEdge]] = {
            site.location_id: [] for site in self.sites
        }
        for route in self.routes:
            route_index.setdefault(route.from_site_id, []).append(route)
            route_index.setdefault(route.to_site_id, []).append(route)
        self._routes_by_site = route_index
        self._routes_dirty = False

    def _ensure_route_index_current(self) -> None:
        """Keep the cached route adjacency in sync with direct route reassignment."""
        if self._routes_dirty:
            self._rebuild_route_index()

    def _validate_topology_integrity(self) -> None:
        """Validate that restored topology is coherent with the active grid."""
        for site in self.sites:
            location = self._location_id_index.get(site.location_id)
            if location is None:
                raise ValueError(f"Serialized site references unknown location: {site.location_id!r}")
            if (site.x, site.y) != (location.x, location.y):
                raise ValueError(
                    f"Serialized site coordinates disagree with location state for {site.location_id!r}"
                )

        seen_route_ids: set[str] = set()
        seen_route_pairs: set[Tuple[str, str]] = set()
        for route in self.routes:
            if route.route_id in seen_route_ids:
                raise ValueError(f"Serialized topology contains duplicate route id: {route.route_id!r}")
            seen_route_ids.add(route.route_id)
            if route.from_site_id == route.to_site_id:
                raise ValueError(f"Serialized route forms a self-loop: {route.route_id!r}")
            if route.from_site_id not in self._site_index or route.to_site_id not in self._site_index:
                raise ValueError(f"Serialized route references unknown site: {route.route_id!r}")
            pair = tuple(sorted((route.from_site_id, route.to_site_id)))
            if pair in seen_route_pairs:
                raise ValueError(f"Serialized topology contains duplicate route pair: {pair[0]}->{pair[1]}")
            seen_route_pairs.add(pair)

    def get_site_by_id(self, location_id: str) -> Optional[Site]:
        """Return the Site record for a location, or None."""
        return self._site_index.get(location_id)

    def get_routes_for_site(self, location_id: str) -> List[RouteEdge]:
        """Return all routes connected to a site."""
        self._ensure_route_index_current()
        return list(self._routes_by_site.get(location_id, []))

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
        for location in self.grid.values():
            location.recent_event_ids = []

        for record in self.event_records:
            if record.location_id not in self._location_id_index:
                record.location_id = None
                continue
            self._location_id_index[record.location_id].recent_event_ids.append(record.record_id)

        for location in self.grid.values():
            location.recent_event_ids = location.recent_event_ids[-12:]

    def _ensure_unique_event_record_ids(self) -> None:
        """Fail fast when canonical history contains duplicate record IDs."""
        seen: set[str] = set()
        for record in self.event_records:
            if record.record_id in seen:
                raise ValueError(f"Duplicate event record ID during rebuild: {record.record_id!r}")
            seen.add(record.record_id)

    def normalize_after_load(self) -> None:
        """Rebuild derived indexes and repair invariants after deserialization."""
        self._repair_location_references()
        self.rebuild_char_index()
        self._ensure_unique_event_record_ids()
        self._backfill_watched_actor_tags_after_load()
        self.ensure_valid_character_locations()
        self.rebuild_adventure_index()
        self.rebuild_recent_event_ids()
        self._rebuild_location_memorial_ids()
        if self.event_records:
            self.rebuild_compatibility_event_log()

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
        if not watched_actor_ids:
            return

        for record in self.event_records:
            if any(tag.startswith(self.WATCHED_ACTOR_TAG_PREFIX) for tag in record.tags):
                continue
            actor_ids = [record.primary_actor_id] + list(record.secondary_actor_ids)
            watched_tags = [
                f"{self.WATCHED_ACTOR_TAG_PREFIX}{actor_id}"
                for actor_id in actor_ids
                if actor_id and actor_id in watched_actor_ids
            ]
            if watched_tags:
                record.tags = list(
                    dict.fromkeys(
                        list(record.tags)
                        + watched_tags
                        + [self.WATCHED_ACTOR_INFERRED_TAG]
                    )
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
        loc = self._location_id_index.get(location_id)
        if loc is None:
            return
        loc.live_traces.append({"year": year, "char_name": char_name, "text": text})
        if len(loc.live_traces) > self.MAX_LIVE_TRACES:
            loc.live_traces = loc.live_traces[-self.MAX_LIVE_TRACES:]

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
        self.memorials[memorial_id] = record
        loc = self._location_id_index.get(location_id)
        if loc is not None and memorial_id not in loc.memorial_ids:
            loc.memorial_ids.append(memorial_id)

    def add_alias(self, location_id: str, alias: str) -> None:
        """Append an alias to a location if not already present (design §E-2).

        Capped at ``MAX_ALIASES`` per location; duplicate strings are
        silently ignored.
        """
        loc = self._location_id_index.get(location_id)
        if loc is None:
            return
        if alias not in loc.aliases and len(loc.aliases) < self.MAX_ALIASES:
            loc.aliases.append(alias)

    def get_memorials_for_location(self, location_id: str) -> List[MemorialRecord]:
        """Return all ``MemorialRecord`` objects associated with a location."""
        loc = self._location_id_index.get(location_id)
        if loc is None:
            return []
        return [
            self.memorials[mid]
            for mid in loc.memorial_ids
            if mid in self.memorials
        ]

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
        start = (int(start_year), max(1, int(start_month)), max(1, int(start_day)))
        end = (int(end_year), max(1, int(end_month)), max(1, int(end_day)))
        if end < start:
            return 0

        elapsed = 0
        cursor_year, cursor_month, cursor_day = start
        cursor_calendar_key = start_calendar_key

        while True:
            calendar = self.calendar_definition_for_date(
                cursor_year,
                cursor_month,
                cursor_day,
                calendar_key=cursor_calendar_key,
            )
            next_year = cursor_year
            next_month = cursor_month + 1
            if next_month > calendar.months_per_year:
                next_month = 1
                next_year += 1
            if (next_year, next_month, 1) > end:
                break
            elapsed += 1
            cursor_year, cursor_month, cursor_day = next_year, next_month, 1
            cursor_calendar_key = ""

        return elapsed

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
        if not calendar_key:
            return self._base_calendar_ref()
        if self._base_calendar_ref().calendar_key == calendar_key:
            return self._base_calendar_ref()
        if self.calendar_baseline.calendar_key == calendar_key:
            return self.calendar_baseline
        for entry in reversed(sorted(self.calendar_history, key=lambda item: (item.year, item.month, item.day))):
            if entry.calendar.calendar_key == calendar_key:
                return entry.calendar
        return self._base_calendar_ref()

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
        if calendar_key:
            return self._calendar_definition_by_key_ref(calendar_key)
        target = (int(year), max(1, int(month)), max(1, int(day)))
        selected = self.calendar_baseline
        for entry in sorted(self.calendar_history, key=lambda item: (item.year, item.month, item.day)):
            if (entry.year, entry.month, entry.day) <= target:
                selected = entry.calendar
            else:
                break
        return selected

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
        if month in (12, 1, 2):
            return "winter"
        if month in (3, 4, 5):
            return "spring"
        if month in (6, 7, 8):
            return "summer"
        return "autumn"

    def season_for_month(self, month: int) -> str:
        """Return the season for a month in the active world definition.

        If the active calendar does not provide an explicit season tag for that
        month, the simulator falls back to the built-in ordinal month mapping
        used by the default Aethorian calendar.
        """
        season = self._base_calendar_ref().season_for_month(month)
        if season != "unknown":
            return season
        return self.get_season(month)

    def season_for_date(
        self, year: int, month: int, day: int = 1, *, calendar_key: str = ""
    ) -> str:
        """Return the season for a historical date using the relevant calendar.

        Missing season tags fall back to the built-in ordinal month mapping so
        irregular calendars without explicit season metadata still resolve to a
        stable season label.
        """
        calendar = self._calendar_definition_for_date_ref(year, month, day, calendar_key=calendar_key)
        season = calendar.season_for_month(month)
        if season != "unknown":
            return season
        return self.get_season(month)

    def clamp_calendar_position(self, month: int, day: int) -> Tuple[int, int]:
        """Clamp month/day into the active calendar's valid ranges."""
        clamped_month = max(1, min(self.months_per_year, int(month)))
        clamped_day = max(1, min(self.days_in_month(clamped_month), int(day)))
        return clamped_month, clamped_day

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
        month = max(1, min(calendar.months_per_year, int(changed_month)))
        day = max(1, min(calendar.days_in_month(month), int(changed_day)))
        self.calendar_history.append(CalendarChangeRecord(
            year=self.year if changed_year is None else changed_year,
            month=month,
            day=day,
            calendar=_clone_calendar(calendar),
        ))
        self.calendar_history.sort(key=lambda item: (item.year, item.month, item.day))

    def remaining_days_in_year(self, month: int, day: int) -> int:
        """Return how many in-world days remain including the current date."""
        clamped_month, clamped_day = self.clamp_calendar_position(month, day)
        remaining = self.days_in_month(clamped_month) - clamped_day + 1
        for month_index in range(clamped_month + 1, self.months_per_year + 1):
            remaining += self.days_in_month(month_index)
        return remaining

    def advance_calendar_position(self, month: int, day: int, days: int = 1) -> Tuple[int, int, int]:
        """Advance a month/day position and return ``(month, day, year_delta)``."""
        current_month, current_day = self.clamp_calendar_position(month, day)
        year_delta = 0
        for _ in range(max(0, int(days))):
            current_day += 1
            if current_day > self.days_in_month(current_month):
                current_day = 1
                current_month += 1
                if current_month > self.months_per_year:
                    current_month = 1
                    year_delta += 1
        return current_month, current_day, year_delta

    def advance_time(self, years: int = 1) -> None:
        self.year += years

    def latest_absolute_day_before_or_on(self, year: int, month: int) -> int:
        """Return the latest known absolute day on or before a given report period."""
        matching_days = [
            record.absolute_day
            for record in self.event_records
            if record.absolute_day > 0 and (record.year, record.month) <= (year, month)
        ]
        return max(matching_days, default=0)

    MAX_EVENT_LOG = 2000

    def _format_event_log_entry(
        self,
        event_text: str,
        *,
        year: Optional[int] = None,
        month: Optional[int] = None,
        day: Optional[int] = None,
    ) -> str:
        """Format a compatibility event-log line from canonical event data."""
        effective_year = self.year if year is None else year
        return format_event_log_entry(
            event_text,
            translate=tr,
            year=effective_year,
            month=month,
            day=day,
        )

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
        self._display_event_log.append(self._format_event_log_entry(event_text, month=month, day=day))
        if len(self._display_event_log) > self.MAX_EVENT_LOG:
            self._display_event_log = self._display_event_log[-self.MAX_EVENT_LOG:]

    MAX_EVENT_RECORDS = 5000

    def rebuild_compatibility_event_log(self) -> None:
        """Drop stale display-only lines when canonical history exists."""
        if self.event_records:
            self._display_event_log = []

    def _project_compatibility_event_log(self) -> List[str]:
        """Project the compatibility display buffer from canonical event records."""
        return project_compatibility_event_log(
            self.event_records,
            max_event_log=self.MAX_EVENT_LOG,
            translate=tr,
        )

    def _compatibility_event_log_line(self, record: WorldEventRecord) -> str:
        if record.legacy_event_log_entry is not None:
            return record.legacy_event_log_entry
        return format_event_log_entry(
            record.description,
            translate=tr,
            year=record.year,
            month=record.month,
            day=record.day,
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
        )
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
        return [r for r in self.event_records if r.location_id == location_id]

    def get_events_by_actor(self, char_id: str) -> List[WorldEventRecord]:
        """Return all event records involving a specific character."""
        return [
            r for r in self.event_records
            if r.primary_actor_id == char_id or char_id in r.secondary_actor_ids
        ]

    def get_events_by_year(self, year: int) -> List[WorldEventRecord]:
        """Return all event records for a specific year."""
        return [r for r in self.event_records if r.year == year]

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
        if not serialized_routes:
            return
        serialized_by_id: Dict[str, Dict[str, Any]] = {}
        for item in serialized_routes:
            if not isinstance(item, dict):
                raise ValueError("Serialized route overlay entries must be dicts")
            payload = normalize_route_payload(item)
            route_id = payload["route_id"]
            if route_id in serialized_by_id:
                raise ValueError(f"Serialized route overlay contains duplicate route id: {route_id!r}")
            serialized_by_id[route_id] = payload
        if not serialized_by_id:
            return
        for route in self.routes:
            payload = serialized_by_id.get(route.route_id)
            if payload is None:
                continue
            if payload["from_site_id"] != route.from_site_id or payload["to_site_id"] != route.to_site_id:
                raise ValueError(f"Serialized route overlay disagrees with canonical endpoints: {route.route_id!r}")
            route.route_type = payload["route_type"]
            route.distance = payload["distance"]
            route.blocked = payload["blocked"]

    def to_dict(self) -> Dict[str, Any]:
        lore_text = self._setting_bundle.world_definition.lore_text
        result: Dict[str, Any] = {
            "name": self.name,
            "lore": lore_text,
            "width": self.width,
            "height": self.height,
            "year": self.year,
            "grid": [loc.to_dict() for loc in self.grid.values()],
            "event_records": [r.to_dict() for r in self.event_records],
            "rumors": [r.to_dict() for r in self.rumors],
            "rumor_archive": [r.to_dict() for r in self.rumor_archive],
            "active_adventures": [run.to_dict() for run in self.active_adventures],
            "completed_adventures": [run.to_dict() for run in self.completed_adventures],
            "memorials": {k: v.to_dict() for k, v in self.memorials.items()},
            "calendar_baseline": self.calendar_baseline.to_dict(),
            "calendar_history": [entry.to_dict() for entry in self.calendar_history],
        }
        bundle_backed_topology = self._setting_bundle is not None and self._grid_matches_bundle_seeds()
        # PR-G: persist terrain/site/route layers for non-bundle-backed worlds.
        # Bundle-backed worlds persist route state separately from the
        # canonical bundle topology to avoid conflicting sources of truth.
        if self.terrain_map is not None and not bundle_backed_topology:
            result["terrain_map"] = self.terrain_map.to_dict()
        if self.sites and not bundle_backed_topology:
            result["sites"] = [s.to_dict() for s in self.sites]
        if self.routes:
            result["routes"] = [r.to_dict() for r in self.routes]
        # PR-G2: persist atlas layout
        if self.atlas_layout is not None:
            result["atlas_layout"] = self.atlas_layout.to_dict()
        if self._setting_bundle is not None:
            result["setting_bundle"] = self._setting_bundle.to_dict()
        return result

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
        from .adventure import AdventureRun
        from .rumor import Rumor

        world = cls(
            name=data["name"],
            lore=data.get("lore"),
            width=data.get("width", 5),
            height=data.get("height", 5),
            year=data.get("year", 1000),
            _skip_defaults=True,
        )
        serialized_grid = list(data.get("grid", []))
        bundle_backed_structure = False
        if "setting_bundle" in data:
            world._set_setting_bundle_metadata(
                bundle_from_dict_validated(
                    data["setting_bundle"],
                    source="embedded world.setting_bundle",
                )
            )
            if world._serialized_grid_is_compatible_with_active_bundle(serialized_grid):
                bundle_backed_structure = True
                world._build_default_map()
                world._overlay_serialized_grid_runtime_state(serialized_grid)
            else:
                world._register_serialized_grid_locations(serialized_grid)
        else:
            world._register_serialized_grid_locations(serialized_grid)
        world.event_log = list(data.get("event_log", []))
        world.event_records = [
            WorldEventRecord.from_dict(r) for r in data.get("event_records", [])
        ]
        for record in world.event_records:
            record.location_id = world.normalize_location_id(record.location_id)
        world.rumors = [
            Rumor.from_dict(r) for r in data.get("rumors", [])
        ]
        for rumor in world.rumors:
            rumor.source_location_id = world.normalize_location_id(rumor.source_location_id)
        world.rumor_archive = [
            Rumor.from_dict(r) for r in data.get("rumor_archive", [])
        ]
        for rumor in world.rumor_archive:
            rumor.source_location_id = world.normalize_location_id(rumor.source_location_id)
        world.active_adventures = [
            AdventureRun.from_dict(run) for run in data.get("active_adventures", [])
        ]
        world.completed_adventures = [
            AdventureRun.from_dict(run) for run in data.get("completed_adventures", [])
        ]
        for run in world.active_adventures + world.completed_adventures:
            run.origin = world.normalize_location_id(run.origin) or run.origin
            run.destination = world.normalize_location_id(run.destination) or run.destination
        world.memorials = {
            k: MemorialRecord.from_dict(v) for k, v in data.get("memorials", {}).items()
        }
        world.calendar_baseline = CalendarDefinition.from_dict(
            data.get(
                "calendar_baseline",
                world.setting_bundle.world_definition.calendar.to_dict(),
            )
        )
        world.calendar_history = [
            CalendarChangeRecord.from_dict(item)
            for item in data.get("calendar_history", [])
        ]

        # PR-G: when the active bundle already defines the authoritative site set,
        # rebuild topology from that grid so stale serialized routes cannot
        # override the active bundle graph. Otherwise restore serialized topology.
        if bundle_backed_structure:
            world._build_terrain_from_grid()
            world._overlay_serialized_route_state(data.get("routes", []))
            world._rebuild_route_index()
        elif "terrain_map" in data:
            world.terrain_map = TerrainMap.from_dict(data["terrain_map"])
            world.sites = [Site.from_dict(s) for s in data.get("sites", [])]
            world.routes = [RouteEdge.from_dict(r) for r in data.get("routes", [])]
            world._route_graph_explicit = True
            for site in world.sites:
                site.location_id = world.normalize_location_id(site.location_id) or site.location_id
            for route in world.routes:
                route.from_site_id = world.normalize_location_id(route.from_site_id) or route.from_site_id
                route.to_site_id = world.normalize_location_id(route.to_site_id) or route.to_site_id
            world._rebuild_site_index()
            world._rebuild_route_index()
            world._validate_topology_integrity()
        else:
            world._build_terrain_from_grid()

        # PR-G2: restore atlas layout if present, otherwise backfill it
        # from the loaded terrain/site data so fresh v7 saves and older
        # partially-upgraded saves converge on the same state shape.
        if "atlas_layout" in data:
            world.atlas_layout = AtlasLayout.from_dict(data["atlas_layout"])
        else:
            world.atlas_layout = world._build_atlas_layout_from_current_state()

        if "calendar_baseline" not in data:
            world.calendar_baseline = _clone_calendar(world.setting_bundle.world_definition.calendar)

        world.normalize_after_load()
        return world

    def __repr__(self) -> str:  # pragma: no cover
        return f"World(name={self.name!r}, year={self.year}, characters={len(self.characters)})"

"""
world.py - World aggregate and compatibility exports.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .event_models import WorldEventRecord
from .language.engine import LanguageEngine, fallback_evolution_targets
from .language.state import LanguageEvolutionRecord, LanguageRuntimeState
from .rule_override_resolution import (
    clone_default_event_impact_rules,
    clone_default_propagation_rules,
)
from . import world_language_facade as language_facade
from . import world_event_log_facade as event_log_facade
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
from .world_actor_index import (
    add_adventure as add_adventure_to_index,
    add_character as add_character_to_index,
    characters_at_location,
    complete_adventure as complete_adventure_in_index,
    default_resident_location_id,
    ensure_valid_character_locations as ensure_valid_character_locations_in_index,
    location_ids as location_ids_for_locations,
    location_name as location_name_for_id,
    location_names as location_names_for_locations,
    mark_location_visited as mark_location_visited_in_index,
    rebuild_adventure_index as build_adventure_index,
    rebuild_character_index,
    remove_character as remove_character_from_index,
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
    replace_routes,
    routes_for_site,
)
from .world_event_state import (
    apply_event_impact_to_location,
)
from .world_event_history import (
    latest_absolute_day_before_or_on as latest_event_absolute_day_before_or_on,
    record_world_event,
)
from .world_event_queries import (
    events_by_actor,
    events_by_kind,
    events_by_location,
    events_by_month,
    events_by_year,
)
from .world_dynamic_changes import (
    apply_controlling_faction,
    apply_location_rename,
    apply_route_blocked_state,
)
from .world_event_index import EventHistoryIndex
from . import world_calendar_facade as calendar_facade
from .world_topology_queries import (
    connected_site_ids,
    grid_neighboring_locations,
    propagation_neighboring_locations,
    reachable_location_ids as reachable_topology_location_ids,
    travel_neighboring_locations,
)
from .world_state_runtime import (
    decay_world_state,
    propagate_world_state,
)
from .world_location_state import (
    LocationState,
    clamp_state as _clamp_state,
    configure_location_state_resolvers,
    location_state_from_site_seed,
)
from .world_location_structure import (
    clear_world_structure,
    copy_location_runtime_state,
    default_location_entries as default_location_entries_from_seeds,
    grid_matches_site_seeds,
    preserved_locations_by_normalized_id,
    register_location,
    serialized_grid_is_compatible_with_site_seeds,
    site_seed_tags,
)
from .world_records import CalendarChangeRecord, MemorialRecord
from .world_topology_state import (
    WorldTopologyState,
    build_atlas_layout_from_topology,
    build_topology_from_locations,
    overlay_serialized_route_state,
    validate_topology_integrity,
)
from .world_topology_runtime import (
    apply_topology_state,
    route_index_by_site,
    site_index_by_location,
)
from .world_topology import (
    PROPAGATION_TOPOLOGY_TRAVEL,
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


configure_location_state_resolvers(
    fallback_resolver=fallback_location_id,
    defaults_resolver=get_location_state_defaults,
)


def _clone_calendar(calendar: CalendarDefinition) -> CalendarDefinition:
    return CalendarDefinition.from_dict(calendar.to_dict())


def _clone_setting_bundle(bundle: SettingBundle) -> SettingBundle:
    return SettingBundle.from_dict(bundle.to_dict())


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
        return event_log_facade.event_log_view(self)

    @event_log.setter
    def event_log(self, value: List[str]) -> None:
        event_log_facade.set_event_log_entries(self, value)

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
        return language_facade.language_engine(self)

    def naming_rules_for_identity(
        self,
        *,
        race: str | None = None,
        tribe: str | None = None,
        region: str | None = None,
    ):
        return language_facade.naming_rules_for_identity(self, race=race, tribe=tribe, region=region)

    def resolve_language_for_identity(
        self,
        *,
        race: str | None = None,
        tribe: str | None = None,
        region: str | None = None,
    ) -> str | None:
        return language_facade.resolve_language_for_identity(self, race=race, tribe=tribe, region=region)

    def describe_language_lineage(self, language_key: str) -> List[str]:
        return language_facade.describe_language_lineage(self, language_key)

    def location_endonym(self, location_id: str) -> str | None:
        return language_facade.location_endonym(self, location_id)

    def language_status(self) -> List[Dict[str, Any]]:
        return language_facade.language_status(self)

    def language_evolution_records(self, language_key: str) -> List[LanguageEvolutionRecord]:
        return language_facade.language_evolution_records(self, language_key)

    def _register_location(self, loc: LocationState) -> None:
        register_location(
            grid=self.grid,
            location_name_index=self._location_name_index,
            location_id_index=self._location_id_index,
            location=loc,
        )

    def _clear_world_structure(self) -> None:
        """Reset world structures derived from the active location grid."""
        clear_world_structure(self)

    def _copy_location_runtime_state(self, source: LocationState, target: LocationState) -> None:
        """Preserve mutable location state across structural rebuilds."""
        copy_location_runtime_state(source, target)

    def _refresh_generated_endonyms(
        self,
        stale_endonyms_by_location_id: Dict[str, str] | None = None,
    ) -> None:
        language_facade.refresh_generated_endonyms(
            self,
            stale_endonyms_by_location_id=stale_endonyms_by_location_id,
        )

    def _derive_language_evolution_record(self, language_key: str, year: int) -> LanguageEvolutionRecord | None:
        return language_facade.derive_language_evolution_record(self, language_key=language_key, year=year)

    def _apply_language_evolution_record(self, record: LanguageEvolutionRecord) -> bool:
        return language_facade.apply_language_evolution_record(self, record)

    def _maybe_evolve_languages_for_year(self, year: int) -> None:
        language_facade.maybe_evolve_languages_for_year(self, year)

    def _build_default_map(self, previous_locations: Optional[List[LocationState]] = None) -> None:
        """Rebuild the world from the active setting bundle's site seeds.

        Only locations whose ``(x, y)`` fall within ``self.width x
        self.height`` are registered.  This means ``World(width=3,
        height=3)`` will contain only the locations that fit.
        """
        if previous_locations is None:
            previous_locations = list(self.grid.values())
        preserved_by_id = preserved_locations_by_normalized_id(
            previous_locations,
            normalize_location_id=lambda loc_id, name: self.normalize_location_id(loc_id, location_name=name),
        )
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
        return default_location_entries_from_seeds(
            self._setting_bundle.world_definition.site_seeds,
            width=self.width,
            height=self.height,
        )

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
        return serialized_grid_is_compatible_with_site_seeds(
            grid_data,
            site_seeds=self._setting_bundle.world_definition.site_seeds,
            normalize_location_id=lambda loc_id, name: self.normalize_location_id(loc_id, location_name=name),
        )

    def _site_seed_tags(self, location_id: str) -> List[str]:
        """Return semantic tags for a location from the active setting bundle."""
        return site_seed_tags(self._setting_bundle.world_definition.site_seeds, location_id)

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
        return location_state_from_site_seed(
            seed,
            defaults_for_location=self.location_state_defaults,
            endonym_for_location=self.location_endonym,
        )

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
        apply_topology_state(self, topology_state)

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
        self._site_index = site_index_by_location(self.sites)

    def _mark_routes_dirty(self) -> None:
        """Mark cached route adjacency as stale after route mutations."""
        self._routes_dirty = True

    def _rebuild_route_index(self) -> None:
        """Rebuild route adjacency lists keyed by endpoint location id."""
        self._routes_by_site = route_index_by_site(
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
        return connected_site_ids(
            location_id,
            get_routes_for_site=self.get_routes_for_site,
        )

    def get_grid_neighboring_locations(self, location_id: str) -> List[LocationState]:
        """Return adjacency by physical map grid, regardless of route state."""
        return grid_neighboring_locations(
            location_id,
            location_index=self._location_id_index,
            grid=self.grid,
        )

    def get_travel_neighboring_locations(self, location_id: str) -> List[LocationState]:
        """Return neighbors reachable for travel using the travel topology contract."""
        return travel_neighboring_locations(
            location_id,
            location_index=self._location_id_index,
            grid=self.grid,
            routes=self.routes,
            route_graph_explicit=self._route_graph_explicit,
            get_routes_for_site=self.get_routes_for_site,
        )

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
        return propagation_neighboring_locations(
            location_id,
            location_index=self._location_id_index,
            grid=self.grid,
            routes=self.routes,
            route_graph_explicit=self._route_graph_explicit,
            get_routes_for_site=self.get_routes_for_site,
            topology_mode=topology_mode,
            include_blocked_routes=effective_include_blocked_routes,
        )

    def reachable_location_ids(self, location_id: str) -> List[str]:
        """Return all reachable location_ids from ``location_id``."""
        return reachable_topology_location_ids(
            location_id,
            location_index=self._location_id_index,
            get_travel_neighbors=self.get_travel_neighboring_locations,
        )

    def _location_ids_for_site_tag(self, tag: str) -> List[str]:
        """Return in-bounds location_ids for bundle site seeds carrying *tag*."""
        return [
            seed.location_id
            for seed in self._setting_bundle.world_definition.site_seeds
            if tag in seed.tags and seed.location_id in self._location_id_index
        ]

    def _default_resident_location_id(self) -> str:
        return default_resident_location_id(
            locations=self.grid.values(),
            location_index=self._location_id_index,
            location_ids_for_site_tag=self._location_ids_for_site_tag,
        )

    def mark_location_visited(self, location_id: str) -> None:
        """Mark a location as visited when it is meaningfully occupied or reached."""
        mark_location_visited_in_index(self._location_id_index, location_id)

    def ensure_valid_character_locations(self) -> None:
        """Repair invalid location references after loading legacy data."""
        ensure_valid_character_locations_in_index(
            characters=self.characters,
            location_index=self._location_id_index,
            default_location_id=self._default_resident_location_id,
            mark_visited=self.mark_location_visited,
        )

    def add_character(self, character: Character, rng: Any = random) -> None:
        add_character_to_index(
            characters=self.characters,
            character_index=self._char_index,
            location_index=self._location_id_index,
            locations=self.grid.values(),
            character=character,
            default_location_id=self._default_resident_location_id,
            mark_visited=self.mark_location_visited,
            rng=rng,
        )

    def rebuild_char_index(self) -> None:
        """Rebuild the character ID index after external mutations."""
        self._char_index = rebuild_character_index(self.characters)

    def remove_character(self, char_id: str) -> None:
        self.characters = remove_character_from_index(
            characters=self.characters,
            character_index=self._char_index,
            char_id=char_id,
        )

    def get_character_by_id(self, char_id: str) -> Optional[Character]:
        return self._char_index.get(char_id)

    def get_adventure_by_id(self, adventure_id: str) -> Optional[AdventureRun]:
        return self._adventure_index.get(adventure_id)

    def rebuild_adventure_index(self) -> None:
        """Rebuild the adventure ID index after loading or external mutations."""
        self._adventure_index = build_adventure_index(
            self.active_adventures,
            self.completed_adventures,
        )

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
        add_adventure_to_index(
            active_adventures=self.active_adventures,
            adventure_index=self._adventure_index,
            run=run,
        )

    def complete_adventure(self, adventure_id: str) -> None:
        self.active_adventures = complete_adventure_in_index(
            active_adventures=self.active_adventures,
            completed_adventures=self.completed_adventures,
            adventure_id=adventure_id,
        )

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

    def rename_location(self, location_id: str, new_name: str) -> str:
        """Rename a location and keep the previous name as an alias."""
        old_name = apply_location_rename(
            self._location_id_index,
            location_id=location_id,
            new_name=new_name,
            max_aliases=self.MAX_ALIASES,
        )
        location = self._location_id_index[location_id]
        if old_name != location.canonical_name:
            self._location_name_index.pop(old_name, None)
            self._location_name_index[location.canonical_name] = location
        return old_name

    def set_location_controlling_faction(self, location_id: str, faction_id: Optional[str]) -> Optional[str]:
        """Set the controlling faction for a location and return the previous value."""
        return apply_controlling_faction(
            self._location_id_index,
            location_id=location_id,
            faction_id=faction_id,
        )

    def set_route_blocked(self, route_id: str, blocked: bool) -> bool:
        """Set route passability and return the previous blocked state."""
        return apply_route_blocked_state(self.routes, route_id=route_id, blocked=blocked)

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
        return location_names_for_locations(self.grid.values())

    @property
    def location_ids(self) -> List[str]:
        return location_ids_for_locations(self.grid.values())

    def get_location_by_name(self, name: str) -> Optional[LocationState]:
        return self._location_name_index.get(name)

    def get_location_by_id(self, location_id: str) -> Optional[LocationState]:
        return self._location_id_index.get(location_id)

    def location_name(self, location_id: str) -> str:
        return location_name_for_id(self._location_id_index, location_id)

    def get_characters_at_location(self, location_id: str) -> List[Character]:
        return characters_at_location(self.characters, location_id)

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
        return calendar_facade.months_elapsed_between(
            self,
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
        return calendar_facade.base_calendar_ref(self)

    @property
    def calendar_definition(self):
        return calendar_facade.calendar_definition(self, clone_calendar=_clone_calendar)

    @property
    def months_per_year(self) -> int:
        return calendar_facade.months_per_year(self)

    @property
    def days_per_year(self) -> int:
        return calendar_facade.days_per_year(self)

    def days_in_month(self, month: int) -> int:
        return calendar_facade.days_in_month(self, month)

    def month_display_name(self, month: int) -> str:
        return calendar_facade.month_display_name(self, month)

    def _calendar_definition_by_key_ref(self, calendar_key: str) -> CalendarDefinition:
        return calendar_facade.calendar_definition_by_key_ref(self, calendar_key)

    def calendar_definition_by_key(self, calendar_key: str) -> CalendarDefinition:
        return calendar_facade.calendar_definition_by_key(
            self,
            calendar_key,
            clone_calendar=_clone_calendar,
        )

    def _calendar_definition_for_date_ref(
        self,
        year: int,
        month: int = 1,
        day: int = 1,
        *,
        calendar_key: str = "",
    ) -> CalendarDefinition:
        return calendar_facade.calendar_definition_for_date_ref(
            self,
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
        return calendar_facade.calendar_definition_for_date(
            self,
            year,
            month,
            day,
            calendar_key=calendar_key,
            clone_calendar=_clone_calendar,
        )

    def months_per_year_for_date(
        self, year: int, month: int = 1, day: int = 1, *, calendar_key: str = ""
    ) -> int:
        return calendar_facade.months_per_year_for_date(
            self,
            year,
            month,
            day,
            calendar_key=calendar_key,
        )

    def month_display_name_for_date(
        self, year: int, month: int, day: int = 1, *, calendar_key: str = ""
    ) -> str:
        return calendar_facade.month_display_name_for_date(
            self,
            year,
            month,
            day,
            calendar_key=calendar_key,
        )

    @staticmethod
    def get_season(month: int) -> str:
        """Return the default season mapping used by the built-in calendar."""
        return calendar_facade.default_season(month)

    def season_for_month(self, month: int) -> str:
        """Return the season for a month in the active world definition.

        If the active calendar does not provide an explicit season tag for that
        month, the simulator falls back to the built-in ordinal month mapping
        used by the default Aethorian calendar.
        """
        return calendar_facade.season_for_month(self, month)

    def season_for_date(
        self, year: int, month: int, day: int = 1, *, calendar_key: str = ""
    ) -> str:
        """Return the season for a historical date using the relevant calendar.

        Missing season tags fall back to the built-in ordinal month mapping so
        irregular calendars without explicit season metadata still resolve to a
        stable season label.
        """
        return calendar_facade.season_for_date(
            self,
            year=year,
            month=month,
            day=day,
            calendar_key=calendar_key,
        )

    def clamp_calendar_position(self, month: int, day: int) -> Tuple[int, int]:
        """Clamp month/day into the active calendar's valid ranges."""
        return calendar_facade.clamp_calendar_position(self, month, day)

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
        calendar_facade.apply_calendar_definition(
            self,
            calendar=calendar,
            clone_calendar=_clone_calendar,
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
        return calendar_facade.remaining_days_in_year(self, month, day)

    def advance_calendar_position(self, month: int, day: int, days: int = 1) -> Tuple[int, int, int]:
        """Advance a month/day position and return ``(month, day, year_delta)``."""
        return calendar_facade.advance_calendar_position(
            self,
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
        return latest_event_absolute_day_before_or_on(self.event_records, year=year, month=month)

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
        event_log_facade.append_event_log_entry(
            self,
            event_text,
            month=month,
            day=day,
        )

    MAX_EVENT_RECORDS = 5000

    def rebuild_compatibility_event_log(self) -> None:
        """Drop stale display-only lines when canonical history exists."""
        event_log_facade.rebuild_compatibility_event_log(self)

    def get_compatibility_event_log(self, last_n: Optional[int] = None) -> List[str]:
        """Return the legacy event-log adapter, projecting from records if needed."""
        return event_log_facade.compatibility_event_log(self, last_n=last_n)

    def record_event(self, record: WorldEventRecord) -> WorldEventRecord:
        """Store a structured event record in the canonical world history.

        Returns the canonical stored record (may be a normalized copy).
        """
        stored_record = record_world_event(
            record=record,
            event_records=self.event_records,
            event_index=self._event_index,
            location_index=self._location_id_index,
            grid=self.grid,
            max_event_records=self.MAX_EVENT_RECORDS,
            get_character_by_id=self.get_character_by_id,
            watched_actor_tag_prefix=self.WATCHED_ACTOR_TAG_PREFIX,
        )
        event_log_facade.clear_display_event_log(self)
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
        decay_world_state(
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
        propagate_world_state(
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
        return events_by_location(self._event_index, self.event_records, location_id)

    def get_events_by_actor(self, char_id: str) -> List[WorldEventRecord]:
        """Return all event records involving a specific character."""
        return events_by_actor(self._event_index, self.event_records, char_id)

    def get_events_by_year(self, year: int) -> List[WorldEventRecord]:
        """Return all event records for a specific year."""
        return events_by_year(self._event_index, self.event_records, year)

    def get_events_by_month(self, year: int, month: int) -> List[WorldEventRecord]:
        """Return all event records for a specific in-world month."""
        return events_by_month(self._event_index, self.event_records, year, month)

    def get_events_by_kind(self, kind: str) -> List[WorldEventRecord]:
        """Return all event records for a specific canonical event kind."""
        return events_by_kind(self._event_index, self.event_records, kind)

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
        return grid_matches_site_seeds(
            site_seeds=self._setting_bundle.world_definition.site_seeds,
            grid_locations=self.grid.values(),
            width=self.width,
            height=self.height,
        )

    def _overlay_serialized_route_state(self, serialized_routes: List[Dict[str, Any]]) -> None:
        """Overlay mutable route state onto the canonical route graph."""
        overlay_serialized_route_state(self.routes, serialized_routes)

    def to_dict(self) -> Dict[str, Any]:
        return serialize_world_state(self)

    def _location_state_from_dict(self, data: Dict[str, Any]) -> LocationState:
        """Restore LocationState using the active bundle for missing defaults."""
        return LocationState.from_dict(
            data,
            normalize_location_id=lambda loc_id, name: self.normalize_location_id(loc_id, location_name=name),
            defaults_for_location=self.location_state_defaults,
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

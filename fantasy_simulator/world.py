"""
world.py - World aggregate and compatibility exports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .event_models import WorldEventRecord
from .language.engine import LanguageEngine, fallback_evolution_targets
from .language.state import LanguageEvolutionRecord, LanguageRuntimeState
from .rule_override_resolution import (
    clone_default_event_impact_rules,
    clone_default_propagation_rules,
)
from .world_calendar_api import WorldCalendarMixin
from .world_event_api import WorldEventMixin
from .world_event_log_api import WorldEventLogMixin
from .world_language_api import WorldLanguageMixin
from .world_actor_api import WorldActorMixin
from .world_memory_api import WorldMemoryMixin
from .world_structure_api import WorldStructureMixin
from .world_topology_api import WorldTopologyMixin
from .world_bundle_transition import (
    apply_setting_bundle as apply_world_setting_bundle,
    set_setting_bundle_metadata,
    topology_signature,
)
from .world_location_references import LocationReferenceResolver
from .world_persistence import (
    hydrate_world_state,
    serialize_world_state,
)
from .world_route_graph import (
    ObservableRouteList,
    replace_routes,
)
from .world_event_index import EventHistoryIndex
from .world_state_runtime import (
    decay_world_state,
    propagate_world_state,
)
from .world_location_state import (
    LocationState,
    clamp_state as _clamp_state,
)
from .world_records import CalendarChangeRecord, MemorialRecord
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


def _clone_calendar(calendar: CalendarDefinition) -> CalendarDefinition:
    return CalendarDefinition.from_dict(calendar.to_dict())


def _clone_setting_bundle(bundle: SettingBundle) -> SettingBundle:
    return SettingBundle.from_dict(bundle.to_dict())


class World(
    WorldStructureMixin,
    WorldTopologyMixin,
    WorldActorMixin,
    WorldMemoryMixin,
    WorldLanguageMixin,
    WorldCalendarMixin,
    WorldEventMixin,
    WorldEventLogMixin,
):
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
        self._fallback_location_id_resolver = fallback_location_id
        self._location_state_defaults_resolver = get_location_state_defaults
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

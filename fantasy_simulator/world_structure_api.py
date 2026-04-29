"""Location-structure methods for :class:`fantasy_simulator.world.World`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

from .world_location_state import LocationState, location_state_from_site_seed
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
from .world_memory import rebuild_location_memorial_ids
from .world_reference_repair import (
    normalize_world_references_after_structure_change,
    repair_world_location_references,
)

if TYPE_CHECKING:
    from .adventure import AdventureRun
    from .character import Character
    from .content.setting_bundle import SettingBundle
    from .event_models import WorldEventRecord
    from .rumor import Rumor
    from .world_location_references import LocationReferenceResolver
    from .world_records import MemorialRecord


class WorldStructureMixin:
    if TYPE_CHECKING:
        _fallback_location_id_resolver: Callable[[str], str]
        _location_state_defaults_resolver: Callable[..., Dict[str, int]]
        _setting_bundle: SettingBundle
        _location_reference_resolver: LocationReferenceResolver
        width: int
        height: int
        grid: Dict[Tuple[int, int], LocationState]
        _location_name_index: Dict[str, LocationState]
        _location_id_index: Dict[str, LocationState]
        characters: List[Character]
        event_records: List[WorldEventRecord]
        rumors: List[Rumor]
        rumor_archive: List[Rumor]
        active_adventures: List[AdventureRun]
        completed_adventures: List[AdventureRun]
        memorials: Dict[str, MemorialRecord]

        def _build_terrain_from_grid(self, *, explicit_route_graph: Optional[bool] = None) -> None: ...
        def _location_state_from_dict(self, data: Dict[str, Any]) -> LocationState: ...
        def location_endonym(self, location_id: str, fallback: str = "") -> str: ...
        def _default_resident_location_id(self) -> str: ...
        def rebuild_char_index(self) -> None: ...
        def ensure_valid_character_locations(self) -> None: ...
        def rebuild_adventure_index(self) -> None: ...
        def rebuild_recent_event_ids(self) -> None: ...
        def rebuild_compatibility_event_log(self) -> None: ...

    def _fallback_location_id(self, name: str) -> str:
        """Resolve legacy fallback location IDs through this world instance."""
        return self._fallback_location_id_resolver(name)

    def _location_state_defaults(self, location_id: str, region_type: str, **kwargs: Any) -> Dict[str, int]:
        """Resolve location-state defaults through this world instance."""
        return self._location_state_defaults_resolver(location_id, region_type, **kwargs)

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

    def _build_default_map(self, previous_locations: Optional[List[LocationState]] = None) -> None:
        """Rebuild the world from the active setting bundle's site seeds."""
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
            fallback_resolver=self._fallback_location_id,
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
            fallback_resolver=self._fallback_location_id,
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
            fallback_resolver=self._fallback_location_id,
        )

    def _repair_location_references(self) -> None:
        """Repair persisted location references against the active world structure."""
        fallback_location_id_value = None
        if self._location_id_index:
            fallback_location_id_value = self._default_resident_location_id()
        repair_world_location_references(
            characters=self.characters,
            event_records=self.event_records,
            rumors=self.rumors,
            rumor_archive=self.rumor_archive,
            active_adventures=self.active_adventures,
            completed_adventures=self.completed_adventures,
            memorials=self.memorials,
            repair_location_reference=self._repair_location_reference,
            fallback_location_id=fallback_location_id_value,
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
        return self._location_state_defaults(
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

    def _grid_matches_bundle_seeds(self) -> bool:
        return grid_matches_site_seeds(
            site_seeds=self._setting_bundle.world_definition.site_seeds,
            grid_locations=self.grid.values(),
            width=self.width,
            height=self.height,
        )

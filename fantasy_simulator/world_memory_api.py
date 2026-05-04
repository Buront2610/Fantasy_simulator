"""Memory, dynamic-location, and lookup methods for :class:`fantasy_simulator.world.World`."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Container, Dict, List, Optional, Tuple

from .event_models import WorldEventRecord
from .event_rendering import render_event_record
from .ids import EventRecordId, FactionId, LocationId, RouteId
from .terrain import BIOME_TYPES
from .world_change import (
    MutateTerrainCellCommand,
    RenameLocationCommand,
    SetLocationControllingFactionCommand,
    SetRouteBlockedCommand,
    apply_world_change_set,
    build_location_occupation_change_set,
    build_location_rename_change_set,
    build_route_blocked_change_set,
    build_terrain_cell_mutation_change_set,
)
from .world_actor_index import (
    location_ids as location_ids_for_locations,
    location_name as location_name_for_id,
    location_names as location_names_for_locations,
)
from .world_dynamic_changes import (
    apply_controlling_faction,
    apply_location_rename,
    apply_route_blocked_state,
)
from .world_location_state import LocationState
from .world_memory import (
    add_alias as add_location_alias,
    add_live_trace as add_location_live_trace,
    link_memorial_record,
    memorials_for_location,
)
from .world_records import MemorialRecord

if TYPE_CHECKING:
    from .world_route_graph import RouteCollection


class WorldMemoryMixin:
    #: Maximum live traces kept per location (rolling window)
    MAX_LIVE_TRACES = 10
    #: Maximum aliases allowed per location
    MAX_ALIASES = 3

    if TYPE_CHECKING:
        year: int
        grid: Dict[Tuple[int, int], LocationState]
        routes: RouteCollection
        terrain_map: Any
        memorials: Dict[str, MemorialRecord]
        _location_id_index: Dict[str, LocationState]
        _location_name_index: Dict[str, LocationState]

        def get_travel_neighboring_locations(self, location_id: str) -> List[LocationState]: ...
        def record_event(self, record: WorldEventRecord) -> WorldEventRecord: ...

    def _record_world_change(
        self,
        *,
        kind: str,
        location_id: Optional[str],
        description: str,
        summary_key: str,
        render_params: Dict[str, Any],
        impacts: List[Dict[str, Any]],
        tags: Optional[List[str]] = None,
        year: Optional[int] = None,
        month: int = 1,
        day: int = 1,
        calendar_key: str = "",
    ) -> WorldEventRecord:
        record = WorldEventRecord(
            kind=kind,
            year=self.year if year is None else year,
            month=month,
            day=day,
            location_id=location_id,
            description=description,
            severity=2,
            visibility="public",
            calendar_key=calendar_key,
            summary_key=summary_key,
            render_params=render_params,
            tags=list(dict.fromkeys(["world_change", *(tags or [])])),
            impacts=impacts,
        )
        return self.record_event(record)

    def _route_location_name(self, location_id: str) -> str:
        location = self._location_id_index.get(location_id)
        if location is None:
            return location_id
        return location.canonical_name

    def _world_change_description(
        self,
        *,
        summary_key: str,
        render_params: Dict[str, Any],
        fallback_description: str,
    ) -> str:
        """Render a world-change description with a non-empty compatibility fallback."""
        description = render_event_record(
            WorldEventRecord(
                description=fallback_description,
                summary_key=summary_key,
                render_params=render_params,
            )
        )
        if not description:
            raise ValueError("world-change event description must not be empty")
        return description

    def _restore_location_rename_state(
        self,
        location_id: str,
        *,
        canonical_name: str,
        aliases: List[str],
    ) -> None:
        location = self._location_id_index[location_id]
        self._location_name_index.pop(location.canonical_name, None)
        location.canonical_name = canonical_name
        location.aliases = list(aliases)
        self._location_name_index[canonical_name] = location

    def add_live_trace(
        self,
        location_id: str,
        year: int,
        char_name: str,
        text: str,
    ) -> None:
        """Record a visitor trace at a location (design §E-2)."""
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
        """Create a permanent memorial at a location (design §E-2)."""
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
        """Append an alias to a location if not already present (design §E-2)."""
        add_location_alias(
            location_index=self._location_id_index,
            location_id=location_id,
            alias=alias,
            max_aliases=self.MAX_ALIASES,
        )

    def rename_location(self, location_id: str, new_name: str) -> str:
        """Rename a location and keep the previous name as an alias."""
        location = self._location_id_index[location_id]
        normalized_name = new_name.strip()
        existing = self._location_name_index.get(normalized_name)
        if existing is not None and existing is not location:
            raise ValueError(f"location name already exists: {normalized_name}")
        old_name = apply_location_rename(
            self._location_id_index,
            location_id=location_id,
            new_name=new_name,
            max_aliases=self.MAX_ALIASES,
        )
        if old_name != location.canonical_name:
            self._location_name_index.pop(old_name, None)
            self._location_name_index[location.canonical_name] = location
        return old_name

    def apply_location_rename_change(
        self,
        location_id: str,
        new_name: str,
        *,
        year: Optional[int] = None,
        month: int = 1,
        day: int = 1,
        calendar_key: str = "",
    ) -> WorldEventRecord | None:
        """Rename a location and record the canonical world-change event."""
        command = RenameLocationCommand(
            location_id=LocationId(location_id),
            new_name=new_name,
            year=self.year if year is None else year,
            month=month,
            day=day,
            calendar_key=calendar_key,
        )

        def _describe(summary_key: str, render_params: Dict[str, Any], fallback_description: str) -> str:
            return self._world_change_description(
                summary_key=summary_key,
                render_params=render_params,
                fallback_description=fallback_description,
            )

        change_set = build_location_rename_change_set(
            command,
            location_index=self._location_id_index,
            location_name_index=self._location_name_index,
            max_aliases=self.MAX_ALIASES,
            describe=_describe,
        )
        if change_set is None:
            return None
        stored_records = apply_world_change_set(
            change_set,
            routes=self.routes,
            record_event=self.record_event,
            location_index=self._location_id_index,
            location_name_index=self._location_name_index,
        )
        return stored_records[0] if stored_records else None

    def set_location_controlling_faction(self, location_id: str, faction_id: Optional[str]) -> Optional[str]:
        """Set the controlling faction for a location and return the previous value."""
        return apply_controlling_faction(
            self._location_id_index,
            location_id=location_id,
            faction_id=faction_id,
        )

    def apply_controlling_faction_change(
        self,
        location_id: str,
        faction_id: Optional[str],
        *,
        year: Optional[int] = None,
        month: int = 1,
        day: int = 1,
        calendar_key: str = "",
        known_faction_ids: Optional[Container[str]] = None,
    ) -> WorldEventRecord | None:
        """Set a location's controlling faction and record the canonical world-change event."""
        command = SetLocationControllingFactionCommand(
            location_id=LocationId(location_id),
            faction_id=None if faction_id is None else FactionId(faction_id),
            year=self.year if year is None else year,
            month=month,
            day=day,
            calendar_key=calendar_key,
        )

        def _describe(summary_key: str, render_params: Dict[str, Any], fallback_description: str) -> str:
            return self._world_change_description(
                summary_key=summary_key,
                render_params=render_params,
                fallback_description=fallback_description,
            )

        change_set = build_location_occupation_change_set(
            command,
            location_index=self._location_id_index,
            location_name=self._route_location_name,
            known_faction_ids=known_faction_ids,
            describe=_describe,
        )
        if change_set is None:
            return None
        stored_records = apply_world_change_set(
            change_set,
            routes=self.routes,
            record_event=self.record_event,
            location_index=self._location_id_index,
        )
        return stored_records[0] if stored_records else None

    def set_route_blocked(self, route_id: str, blocked: bool) -> bool:
        """Set route passability and return the previous blocked state."""
        return apply_route_blocked_state(self.routes, route_id=route_id, blocked=blocked)

    def apply_route_blocked_change(
        self,
        route_id: str,
        blocked: bool,
        *,
        year: Optional[int] = None,
        month: int = 1,
        day: int = 1,
        calendar_key: str = "",
    ) -> WorldEventRecord | None:
        """Set route passability and record the canonical world-change event."""
        command = SetRouteBlockedCommand(
            route_id=RouteId(route_id),
            blocked=blocked,
            year=self.year if year is None else year,
            month=month,
            day=day,
            calendar_key=calendar_key,
        )

        def _describe(summary_key: str, render_params: Dict[str, Any], fallback_description: str) -> str:
            return self._world_change_description(
                summary_key=summary_key,
                render_params=render_params,
                fallback_description=fallback_description,
            )

        change_set = build_route_blocked_change_set(
            command,
            routes=self.routes,
            location_ids=set(self.location_ids),
            location_name=self._route_location_name,
            describe=_describe,
        )
        if change_set is None:
            return None
        stored_records = apply_world_change_set(
            change_set,
            routes=self.routes,
            record_event=self.record_event,
        )
        return stored_records[0] if stored_records else None

    def apply_terrain_cell_change(
        self,
        x: int,
        y: int,
        *,
        biome: Optional[str] = None,
        elevation: Optional[int] = None,
        moisture: Optional[int] = None,
        temperature: Optional[int] = None,
        location_id: Optional[str] = None,
        year: Optional[int] = None,
        month: int = 1,
        day: int = 1,
        calendar_key: str = "",
        reason_key: str = "",
        cause_event_id: Optional[str] = None,
    ) -> WorldEventRecord | None:
        """Mutate one terrain cell and record the canonical world-change event."""
        location = self.grid.get((x, y))
        if location_id is not None:
            if location_id not in self._location_id_index:
                raise KeyError(location_id)
            if location is not None and location.id != location_id:
                raise ValueError(f"terrain cell ({x}, {y}) belongs to location {location.id}, not {location_id}")
        resolved_location_id = location_id if location_id is not None else None if location is None else location.id
        command = MutateTerrainCellCommand(
            x=x,
            y=y,
            biome=biome,
            elevation=elevation,
            moisture=moisture,
            temperature=temperature,
            location_id=None if resolved_location_id is None else LocationId(resolved_location_id),
            year=self.year if year is None else year,
            month=month,
            day=day,
            calendar_key=calendar_key,
            reason_key=reason_key,
            cause_event_id=None if cause_event_id is None else EventRecordId(cause_event_id),
        )

        def _describe(summary_key: str, render_params: Dict[str, Any], fallback_description: str) -> str:
            return self._world_change_description(
                summary_key=summary_key,
                render_params=render_params,
                fallback_description=fallback_description,
            )

        change_set = build_terrain_cell_mutation_change_set(
            command,
            terrain_map=self.terrain_map,
            allowed_biomes=BIOME_TYPES,
            describe=_describe,
        )
        if change_set is None:
            return None
        stored_records = apply_world_change_set(
            change_set,
            routes=self.routes,
            terrain_map=self.terrain_map,
            record_event=self.record_event,
        )
        return stored_records[0] if stored_records else None

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

    def get_neighboring_locations(self, location_id: str) -> List[LocationState]:
        """Compatibility alias for travel adjacency."""
        return self.get_travel_neighboring_locations(location_id)

    def random_location(self, exclude_dungeon: bool = False, rng: Any = random) -> LocationState:
        options = list(self.grid.values())
        if exclude_dungeon:
            options = [loc for loc in options if loc.region_type != "dungeon"]
        if not options:
            raise ValueError("World has no locations.")
        return rng.choice(options)

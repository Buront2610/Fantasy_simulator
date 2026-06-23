"""Memory and dynamic-location methods for :class:`fantasy_simulator.world.World`."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Container, Dict, Iterable, List, Optional, Tuple

from ..event_models import WorldEventRecord
from ..event_rendering import render_event_record
from ..ids import EventRecordId, FactionId, LocationId, RouteId
from ..world_dynamics import pressure as world_conflict_pressure
from ..world_arc import management as world_arcs
from ..world_change import (
    DeclareWarCommand,
    EndWarCommand,
    MutateTerrainCellCommand,
    RenameLocationCommand,
    SetLocationControllingFactionCommand,
    SetRouteBlockedCommand,
    apply_world_change_set,
    build_war_ended_change_set,
    build_war_declaration_change_set,
    build_location_occupation_change_set,
    build_location_rename_change_set,
    build_route_blocked_change_set,
    build_terrain_cell_mutation_change_set,
)
from ..world_dynamics.changes import (
    apply_controlling_faction,
    apply_location_rename,
    apply_route_blocked_state,
)
from ..world_location.state import LocationState
from ..world_location.lookup_api import WorldLocationLookupMixin
from . import (
    add_alias as add_location_alias,
    add_live_trace as add_location_live_trace,
    link_memorial_record,
    memorials_for_location,
)
from ..world_core.records import MemorialRecord

__all__ = ["WorldConflictMixin", "WorldLocationLookupMixin", "WorldMemoryMixin"]


def _setting_entry_key(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_").replace("'", "")


def _render_world_change_description(
    *,
    summary_key: str,
    render_params: Dict[str, Any],
    fallback_description: str,
    world_context: Any = None,
) -> str:
    record = WorldEventRecord(
        description=fallback_description,
        summary_key=summary_key,
        render_params=render_params,
    )
    try:
        description = render_event_record(record, world=world_context)
    except TypeError:
        description = render_event_record(record)
    if not description:
        raise ValueError("world-change event description must not be empty")
    return description


def _apply_caused_language_evolution(world: Any, record: WorldEventRecord, cause_key: str) -> None:
    apply_language_evolution = getattr(world, "apply_language_evolution_from_event", None)
    if callable(apply_language_evolution):
        apply_language_evolution(record, cause_key=cause_key)


class WorldConflictMixin:
    """Headless PR-K conflict/war API methods."""

    if TYPE_CHECKING:
        year: int
        routes: Any
        MAX_LIVE_TRACES: int
        _location_id_index: Dict[str, LocationState]

        def _known_faction_ids_from_setting_bundle(self) -> set[str] | None: ...

        def _world_change_description(
            self,
            *,
            summary_key: str,
            render_params: Dict[str, Any],
            fallback_description: str,
        ) -> str: ...

        @property
        def location_ids(self) -> List[str]: ...

        def world_change_event_recorder(self) -> Any: ...

    def apply_war_declaration(
        self,
        aggressor_faction_id: str,
        target_faction_id: str,
        *,
        location_ids: Iterable[str] = (),
        year: Optional[int] = None,
        month: int = 1,
        day: int = 1,
        calendar_key: str = "",
        cause_key: str = "",
        cause_event_id: Optional[str] = None,
        known_faction_ids: Optional[Container[str]] = None,
    ) -> WorldEventRecord:
        """Record a headless faction war declaration as a canonical world-change event."""
        command = DeclareWarCommand(
            aggressor_faction_id=FactionId(aggressor_faction_id),
            target_faction_id=FactionId(target_faction_id),
            location_ids=tuple(LocationId(location_id) for location_id in location_ids),
            year=self.year if year is None else year,
            month=month,
            day=day,
            calendar_key=calendar_key,
            cause_key=cause_key,
            cause_event_id=None if cause_event_id is None else EventRecordId(cause_event_id),
        )

        def _describe(summary_key: str, render_params: Dict[str, Any], fallback_description: str) -> str:
            return self._world_change_description(
                summary_key=summary_key,
                render_params=render_params,
                fallback_description=fallback_description,
            )

        resolved_known_faction_ids = known_faction_ids
        if resolved_known_faction_ids is None:
            resolved_known_faction_ids = self._known_faction_ids_from_setting_bundle()
        change_set = build_war_declaration_change_set(
            command,
            known_faction_ids=resolved_known_faction_ids or set(),
            location_ids=set(self.location_ids),
            describe=_describe,
        )
        stored_records = apply_world_change_set(
            change_set,
            routes=self.routes,
            record_event=self.world_change_event_recorder(),
        )
        record = stored_records[0]
        world_conflict_pressure.apply_war_pressure_to_locations(
            record,
            location_index=self._location_id_index,
            max_live_traces=self.MAX_LIVE_TRACES,
            world_context=self,
        )
        _apply_caused_language_evolution(self, record, cause_key or "war_declared")
        world_arcs.create_war_arc_from_record(self, record)
        return record

    def apply_war_ended(
        self,
        aggressor_faction_id: str,
        target_faction_id: str,
        *,
        location_ids: Iterable[str] = (),
        year: Optional[int] = None,
        month: int = 1,
        day: int = 1,
        calendar_key: str = "",
        cause_key: str = "",
        cause_event_id: Optional[str] = None,
        known_faction_ids: Optional[Container[str]] = None,
    ) -> WorldEventRecord:
        """Record a headless faction war ending as a canonical world-change event."""
        command = EndWarCommand(
            aggressor_faction_id=FactionId(aggressor_faction_id),
            target_faction_id=FactionId(target_faction_id),
            location_ids=tuple(LocationId(location_id) for location_id in location_ids),
            year=self.year if year is None else year,
            month=month,
            day=day,
            calendar_key=calendar_key,
            cause_key=cause_key,
            cause_event_id=None if cause_event_id is None else EventRecordId(cause_event_id),
        )

        def _describe(summary_key: str, render_params: Dict[str, Any], fallback_description: str) -> str:
            return self._world_change_description(
                summary_key=summary_key,
                render_params=render_params,
                fallback_description=fallback_description,
            )

        resolved_known_faction_ids = known_faction_ids
        if resolved_known_faction_ids is None:
            resolved_known_faction_ids = self._known_faction_ids_from_setting_bundle()
        change_set = build_war_ended_change_set(
            command,
            known_faction_ids=resolved_known_faction_ids or set(),
            location_ids=set(self.location_ids),
            describe=_describe,
        )
        stored_records = apply_world_change_set(
            change_set,
            routes=self.routes,
            record_event=self.world_change_event_recorder(),
        )
        record = stored_records[0]
        world_conflict_pressure.apply_war_pressure_to_locations(
            record,
            location_index=self._location_id_index,
            max_live_traces=self.MAX_LIVE_TRACES,
            world_context=self,
        )
        _apply_caused_language_evolution(self, record, cause_key or "war_ended")
        world_arcs.close_war_arc_from_record(self, record)
        return record


class WorldMemoryMixin:
    #: Maximum live traces kept per location (rolling window)
    MAX_LIVE_TRACES = 10
    #: Maximum aliases allowed per location
    MAX_ALIASES = 3

    if TYPE_CHECKING:
        year: int
        grid: Dict[Tuple[int, int], LocationState]
        routes: Any
        terrain_map: Any
        memorials: Dict[str, MemorialRecord]
        _location_id_index: Dict[str, LocationState]
        _location_name_index: Dict[str, LocationState]

        def get_travel_neighboring_locations(self, location_id: str) -> List[LocationState]: ...
        def record_event(self, record: WorldEventRecord) -> WorldEventRecord: ...
        def world_change_event_recorder(self) -> Any: ...

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
        return _render_world_change_description(
            summary_key=summary_key,
            render_params=render_params,
            fallback_description=fallback_description,
            world_context=self,
        )

    def _known_faction_ids_from_setting_bundle(self) -> set[str] | None:
        bundle = getattr(self, "_setting_bundle", None)
        if bundle is None:
            bundle = getattr(self, "setting_bundle", None)
        world_definition = getattr(bundle, "world_definition", None)
        faction_entries = getattr(world_definition, "faction_entries", None)
        if not callable(faction_entries):
            return None

        faction_ids: set[str] = set()
        for entry in faction_entries():
            key = getattr(entry, "key", "")
            display_name = getattr(entry, "display_name", "")
            if isinstance(key, str) and key:
                faction_ids.add(key)
            if isinstance(display_name, str) and display_name:
                faction_ids.add(display_name)
                faction_ids.add(_setting_entry_key(display_name))
        return faction_ids

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
        """Legacy mutation helper; prefer ``apply_location_rename_change`` for canonical history."""
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
        cause_event_id: Optional[str] = None,
    ) -> WorldEventRecord | None:
        """Rename a location and record the canonical world-change event."""
        command = RenameLocationCommand(
            location_id=LocationId(location_id),
            new_name=new_name,
            year=self.year if year is None else year,
            month=month,
            day=day,
            calendar_key=calendar_key,
            cause_event_id=None if cause_event_id is None else EventRecordId(cause_event_id),
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
            record_event=self.world_change_event_recorder(),
            location_index=self._location_id_index,
            location_name_index=self._location_name_index,
        )
        if not stored_records:
            return None
        record = stored_records[0]
        world_conflict_pressure.apply_rename_pressure_to_location(
            record,
            location_index=self._location_id_index,
            max_live_traces=self.MAX_LIVE_TRACES,
            world_context=self,
        )
        _apply_caused_language_evolution(self, record, "location_renamed")
        return record

    def set_location_controlling_faction(self, location_id: str, faction_id: Optional[str]) -> Optional[str]:
        """Legacy mutation helper; prefer ``apply_controlling_faction_change`` for canonical history."""
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
        allow_unknown_faction: bool = False,
        cause_event_id: Optional[str] = None,
    ) -> WorldEventRecord | None:
        """Set a location's controlling faction and record the canonical world-change event."""
        command = SetLocationControllingFactionCommand(
            location_id=LocationId(location_id),
            faction_id=None if faction_id is None else FactionId(faction_id),
            year=self.year if year is None else year,
            month=month,
            day=day,
            calendar_key=calendar_key,
            cause_event_id=None if cause_event_id is None else EventRecordId(cause_event_id),
        )

        def _describe(summary_key: str, render_params: Dict[str, Any], fallback_description: str) -> str:
            return self._world_change_description(
                summary_key=summary_key,
                render_params=render_params,
                fallback_description=fallback_description,
            )

        resolved_known_faction_ids = (
            None
            if allow_unknown_faction
            else known_faction_ids if known_faction_ids is not None else self._known_faction_ids_from_setting_bundle()
        )
        change_set = build_location_occupation_change_set(
            command,
            location_index=self._location_id_index,
            location_name=self._route_location_name,
            known_faction_ids=resolved_known_faction_ids,
            describe=_describe,
        )
        if change_set is None:
            return None
        stored_records = apply_world_change_set(
            change_set,
            routes=self.routes,
            record_event=self.world_change_event_recorder(),
            location_index=self._location_id_index,
        )
        if not stored_records:
            return None
        record = stored_records[0]
        world_conflict_pressure.apply_occupation_pressure_to_location(
            record,
            location_index=self._location_id_index,
            max_live_traces=self.MAX_LIVE_TRACES,
            world_context=self,
        )
        _apply_caused_language_evolution(self, record, "location_control_changed")
        return record

    def set_route_blocked(self, route_id: str, blocked: bool) -> bool:
        """Legacy mutation helper; prefer ``apply_route_blocked_change`` for canonical history."""
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
        cause_event_id: Optional[str] = None,
    ) -> WorldEventRecord | None:
        """Set route passability and record the canonical world-change event."""
        command = SetRouteBlockedCommand(
            route_id=RouteId(route_id),
            blocked=blocked,
            year=self.year if year is None else year,
            month=month,
            day=day,
            calendar_key=calendar_key,
            cause_event_id=None if cause_event_id is None else EventRecordId(cause_event_id),
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
            location_ids=set(self._location_id_index),
            location_name=self._route_location_name,
            describe=_describe,
        )
        if change_set is None:
            return None
        stored_records = apply_world_change_set(
            change_set,
            routes=self.routes,
            record_event=self.world_change_event_recorder(),
        )
        if not stored_records:
            return None
        record = stored_records[0]
        world_conflict_pressure.apply_route_pressure_to_locations(
            record,
            location_index=self._location_id_index,
            max_live_traces=self.MAX_LIVE_TRACES,
            world_context=self,
        )
        _apply_caused_language_evolution(self, record, "route_blocked" if blocked else "route_reopened")
        return record

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
        from ..terrain import BIOME_TYPES

        location = self.grid.get((x, y))
        if location_id is not None:
            if location_id not in self._location_id_index:
                raise KeyError(location_id)
            if location is None:
                raise ValueError(f"terrain cell ({x}, {y}) is not associated with location {location_id}")
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
            record_event=self.world_change_event_recorder(),
        )
        if not stored_records:
            return None
        record = stored_records[0]
        world_conflict_pressure.apply_terrain_pressure_to_location(
            record,
            location_index=self._location_id_index,
            max_live_traces=self.MAX_LIVE_TRACES,
            world_context=self,
        )
        _apply_caused_language_evolution(self, record, reason_key or "terrain_cell_mutated")
        return record

    def get_memorials_for_location(self, location_id: str) -> List[MemorialRecord]:
        """Return all ``MemorialRecord`` objects associated with a location."""
        return list(
            memorials_for_location(
                location_index=self._location_id_index,
                memorials=self.memorials,
                location_id=location_id,
            )
        )

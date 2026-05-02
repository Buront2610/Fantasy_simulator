"""Memory, dynamic-location, and lookup methods for :class:`fantasy_simulator.world.World`."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .event_models import LOCATION_TAG_PREFIX, WorldEventRecord
from .event_rendering import render_event_record
from .world_actor_index import (
    location_ids as location_ids_for_locations,
    location_name as location_name_for_id,
    location_names as location_names_for_locations,
)
from .world_dynamic_changes import (
    apply_controlling_faction,
    apply_location_rename,
    apply_route_blocked_state,
    route_by_id,
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
        location = self._location_id_index[location_id]
        rollback_name = location.canonical_name
        rollback_aliases = list(location.aliases)
        old_name = self.rename_location(location_id, new_name)
        if old_name == location.canonical_name:
            return None
        render_params = {
            "location_id": location_id,
            "old_name": old_name,
            "new_name": location.canonical_name,
        }
        summary_key = "events.location_renamed.summary"
        try:
            return self._record_world_change(
                kind="location_renamed",
                location_id=location_id,
                description=self._world_change_description(
                    summary_key=summary_key,
                    render_params=render_params,
                    fallback_description=f"{old_name} was renamed {location.canonical_name}.",
                ),
                summary_key=summary_key,
                render_params=render_params,
                impacts=[
                    {
                        "target_type": "location",
                        "target_id": location_id,
                        "attribute": "canonical_name",
                        "old_value": old_name,
                        "new_value": location.canonical_name,
                    }
                ],
                year=year,
                month=month,
                day=day,
                calendar_key=calendar_key,
            )
        except Exception:
            self._restore_location_rename_state(
                location_id,
                canonical_name=rollback_name,
                aliases=rollback_aliases,
            )
            raise

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
    ) -> WorldEventRecord | None:
        """Set a location's controlling faction and record the canonical world-change event."""
        old_faction_id = self.set_location_controlling_faction(location_id, faction_id)
        location = self._location_id_index[location_id]
        new_faction_id = location.controlling_faction_id
        if old_faction_id == new_faction_id:
            return None
        render_params = {
            "location": location.canonical_name,
            "location_id": location_id,
            "old_faction_id": old_faction_id,
            "new_faction_id": new_faction_id,
        }
        old_faction_fallback = old_faction_id or "none"
        new_faction_fallback = new_faction_id or "none"
        summary_key = "events.location_faction_changed.summary"
        try:
            return self._record_world_change(
                kind="location_faction_changed",
                location_id=location_id,
                description=self._world_change_description(
                    summary_key=summary_key,
                    render_params=render_params,
                    fallback_description=(
                        f"{location.canonical_name} changed controlling faction from "
                        f"{old_faction_fallback} to {new_faction_fallback}."
                    ),
                ),
                summary_key=summary_key,
                render_params=render_params,
                impacts=[
                    {
                        "target_type": "location",
                        "target_id": location_id,
                        "attribute": "controlling_faction_id",
                        "old_value": old_faction_id,
                        "new_value": new_faction_id,
                    }
                ],
                year=year,
                month=month,
                day=day,
                calendar_key=calendar_key,
            )
        except Exception:
            self.set_location_controlling_faction(location_id, old_faction_id)
            raise

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
        route = route_by_id(self.routes, route_id=route_id)
        old_blocked = self.set_route_blocked(route_id, blocked)
        new_blocked = bool(route.blocked)
        if old_blocked == new_blocked:
            return None
        route_kind = "route_blocked" if new_blocked else "route_reopened"
        summary_key = f"events.{route_kind}.summary"
        render_params = {
            "route_id": route_id,
            "from_location_id": route.from_site_id,
            "to_location_id": route.to_site_id,
            "endpoint_location_ids": [route.from_site_id, route.to_site_id],
            "from_location": self._route_location_name(route.from_site_id),
            "to_location": self._route_location_name(route.to_site_id),
        }
        route_verb = "blocked" if new_blocked else "reopened"
        try:
            return self._record_world_change(
                kind=route_kind,
                location_id=route.from_site_id,
                description=self._world_change_description(
                    summary_key=summary_key,
                    render_params=render_params,
                    fallback_description=(
                        f"The route from {render_params['from_location']} to "
                        f"{render_params['to_location']} was {route_verb}."
                    ),
                ),
                summary_key=summary_key,
                render_params=render_params,
                tags=[
                    f"{LOCATION_TAG_PREFIX}{route.from_site_id}",
                    f"{LOCATION_TAG_PREFIX}{route.to_site_id}",
                ],
                impacts=[
                    {
                        "target_type": "route",
                        "target_id": route_id,
                        "attribute": "blocked",
                        "old_value": old_blocked,
                        "new_value": new_blocked,
                    }
                ],
                year=year,
                month=month,
                day=day,
                calendar_key=calendar_key,
            )
        except Exception:
            self.set_route_blocked(route_id, old_blocked)
            raise

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

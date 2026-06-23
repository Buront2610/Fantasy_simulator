"""Location lookup helpers for :class:`fantasy_simulator.world.World`."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from ..world_actor.index import (
    location_ids as location_ids_for_locations,
    location_name as location_name_for_id,
    location_names as location_names_for_locations,
)

if TYPE_CHECKING:
    from .state import LocationState


class WorldLocationLookupMixin:
    if TYPE_CHECKING:
        grid: Dict[Tuple[int, int], LocationState]
        _location_id_index: Dict[str, LocationState]
        _location_name_index: Dict[str, LocationState]

        def get_travel_neighboring_locations(self, location_id: str) -> List[LocationState]: ...

    @property
    def location_names(self) -> List[str]:
        return location_names_for_locations(self.grid.values())

    @property
    def location_ids(self) -> List[str]:
        return location_ids_for_locations(self.grid.values())

    def get_location_by_name(self, name: str) -> LocationState | None:
        return self._location_name_index.get(name)

    def get_location_by_id(self, location_id: str) -> LocationState | None:
        return self._location_id_index.get(location_id)

    def find_location_by_id_or_name(self, value: str) -> LocationState | None:
        """Return a location matching an ID or canonical name, case-insensitively."""
        normalized = value.strip().lower()
        if not normalized:
            return None
        for location in self._location_id_index.values():
            if location.id.lower() == normalized or location.canonical_name.lower() == normalized:
                return location
        return None

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

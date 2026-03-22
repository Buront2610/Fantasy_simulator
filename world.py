"""
world.py - World map, Location dataclass, and the World class.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from i18n import tr
from world_data import DEFAULT_LOCATIONS, WORLD_LORE

if TYPE_CHECKING:
    from adventure import AdventureRun
    from character import Character


@dataclass
class Location:
    """A single cell on the world grid."""

    id: str
    name: str
    description: str
    region_type: str
    x: int
    y: int

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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "region_type": self.region_type,
            "x": self.x,
            "y": self.y,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Location":
        from world_data import NAME_TO_LOCATION_ID, fallback_location_id
        loc_id = data.get("id")
        if not loc_id:
            name = data.get("name", "")
            loc_id = NAME_TO_LOCATION_ID.get(name, fallback_location_id(name))
        return cls(
            id=loc_id,
            name=data["name"],
            description=data["description"],
            region_type=data["region_type"],
            x=data["x"],
            y=data["y"],
        )


class World:
    """Represents the entire game world."""

    def __init__(
        self,
        name: str = "Aethoria",
        lore: str = WORLD_LORE,
        width: int = 5,
        height: int = 5,
        year: int = 1000,
    ) -> None:
        self.name: str = name
        self.lore: str = lore
        self.width: int = width
        self.height: int = height
        self.year: int = year
        self.grid: Dict[Tuple[int, int], Location] = {}
        self.characters: List[Character] = []
        self._char_index: Dict[str, Character] = {}
        self._adventure_index: Dict[str, AdventureRun] = {}
        self._location_name_index: Dict[str, Location] = {}
        self._location_id_index: Dict[str, Location] = {}
        self.event_log: List[str] = []
        self.active_adventures: List[AdventureRun] = []
        self.completed_adventures: List[AdventureRun] = []
        self._build_default_map()

    def _build_default_map(self) -> None:
        for entry in DEFAULT_LOCATIONS:
            loc_id, name, desc, rtype, gx, gy = entry
            loc = Location(id=loc_id, name=name, description=desc, region_type=rtype, x=gx, y=gy)
            self.grid[(gx, gy)] = loc
            self._location_name_index[name] = loc
            self._location_id_index[loc_id] = loc

    def add_character(self, character: Character, rng: Any = random) -> None:
        if character.location_id not in self._location_id_index:
            options = [loc.id for loc in self.grid.values() if loc.region_type != "dungeon"]
            fallback = list(self._location_id_index.keys())
            if options:
                character.location_id = rng.choice(options)
            elif fallback:
                character.location_id = fallback[0]
            else:
                raise ValueError("Cannot add character: world has no locations.")
        if character.char_id in self._char_index:
            raise ValueError(
                f"Duplicate character ID: {character.char_id!r} "
                f"(existing: {self._char_index[character.char_id].name!r}, "
                f"new: {character.name!r})"
            )
        self.characters.append(character)
        self._char_index[character.char_id] = character

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

    @property
    def location_names(self) -> List[str]:
        return sorted(loc.name for loc in self.grid.values())

    @property
    def location_ids(self) -> List[str]:
        return sorted(loc.id for loc in self.grid.values())

    def get_location_by_name(self, name: str) -> Optional[Location]:
        return self._location_name_index.get(name)

    def get_location_by_id(self, location_id: str) -> Optional[Location]:
        return self._location_id_index.get(location_id)

    def location_name(self, location_id: str) -> str:
        loc = self._location_id_index.get(location_id)
        if loc is not None:
            return loc.name
        return location_id

    def get_characters_at_location(self, location_id: str) -> List[Character]:
        return [c for c in self.characters if c.location_id == location_id and c.alive]

    def get_neighboring_locations(self, location_id: str) -> List[Location]:
        source = self._location_id_index.get(location_id)
        if source is None:
            return []
        neighbours: List[Location] = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            coord = (source.x + dx, source.y + dy)
            if coord in self.grid:
                neighbours.append(self.grid[coord])
        return neighbours

    def random_location(self, exclude_dungeon: bool = False, rng: Any = random) -> Location:
        options = list(self.grid.values())
        if exclude_dungeon:
            options = [loc for loc in options if loc.region_type != "dungeon"]
        return rng.choice(options)

    def advance_time(self, years: int = 1) -> None:
        self.year += years

    MAX_EVENT_LOG = 2000

    def log_event(self, event_text: str) -> None:
        prefix = tr("event_log_prefix", year=self.year)
        self.event_log.append(f"{prefix} {event_text}")
        if len(self.event_log) > self.MAX_EVENT_LOG:
            self.event_log = self.event_log[-self.MAX_EVENT_LOG:]

    def render_map(self, highlight_location: Optional[str] = None) -> str:
        """Return a stable ASCII grid of the world map."""
        cell_width = 16
        total_width = self.width * (cell_width + 1) + 1
        border = "  +" + "-" * (total_width - 2) + "+"
        lines: List[str] = [
            border,
            f"  | {tr('map_title')}: {self.name} | {tr('map_year')}: {self.year}".ljust(total_width) + "|",
            border,
        ]

        for y in range(self.height):
            row_names: List[str] = []
            row_types: List[str] = []
            row_pops: List[str] = []
            for x in range(self.width):
                loc = self.grid.get((x, y))
                if loc is None:
                    row_names.append(" ? ???".ljust(cell_width))
                    row_types.append("".ljust(cell_width))
                    row_pops.append("".ljust(cell_width))
                    continue

                is_highlight = (
                    highlight_location is not None
                    and (loc.id == highlight_location or loc.name == highlight_location)
                )
                icon = "*" if is_highlight else loc.icon
                population = len(self.get_characters_at_location(loc.id))
                row_names.append(f" {icon} {loc.name[:cell_width - 4]}".ljust(cell_width))
                row_types.append(f" {tr('map_type')}: {loc.region_type[:cell_width - 8]}".ljust(cell_width))
                row_pops.append(f" {tr('map_population')}: {population}".ljust(cell_width))

            lines.append("  |" + "|".join(row_names) + "|")
            lines.append("  |" + "|".join(row_types) + "|")
            lines.append("  |" + "|".join(row_pops) + "|")
            lines.append(border)

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "lore": self.lore,
            "width": self.width,
            "height": self.height,
            "year": self.year,
            "grid": [loc.to_dict() for loc in self.grid.values()],
            "event_log": self.event_log,
            "active_adventures": [run.to_dict() for run in self.active_adventures],
            "completed_adventures": [run.to_dict() for run in self.completed_adventures],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "World":
        from adventure import AdventureRun

        world = cls(
            name=data["name"],
            lore=data.get("lore", WORLD_LORE),
            width=data.get("width", 5),
            height=data.get("height", 5),
            year=data.get("year", 1000),
        )
        world.grid = {}
        world._location_name_index = {}
        world._location_id_index = {}
        for loc_data in data.get("grid", []):
            loc = Location.from_dict(loc_data)
            world.grid[(loc.x, loc.y)] = loc
            world._location_name_index[loc.name] = loc
            world._location_id_index[loc.id] = loc
        world.event_log = data.get("event_log", [])
        world.active_adventures = [
            AdventureRun.from_dict(run) for run in data.get("active_adventures", [])
        ]
        world.completed_adventures = [
            AdventureRun.from_dict(run) for run in data.get("completed_adventures", [])
        ]
        world._adventure_index = {
            run.adventure_id: run
            for run in world.active_adventures + world.completed_adventures
        }
        return world

    def __repr__(self) -> str:  # pragma: no cover
        return f"World(name={self.name!r}, year={self.year}, characters={len(self.characters)})"

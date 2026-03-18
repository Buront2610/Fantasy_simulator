"""
world.py - World map, Location dataclass, and the World class.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from i18n import tr
from world_data import DEFAULT_LOCATIONS, WORLD_LORE


@dataclass
class Location:
    """A single cell on the world grid."""

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
            "name": self.name,
            "description": self.description,
            "region_type": self.region_type,
            "x": self.x,
            "y": self.y,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Location":
        return cls(
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
        self.characters: List[Any] = []
        self.event_log: List[str] = []
        self.active_adventures: List[Any] = []
        self.completed_adventures: List[Any] = []
        self._build_default_map()

    def _build_default_map(self) -> None:
        for entry in DEFAULT_LOCATIONS:
            name, desc, rtype, gx, gy = entry
            loc = Location(name=name, description=desc, region_type=rtype, x=gx, y=gy)
            self.grid[(gx, gy)] = loc

    def add_character(self, character: Any, rng: Any = random) -> None:
        if character.location not in self.location_names:
            options = [loc.name for loc in self.grid.values() if loc.region_type != "dungeon"]
            character.location = rng.choice(options) if options else self.location_names[0]
        self.characters.append(character)

    def remove_character(self, char_id: str) -> None:
        self.characters = [c for c in self.characters if c.char_id != char_id]

    def get_character_by_id(self, char_id: str) -> Optional[Any]:
        for c in self.characters:
            if c.char_id == char_id:
                return c
        return None

    def get_adventure_by_id(self, adventure_id: str) -> Optional[Any]:
        for run in self.active_adventures + self.completed_adventures:
            if run.adventure_id == adventure_id:
                return run
        return None

    def add_adventure(self, run: Any) -> None:
        self.active_adventures.append(run)

    def complete_adventure(self, adventure_id: str) -> None:
        remaining: List[Any] = []
        for run in self.active_adventures:
            if run.adventure_id == adventure_id:
                self.completed_adventures.append(run)
            else:
                remaining.append(run)
        self.active_adventures = remaining

    @property
    def location_names(self) -> List[str]:
        return sorted(loc.name for loc in self.grid.values())

    def get_location_by_name(self, name: str) -> Optional[Location]:
        for loc in self.grid.values():
            if loc.name == name:
                return loc
        return None

    def get_characters_at_location(self, location_name: str) -> List[Any]:
        return [c for c in self.characters if c.location == location_name and c.alive]

    def get_neighboring_locations(self, location_name: str) -> List[Location]:
        source = self.get_location_by_name(location_name)
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
            options = [l for l in options if l.region_type != "dungeon"]
        return rng.choice(options)

    def advance_time(self, years: int = 1) -> None:
        self.year += years

    def log_event(self, event_text: str) -> None:
        prefix = tr("event_log_prefix", year=self.year)
        self.event_log.append(f"{prefix} {event_text}")

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

                icon = "*" if loc.name == highlight_location else loc.icon
                population = len(self.get_characters_at_location(loc.name))
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
        for loc_data in data.get("grid", []):
            loc = Location.from_dict(loc_data)
            world.grid[(loc.x, loc.y)] = loc
        world.event_log = data.get("event_log", [])
        world.active_adventures = [
            AdventureRun.from_dict(run) for run in data.get("active_adventures", [])
        ]
        world.completed_adventures = [
            AdventureRun.from_dict(run) for run in data.get("completed_adventures", [])
        ]
        return world

    def __repr__(self) -> str:  # pragma: no cover
        return f"World(name={self.name!r}, year={self.year}, characters={len(self.characters)})"

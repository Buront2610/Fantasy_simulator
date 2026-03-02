"""
world.py - World map, Location dataclass, and the World class.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from world_data import DEFAULT_LOCATIONS, WORLD_LORE


# ---------------------------------------------------------------------------
# Location
# ---------------------------------------------------------------------------

@dataclass
class Location:
    """A single cell on the world grid.

    Attributes
    ----------
    name : str
        Human-readable place name.
    description : str
        Flavour text.
    region_type : str
        One of: city, village, forest, dungeon, mountain, plains, sea.
    x : int
        Grid column (0-based, west → east).
    y : int
        Grid row (0-based, north → south).
    """

    name: str
    description: str
    region_type: str
    x: int
    y: int

    # Icons used in ASCII map rendering
    _ICONS: Dict[str, str] = field(default_factory=dict, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        self._ICONS = {
            "city":     "🏙",
            "village":  "🏘",
            "forest":   "🌲",
            "dungeon":  "💀",
            "mountain": "⛰",
            "plains":   "🌾",
            "sea":      "🌊",
        }

    @property
    def icon(self) -> str:
        """Single-character icon for the ASCII map (fallback to '?')."""
        icons_ascii = {
            "city":     "C",
            "village":  "V",
            "forest":   "F",
            "dungeon":  "D",
            "mountain": "M",
            "plains":   "P",
            "sea":      "~",
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


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------

class World:
    """Represents the entire game world.

    Attributes
    ----------
    name : str
        World / continent name.
    lore : str
        Narrative background text.
    width : int
        Grid width (columns).
    height : int
        Grid height (rows).
    grid : dict[(x, y), Location]
        All locations keyed by grid coordinate.
    characters : list[Character]
        All characters currently in the world (imported lazily to avoid
        circular imports — type hint is kept as Any).
    year : int
        Current in-world year.
    event_log : list[str]
        Global log of every notable world event.
    """

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
        self.characters: List[Any] = []  # List[Character] — avoids circular import
        self.event_log: List[str] = []
        self._build_default_map()

    # ------------------------------------------------------------------
    # Map construction
    # ------------------------------------------------------------------

    def _build_default_map(self) -> None:
        """Populate the grid with the predefined location data."""
        for entry in DEFAULT_LOCATIONS:
            name, desc, rtype, gx, gy = entry
            loc = Location(name=name, description=desc, region_type=rtype, x=gx, y=gy)
            self.grid[(gx, gy)] = loc

    # ------------------------------------------------------------------
    # Character management
    # ------------------------------------------------------------------

    def add_character(self, character: Any) -> None:
        """Add a character to the world (and assign a starting location if unset)."""
        if character.location not in self.location_names:
            # Pick a random non-dungeon location
            options = [
                loc.name for loc in self.grid.values()
                if loc.region_type != "dungeon"
            ]
            character.location = random.choice(options) if options else self.location_names[0]
        self.characters.append(character)

    def remove_character(self, char_id: str) -> None:
        """Remove a character by ID (e.g. on death)."""
        self.characters = [c for c in self.characters if c.char_id != char_id]

    def get_character_by_id(self, char_id: str) -> Optional[Any]:
        """Return the character with the matching ID, or None."""
        for c in self.characters:
            if c.char_id == char_id:
                return c
        return None

    # ------------------------------------------------------------------
    # Location queries
    # ------------------------------------------------------------------

    @property
    def location_names(self) -> List[str]:
        """Sorted list of all location names."""
        return sorted(loc.name for loc in self.grid.values())

    def get_location_by_name(self, name: str) -> Optional[Location]:
        """Return the Location with the given name, or None."""
        for loc in self.grid.values():
            if loc.name == name:
                return loc
        return None

    def get_characters_at_location(self, location_name: str) -> List[Any]:
        """Return all *alive* characters currently at *location_name*."""
        return [c for c in self.characters if c.location == location_name and c.alive]

    def get_neighboring_locations(self, location_name: str) -> List[Location]:
        """Return locations adjacent (4-directional) to *location_name*.

        Diagonal neighbours are not included.
        """
        source = self.get_location_by_name(location_name)
        if source is None:
            return []
        neighbours: List[Location] = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            coord = (source.x + dx, source.y + dy)
            if coord in self.grid:
                neighbours.append(self.grid[coord])
        return neighbours

    def random_location(self, exclude_dungeon: bool = False) -> Location:
        """Return a random location from the grid."""
        options = list(self.grid.values())
        if exclude_dungeon:
            options = [l for l in options if l.region_type != "dungeon"]
        return random.choice(options)

    # ------------------------------------------------------------------
    # Time
    # ------------------------------------------------------------------

    def advance_time(self, years: int = 1) -> None:
        """Advance the world clock by *years*."""
        self.year += years

    def log_event(self, event_text: str) -> None:
        """Append a timestamped entry to the global event log."""
        self.event_log.append(f"[Year {self.year}] {event_text}")

    # ------------------------------------------------------------------
    # ASCII map rendering
    # ------------------------------------------------------------------

    def render_map(self, highlight_location: Optional[str] = None) -> str:
        """Return a pretty ASCII grid of the world map.

        Parameters
        ----------
        highlight_location
            If given, that cell is marked with '*' instead of its normal icon.
        """
        lines: List[str] = []
        col_width = 14  # characters per cell (name truncated)

        # Header
        lines.append(f"  ╔{'═' * (col_width * self.width + self.width - 1)}╗")
        lines.append(f"  ║  🗺  {self.name.upper()} — Year {self.year}".ljust(col_width * self.width + 2) + "║")
        lines.append(f"  ╠{'═' * (col_width * self.width + self.width - 1)}╣")

        for y in range(self.height):
            name_row: List[str] = []
            type_row: List[str] = []
            pop_row:  List[str] = []
            for x in range(self.width):
                loc = self.grid.get((x, y))
                if loc is None:
                    name_row.append("  ???  ".ljust(col_width))
                    type_row.append("".ljust(col_width))
                    pop_row.append("".ljust(col_width))
                    continue
                is_hl = loc.name == highlight_location
                icon = "*" if is_hl else loc.icon
                pop = len(self.get_characters_at_location(loc.name))
                trunc_name = loc.name[:col_width - 4]
                name_row.append(f" {icon} {trunc_name}".ljust(col_width))
                type_row.append(f"  [{loc.region_type[:8]}]".ljust(col_width))
                pop_row.append(f"  pop:{pop:>3}".ljust(col_width))

            sep = "│"
            lines.append(f"  ║{sep.join(name_row)}║")
            lines.append(f"  ║{sep.join(type_row)}║")
            lines.append(f"  ║{sep.join(pop_row)}║")
            if y < self.height - 1:
                lines.append(f"  ╠{'─' * (col_width * self.width + self.width - 1)}╣")

        lines.append(f"  ╚{'═' * (col_width * self.width + self.width - 1)}╝")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise world state (without characters — serialise them separately)."""
        return {
            "name": self.name,
            "lore": self.lore,
            "width": self.width,
            "height": self.height,
            "year": self.year,
            "grid": [loc.to_dict() for loc in self.grid.values()],
            "event_log": self.event_log,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "World":
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
        return world

    def __repr__(self) -> str:  # pragma: no cover
        return f"World(name={self.name!r}, year={self.year}, characters={len(self.characters)})"

"""
world.py - World map, LocationState dataclass, and the World class.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from i18n import tr
from world_data import (
    DEFAULT_LOCATIONS,
    NAME_TO_LOCATION_ID,
    WORLD_LORE,
    fallback_location_id,
    get_location_state_defaults,
)

if TYPE_CHECKING:
    from adventure import AdventureRun
    from character import Character
    from events import WorldEventRecord


def _clamp_state(value: int) -> int:
    return max(0, min(100, int(value)))


PROSPERITY_LABELS = [
    (0, 20, "ruined"),
    (20, 45, "declining"),
    (45, 75, "stable"),
    (75, 101, "thriving"),
]

SAFETY_LABELS = [
    (0, 20, "lawless"),
    (20, 45, "dangerous"),
    (45, 75, "tense"),
    (75, 101, "peaceful"),
]

MOOD_LABELS = [
    (0, 20, "grieving"),
    (20, 45, "anxious"),
    (45, 75, "calm"),
    (75, 101, "festive"),
]


def _band_name(value: int, bands: List[Tuple[int, int, str]]) -> str:
    for lo, hi, name in bands:
        if lo <= value < hi:
            return name
    return bands[-1][2]


def _traffic_indicator(value: int) -> str:
    if value >= 70:
        return "+++"
    if value >= 40:
        return "++"
    if value > 0:
        return "+"
    return "-"


@dataclass
class LocationState:
    """A single cell on the world grid with persistent state."""

    id: str
    canonical_name: str
    description: str
    region_type: str
    x: int
    y: int
    prosperity: int
    safety: int
    mood: int
    danger: int
    traffic: int
    rumor_heat: int
    road_condition: int
    visited: bool = False
    controlling_faction_id: Optional[str] = None
    recent_event_ids: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    memorial_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        for field_name in (
            "prosperity",
            "safety",
            "mood",
            "danger",
            "traffic",
            "rumor_heat",
            "road_condition",
        ):
            setattr(self, field_name, _clamp_state(getattr(self, field_name)))

    @property
    def name(self) -> str:
        """Compatibility alias for older callers."""
        return self.canonical_name

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

    @property
    def prosperity_label(self) -> str:
        band = _band_name(self.prosperity, PROSPERITY_LABELS)
        return tr(f"location_prosperity_{band}")

    @property
    def safety_label(self) -> str:
        band = _band_name(self.safety, SAFETY_LABELS)
        return tr(f"location_safety_{band}")

    @property
    def mood_label(self) -> str:
        band = _band_name(self.mood, MOOD_LABELS)
        return tr(f"location_mood_{band}")

    @property
    def traffic_indicator(self) -> str:
        return _traffic_indicator(self.traffic)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "canonical_name": self.canonical_name,
            "name": self.canonical_name,
            "description": self.description,
            "region_type": self.region_type,
            "x": self.x,
            "y": self.y,
            "prosperity": self.prosperity,
            "safety": self.safety,
            "mood": self.mood,
            "danger": self.danger,
            "traffic": self.traffic,
            "rumor_heat": self.rumor_heat,
            "road_condition": self.road_condition,
            "visited": self.visited,
            "controlling_faction_id": self.controlling_faction_id,
            "recent_event_ids": list(self.recent_event_ids),
            "aliases": list(self.aliases),
            "memorial_ids": list(self.memorial_ids),
        }

    @classmethod
    def from_default_entry(cls, entry: Tuple[str, str, str, str, int, int]) -> "LocationState":
        loc_id, canonical_name, description, region_type, x, y = entry
        defaults = get_location_state_defaults(loc_id, region_type)
        return cls(
            id=loc_id,
            canonical_name=canonical_name,
            description=description,
            region_type=region_type,
            x=x,
            y=y,
            **defaults,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocationState":
        loc_id = data.get("id")
        if not loc_id:
            name = data.get("canonical_name") or data.get("name", "")
            loc_id = NAME_TO_LOCATION_ID.get(name, fallback_location_id(name))
        canonical_name = data.get("canonical_name") or data.get("name", "")
        region_type = data["region_type"]
        defaults = get_location_state_defaults(loc_id, region_type)
        return cls(
            id=loc_id,
            canonical_name=canonical_name,
            description=data["description"],
            region_type=region_type,
            x=data["x"],
            y=data["y"],
            prosperity=data.get("prosperity", defaults["prosperity"]),
            safety=data.get("safety", defaults["safety"]),
            mood=data.get("mood", defaults["mood"]),
            danger=data.get("danger", defaults["danger"]),
            traffic=data.get("traffic", defaults["traffic"]),
            rumor_heat=data.get("rumor_heat", defaults["rumor_heat"]),
            road_condition=data.get("road_condition", defaults["road_condition"]),
            visited=data.get("visited", False),
            controlling_faction_id=data.get("controlling_faction_id"),
            recent_event_ids=list(data.get("recent_event_ids", [])),
            aliases=list(data.get("aliases", [])),
            memorial_ids=list(data.get("memorial_ids", [])),
        )


# Backward-compatible alias for older imports.
Location = LocationState


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
        self.grid: Dict[Tuple[int, int], LocationState] = {}
        self.characters: List[Character] = []
        self._char_index: Dict[str, Character] = {}
        self._adventure_index: Dict[str, AdventureRun] = {}
        self._location_name_index: Dict[str, LocationState] = {}
        self._location_id_index: Dict[str, LocationState] = {}
        self.event_log: List[str] = []
        self.event_records: List[WorldEventRecord] = []
        self.active_adventures: List[AdventureRun] = []
        self.completed_adventures: List[AdventureRun] = []
        self._build_default_map()

    def _register_location(self, loc: LocationState) -> None:
        self.grid[(loc.x, loc.y)] = loc
        self._location_name_index[loc.canonical_name] = loc
        self._location_id_index[loc.id] = loc

    def _build_default_map(self) -> None:
        for entry in DEFAULT_LOCATIONS:
            self._register_location(LocationState.from_default_entry(entry))

    def _default_resident_location_id(self) -> str:
        if "loc_aethoria_capital" in self._location_id_index:
            return "loc_aethoria_capital"
        non_dungeons = sorted(
            loc.id for loc in self.grid.values() if loc.region_type != "dungeon"
        )
        if non_dungeons:
            return non_dungeons[0]
        all_locations = sorted(self._location_id_index)
        if all_locations:
            return all_locations[0]
        raise ValueError("World has no locations.")

    def ensure_valid_character_locations(self) -> None:
        """Repair invalid location references after loading legacy data."""
        fallback = self._default_resident_location_id()
        for character in self.characters:
            if character.location_id not in self._location_id_index:
                character.location_id = fallback

    def add_character(self, character: Character, rng: Any = random) -> None:
        if character.location_id not in self._location_id_index:
            options = [loc.id for loc in self.grid.values() if loc.region_type != "dungeon"]
            if options:
                character.location_id = rng.choice(options)
            else:
                character.location_id = self._default_resident_location_id()
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
        return sorted(loc.canonical_name for loc in self.grid.values())

    @property
    def location_ids(self) -> List[str]:
        return sorted(loc.id for loc in self.grid.values())

    def get_location_by_name(self, name: str) -> Optional[LocationState]:
        return self._location_name_index.get(name)

    def get_location_by_id(self, location_id: str) -> Optional[LocationState]:
        return self._location_id_index.get(location_id)

    def location_name(self, location_id: str) -> str:
        loc = self._location_id_index.get(location_id)
        if loc is not None:
            return loc.canonical_name
        lid = location_id
        if lid.startswith("loc_"):
            lid = lid[4:]
        return lid.replace("_", " ").title()

    def get_characters_at_location(self, location_id: str) -> List[Character]:
        return [c for c in self.characters if c.location_id == location_id and c.alive]

    def get_neighboring_locations(self, location_id: str) -> List[LocationState]:
        source = self._location_id_index.get(location_id)
        if source is None:
            return []
        neighbours: List[LocationState] = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            coord = (source.x + dx, source.y + dy)
            if coord in self.grid:
                neighbours.append(self.grid[coord])
        return neighbours

    def random_location(self, exclude_dungeon: bool = False, rng: Any = random) -> LocationState:
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

    MAX_EVENT_RECORDS = 5000

    def record_event(self, record: WorldEventRecord) -> None:
        """Store a structured event record."""
        if record.location_id not in self._location_id_index:
            record.location_id = None
        self.event_records.append(record)
        if record.location_id is not None:
            location = self._location_id_index[record.location_id]
            location.recent_event_ids.append(record.record_id)
            location.recent_event_ids = location.recent_event_ids[-12:]
        if len(self.event_records) > self.MAX_EVENT_RECORDS:
            self.event_records = self.event_records[-self.MAX_EVENT_RECORDS:]
            surviving_ids = {item.record_id for item in self.event_records}
            for location in self.grid.values():
                if location.recent_event_ids:
                    location.recent_event_ids = [
                        record_id for record_id in location.recent_event_ids
                        if record_id in surviving_ids
                    ]

    def get_events_by_location(self, location_id: str) -> List[WorldEventRecord]:
        """Return all event records for a specific location."""
        return [r for r in self.event_records if r.location_id == location_id]

    def get_events_by_actor(self, char_id: str) -> List[WorldEventRecord]:
        """Return all event records involving a specific character."""
        return [
            r for r in self.event_records
            if r.primary_actor_id == char_id or char_id in r.secondary_actor_ids
        ]

    def get_events_by_year(self, year: int) -> List[WorldEventRecord]:
        """Return all event records for a specific year."""
        return [r for r in self.event_records if r.year == year]

    def render_map(self, highlight_location: Optional[str] = None) -> str:
        """Return a stable ASCII grid of the world map."""
        cell_width = 20
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
            row_safety: List[str] = []
            row_state: List[str] = []
            row_pops: List[str] = []
            for x in range(self.width):
                loc = self.grid.get((x, y))
                if loc is None:
                    blank = "".ljust(cell_width)
                    row_names.append(f" ? {'???':<{cell_width - 3}}")
                    row_types.append(blank)
                    row_safety.append(blank)
                    row_state.append(blank)
                    row_pops.append(blank)
                    continue

                is_highlight = (
                    highlight_location is not None
                    and (loc.id == highlight_location or loc.canonical_name == highlight_location)
                )
                icon = "*" if is_highlight else loc.icon
                population = len(self.get_characters_at_location(loc.id))
                row_names.append(f" {icon} {loc.canonical_name[:cell_width - 4]}".ljust(cell_width))
                row_types.append(f" {tr('map_type')}: {loc.region_type}".ljust(cell_width))
                row_safety.append(f" {tr('map_safety')}: {loc.safety_label}".ljust(cell_width))
                row_state.append(
                    f" {tr('map_danger')}: {loc.danger:>3} {tr('map_traffic')}: {loc.traffic_indicator}".ljust(
                        cell_width
                    )
                )
                row_pops.append(f" {tr('map_population')}: {population}".ljust(cell_width))

            lines.append("  |" + "|".join(row_names) + "|")
            lines.append("  |" + "|".join(row_types) + "|")
            lines.append("  |" + "|".join(row_safety) + "|")
            lines.append("  |" + "|".join(row_state) + "|")
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
            "event_records": [r.to_dict() for r in self.event_records],
            "active_adventures": [run.to_dict() for run in self.active_adventures],
            "completed_adventures": [run.to_dict() for run in self.completed_adventures],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "World":
        from adventure import AdventureRun
        from events import WorldEventRecord

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
            world._register_location(LocationState.from_dict(loc_data))
        world.event_log = data.get("event_log", [])
        world.event_records = [
            WorldEventRecord.from_dict(r) for r in data.get("event_records", [])
        ]
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

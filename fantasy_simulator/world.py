"""
world.py - World map, LocationState dataclass, and the World class.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .i18n import tr
from .content.world_data import (
    DEFAULT_LOCATIONS,
    NAME_TO_LOCATION_ID,
    WORLD_LORE,
    fallback_location_id,
    get_location_state_defaults,
)
from .terrain import (
    RouteEdge,
    Site,
    TerrainMap,
    build_default_terrain,
)

if TYPE_CHECKING:
    from .adventure import AdventureRun
    from .character import Character
    from .events import WorldEventRecord
    from .rumor import Rumor


def _clamp_state(value: int) -> int:
    return max(0, min(100, int(value)))


@dataclass
class MemorialRecord:
    """A permanent memorial created when a character dies at a location.

    PR-F: world memory.  Memorial IDs are stored in
    ``LocationState.memorial_ids``; full records live in
    ``World.memorials`` keyed by ``memorial_id``.
    """

    memorial_id: str
    character_id: str
    character_name: str
    location_id: str
    year: int
    cause: str    # e.g. "adventure_death", "battle_fatal"
    epitaph: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memorial_id": self.memorial_id,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "location_id": self.location_id,
            "year": self.year,
            "cause": self.cause,
            "epitaph": self.epitaph,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemorialRecord":
        return cls(
            memorial_id=data["memorial_id"],
            character_id=data["character_id"],
            character_name=data["character_name"],
            location_id=data["location_id"],
            year=data["year"],
            cause=data["cause"],
            epitaph=data["epitaph"],
        )


# ------------------------------------------------------------------
# Propagation rules (design doc §5.6)
# ------------------------------------------------------------------

PROPAGATION_RULES: Dict[str, Dict[str, Any]] = {
    "danger": {
        "decay": 0.30,
        "cap": 15,
        "min_source": 40,
    },
    "traffic": {
        "decay": 0.20,
        "cap": 10,
        "min_source": 35,
    },
    "mood_from_ruin": {
        "source_threshold": 20,
        "neighbor_penalty": 5,
        "max_neighbors": 4,
    },
    "road_damage_from_danger": {
        "danger_threshold": 70,
        "road_penalty": 8,
    },
}

# Event kind -> location state impact (design doc §5.5)
_EVENT_IMPACT: Dict[str, Dict[str, int]] = {
    "death":              {"safety": -3, "mood": -5, "rumor_heat": +10},
    "battle_fatal":       {"safety": -5, "mood": -8, "danger": +5, "rumor_heat": +15},
    "battle":             {"safety": -2, "mood": -3, "danger": +3, "rumor_heat": +5},
    "discovery":          {"rumor_heat": +5, "traffic": +3},
    "marriage":           {"mood": +3},
    "adventure_death":    {"danger": +5, "mood": -5, "rumor_heat": +10},
    "adventure_discovery": {"rumor_heat": +5, "traffic": +2, "prosperity": +2},
    "adventure_started":  {"traffic": +2},
    "adventure_returned": {"mood": +2, "traffic": +1},
    "journey":            {"traffic": +1},
    "injury_recovery":    {"mood": +1},
    "condition_worsened": {"mood": -2, "rumor_heat": +3},
    "dying_rescued":      {"mood": +3, "rumor_heat": +5},
}


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
    live_traces: List[Dict[str, Any]] = field(default_factory=list)

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
            "live_traces": list(self.live_traces),
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
            live_traces=list(data.get("live_traces", [])),
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
        *,
        _skip_defaults: bool = False,
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
        # Transitional event storage during the Phase 1 -> Phase 2 migration:
        # - event_records is the canonical structured history for new features.
        # - event_log is a CLI-facing formatted buffer kept for compatibility.
        self.event_log: List[str] = []
        self.event_records: List[WorldEventRecord] = []
        self.rumors: List[Rumor] = []
        self.rumor_archive: List[Rumor] = []
        self.active_adventures: List[AdventureRun] = []
        self.completed_adventures: List[AdventureRun] = []
        # PR-F: keyed by memorial_id
        self.memorials: Dict[str, MemorialRecord] = {}
        # PR-G: terrain / site / route layers
        self.terrain_map: Optional[TerrainMap] = None
        self.sites: List[Site] = []
        self.routes: List[RouteEdge] = []
        self._site_index: Dict[str, Site] = {}
        if not _skip_defaults:
            self._build_default_map()

    def _register_location(self, loc: LocationState) -> None:
        existing_at_coord = self.grid.get((loc.x, loc.y))
        if existing_at_coord is not None and existing_at_coord is not loc:
            self._location_name_index.pop(existing_at_coord.canonical_name, None)
            self._location_id_index.pop(existing_at_coord.id, None)

        existing_by_id = self._location_id_index.get(loc.id)
        if existing_by_id is not None and existing_by_id is not loc:
            self.grid.pop((existing_by_id.x, existing_by_id.y), None)
            self._location_name_index.pop(existing_by_id.canonical_name, None)

        self.grid[(loc.x, loc.y)] = loc
        self._location_name_index[loc.canonical_name] = loc
        self._location_id_index[loc.id] = loc

    def _build_default_map(self) -> None:
        """Populate the world with default Aethoria locations and terrain.

        Only locations whose ``(x, y)`` fall within ``self.width x
        self.height`` are registered.  This means ``World(width=3,
        height=3)`` will contain only the locations that fit.
        """
        for entry in DEFAULT_LOCATIONS:
            _loc_id, _name, _desc, _rtype, x, y = entry
            if 0 <= x < self.width and 0 <= y < self.height:
                self._register_location(LocationState.from_default_entry(entry))
        self._build_terrain_from_grid()

    def _build_terrain_from_grid(self) -> None:
        """Generate terrain, sites, and routes from the current grid.

        Derives terrain biome from each ``LocationState.region_type``
        and creates provisional routes between adjacent sites.
        """
        # Collect current grid as pseudo-location tuples for the builder
        location_tuples = [
            (loc.id, loc.canonical_name, loc.description,
             loc.region_type, loc.x, loc.y)
            for loc in self.grid.values()
        ]
        tmap, sites, routes = build_default_terrain(
            width=self.width,
            height=self.height,
            locations=location_tuples,
        )
        self.terrain_map = tmap
        self.sites = sites
        self.routes = routes
        self._rebuild_site_index()

    def _rebuild_site_index(self) -> None:
        """Rebuild the site lookup index keyed by location_id."""
        self._site_index = {s.location_id: s for s in self.sites}

    def get_site_by_id(self, location_id: str) -> Optional[Site]:
        """Return the Site record for a location, or None."""
        return self._site_index.get(location_id)

    def get_routes_for_site(self, location_id: str) -> List[RouteEdge]:
        """Return all routes connected to a site."""
        return [r for r in self.routes if r.connects(location_id)]

    def get_connected_site_ids(self, location_id: str) -> List[str]:
        """Return location_ids of sites reachable via routes from a site."""
        result: List[str] = []
        for route in self.routes:
            other = route.other_end(location_id)
            if other is not None and not route.blocked:
                result.append(other)
        return result

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

    def mark_location_visited(self, location_id: str) -> None:
        """Mark a location as visited when it is meaningfully occupied or reached."""
        location = self._location_id_index.get(location_id)
        if location is not None:
            location.visited = True

    def ensure_valid_character_locations(self) -> None:
        """Repair invalid location references after loading legacy data."""
        fallback = self._default_resident_location_id()
        for character in self.characters:
            if character.location_id not in self._location_id_index:
                character.location_id = fallback
            self.mark_location_visited(character.location_id)

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
        self.mark_location_visited(character.location_id)

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

    def rebuild_adventure_index(self) -> None:
        """Rebuild the adventure ID index after loading or external mutations."""
        index: Dict[str, AdventureRun] = {}
        for run in self.active_adventures + self.completed_adventures:
            if run.adventure_id in index:
                raise ValueError(f"Duplicate adventure ID during rebuild: {run.adventure_id!r}")
            index[run.adventure_id] = run
        self._adventure_index = index

    def rebuild_recent_event_ids(self) -> None:
        """Rebuild derived per-location recent_event_ids from structured event records."""
        for location in self.grid.values():
            location.recent_event_ids = []

        for record in self.event_records:
            if record.location_id not in self._location_id_index:
                record.location_id = None
                continue
            self._location_id_index[record.location_id].recent_event_ids.append(record.record_id)

        for location in self.grid.values():
            location.recent_event_ids = location.recent_event_ids[-12:]

    def normalize_after_load(self) -> None:
        """Rebuild derived indexes and repair invariants after deserialization."""
        self.rebuild_char_index()
        self.ensure_valid_character_locations()
        self.rebuild_adventure_index()
        self.rebuild_recent_event_ids()

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

    # ------------------------------------------------------------------
    # PR-F: World memory helpers
    # ------------------------------------------------------------------

    #: Maximum live traces kept per location (rolling window)
    MAX_LIVE_TRACES = 10
    #: Maximum aliases allowed per location
    MAX_ALIASES = 3

    def add_live_trace(
        self,
        location_id: str,
        year: int,
        char_name: str,
        text: str,
    ) -> None:
        """Record a visitor trace at a location (design §E-2).

        Traces are ephemeral footprints capped at ``MAX_LIVE_TRACES``
        per location.  Oldest entries are dropped when the cap is reached.
        """
        loc = self._location_id_index.get(location_id)
        if loc is None:
            return
        loc.live_traces.append({"year": year, "char_name": char_name, "text": text})
        if len(loc.live_traces) > self.MAX_LIVE_TRACES:
            loc.live_traces = loc.live_traces[-self.MAX_LIVE_TRACES:]

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
        """Create a permanent memorial at a location (design §E-2).

        The memorial is stored in ``self.memorials`` and its ID is appended
        to ``LocationState.memorial_ids`` for quick lookup.
        """
        record = MemorialRecord(
            memorial_id=memorial_id,
            character_id=character_id,
            character_name=character_name,
            location_id=location_id,
            year=year,
            cause=cause,
            epitaph=epitaph,
        )
        self.memorials[memorial_id] = record
        loc = self._location_id_index.get(location_id)
        if loc is not None and memorial_id not in loc.memorial_ids:
            loc.memorial_ids.append(memorial_id)

    def add_alias(self, location_id: str, alias: str) -> None:
        """Append an alias to a location if not already present (design §E-2).

        Capped at ``MAX_ALIASES`` per location; duplicate strings are
        silently ignored.
        """
        loc = self._location_id_index.get(location_id)
        if loc is None:
            return
        if alias not in loc.aliases and len(loc.aliases) < self.MAX_ALIASES:
            loc.aliases.append(alias)

    def get_memorials_for_location(self, location_id: str) -> List[MemorialRecord]:
        """Return all ``MemorialRecord`` objects associated with a location."""
        loc = self._location_id_index.get(location_id)
        if loc is None:
            return []
        return [
            self.memorials[mid]
            for mid in loc.memorial_ids
            if mid in self.memorials
        ]

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

    @staticmethod
    def get_season(month: int) -> str:
        """Return season name for a given month (1-12)."""
        if month in (12, 1, 2):
            return "winter"
        if month in (3, 4, 5):
            return "spring"
        if month in (6, 7, 8):
            return "summer"
        return "autumn"

    def advance_time(self, years: int = 1) -> None:
        self.year += years

    MAX_EVENT_LOG = 2000

    def log_event(self, event_text: str, *, month: Optional[int] = None) -> None:
        """Append a formatted compatibility log entry for legacy CLI consumers.

        This buffer is intentionally separate from ``event_records`` during the
        Phase 1 -> Phase 2 migration. New gameplay/report features should treat
        ``event_records`` as the canonical history and view this method as a
        presentation-layer compatibility path.

        When *month* is provided, the prefix includes month information so that
        the player-visible log reflects monthly causality introduced in PR-B.
        """
        if month is not None:
            prefix = tr("event_log_prefix_month", year=self.year, month=month)
        else:
            prefix = tr("event_log_prefix", year=self.year)
        self.event_log.append(f"{prefix} {event_text}")
        if len(self.event_log) > self.MAX_EVENT_LOG:
            self.event_log = self.event_log[-self.MAX_EVENT_LOG:]

    MAX_EVENT_RECORDS = 5000

    def record_event(self, record: WorldEventRecord) -> None:
        """Store a structured event record in the canonical world history."""
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

    def apply_event_impact(self, kind: str, location_id: Optional[str]) -> List[Dict[str, Any]]:
        """Update location state quantities based on an event kind (design §5.5).

        Returns a list of impact dicts recording the state changes applied,
        each containing ``target_type``, ``target_id``, ``attribute``,
        ``old_value``, ``new_value``, and ``delta``.
        """
        impacts: List[Dict[str, Any]] = []
        if location_id is None:
            return impacts
        loc = self._location_id_index.get(location_id)
        if loc is None:
            return impacts
        deltas = _EVENT_IMPACT.get(kind, {})
        for attr, delta in deltas.items():
            old = getattr(loc, attr, None)
            if old is not None:
                new_val = _clamp_state(old + delta)
                setattr(loc, attr, new_val)
                impacts.append({
                    "target_type": "location",
                    "target_id": location_id,
                    "attribute": attr,
                    "old_value": old,
                    "new_value": new_val,
                    "delta": new_val - old,
                })
        return impacts

    # Annual decay rate: each year, event-driven deviations from baseline
    # decay by this fraction toward the region-type default, preventing
    # runaway accumulation of danger/traffic/mood changes over long runs.
    # Set high enough to counterbalance propagation from neighboring
    # high-danger/traffic locations (e.g. dungeons, mountains).
    _STATE_DECAY_RATE = 0.30

    def _decay_toward_baseline(self) -> None:
        """Pull volatile state fields back toward their region-type defaults.

        Without this, additive event impacts and neighbor propagation cause
        states to drift monotonically toward 0 or 100 over long simulations.
        """
        for loc in self.grid.values():
            defaults = get_location_state_defaults(loc.id, loc.region_type)
            for attr in ("danger", "traffic", "mood", "safety", "rumor_heat"):
                current = getattr(loc, attr)
                baseline = defaults[attr]
                diff = baseline - current
                if diff == 0:
                    continue
                # Move a fraction of the distance back toward baseline
                adjustment = int(diff * self._STATE_DECAY_RATE)
                if adjustment == 0:
                    adjustment = 1 if diff > 0 else -1
                setattr(loc, attr, _clamp_state(current + adjustment))

    def propagate_state(self) -> None:
        """Propagate location state to neighbors (design §5.6).

        Called once per simulated year after events are processed.
        Applies natural decay toward baseline first, then propagation,
        so that state quantities stabilise over time instead of
        accumulating unboundedly.
        """
        # Decay toward baseline before propagation
        self._decay_toward_baseline()

        pending_changes: List[tuple] = []

        for loc in self.grid.values():
            neighbours = self.get_neighboring_locations(loc.id)
            if not neighbours:
                continue

            # Danger propagation — only to neighbors whose danger is
            # below the source's current level (prevents runaway upward drift)
            rule = PROPAGATION_RULES["danger"]
            if loc.danger >= rule["min_source"]:
                spread = min(int(loc.danger * rule["decay"]), rule["cap"])
                for n in neighbours:
                    if n.danger < loc.danger:
                        capped = min(spread, loc.danger - n.danger)
                        pending_changes.append((n.id, "danger", capped))

            # Traffic propagation — same directional cap
            rule = PROPAGATION_RULES["traffic"]
            if loc.traffic >= rule["min_source"]:
                spread = min(int(loc.traffic * rule["decay"]), rule["cap"])
                for n in neighbours:
                    if n.traffic < loc.traffic:
                        capped = min(spread, loc.traffic - n.traffic)
                        pending_changes.append((n.id, "traffic", capped))

            # Mood penalty from ruined neighbors
            rule = PROPAGATION_RULES["mood_from_ruin"]
            if loc.prosperity < rule["source_threshold"]:
                for n in neighbours[:rule["max_neighbors"]]:
                    pending_changes.append((n.id, "mood", -rule["neighbor_penalty"]))

            # Road damage from high danger
            rule = PROPAGATION_RULES["road_damage_from_danger"]
            if loc.danger >= rule["danger_threshold"]:
                pending_changes.append((loc.id, "road_condition", -rule["road_penalty"]))

        for loc_id, attr, delta in pending_changes:
            loc = self._location_id_index.get(loc_id)
            if loc is not None:
                old = getattr(loc, attr)
                setattr(loc, attr, _clamp_state(old + delta))

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
        result: Dict[str, Any] = {
            "name": self.name,
            "lore": self.lore,
            "width": self.width,
            "height": self.height,
            "year": self.year,
            "grid": [loc.to_dict() for loc in self.grid.values()],
            "event_log": self.event_log,
            "event_records": [r.to_dict() for r in self.event_records],
            "rumors": [r.to_dict() for r in self.rumors],
            "rumor_archive": [r.to_dict() for r in self.rumor_archive],
            "active_adventures": [run.to_dict() for run in self.active_adventures],
            "completed_adventures": [run.to_dict() for run in self.completed_adventures],
            "memorials": {k: v.to_dict() for k, v in self.memorials.items()},
        }
        # PR-G: persist terrain/site/route layers
        if self.terrain_map is not None:
            result["terrain_map"] = self.terrain_map.to_dict()
        if self.sites:
            result["sites"] = [s.to_dict() for s in self.sites]
        if self.routes:
            result["routes"] = [r.to_dict() for r in self.routes]
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "World":
        """Restore a World from a serialised dict.

        Uses ``_skip_defaults=True`` so that no default Aethoria map
        is generated.  The world is populated entirely from the saved
        data, avoiding contamination from the default 5×5 locations.

        If the saved grid has fewer locations than the declared
        ``width × height`` (e.g. a partial legacy save), missing
        default locations are *not* injected — the data migration
        chain (``persistence.migrations``) is responsible for filling
        in any missing structure before this method is called.

        If no terrain data is present in *data*, terrain/site/routes
        are derived from the loaded grid via ``_build_terrain_from_grid()``.
        """
        from .adventure import AdventureRun
        from .events import WorldEventRecord
        from .rumor import Rumor

        world = cls(
            name=data["name"],
            lore=data.get("lore", WORLD_LORE),
            width=data.get("width", 5),
            height=data.get("height", 5),
            year=data.get("year", 1000),
            _skip_defaults=True,
        )
        for loc_data in data.get("grid", []):
            world._register_location(LocationState.from_dict(loc_data))
        world.event_log = data.get("event_log", [])
        world.event_records = [
            WorldEventRecord.from_dict(r) for r in data.get("event_records", [])
        ]
        world.rumors = [
            Rumor.from_dict(r) for r in data.get("rumors", [])
        ]
        world.rumor_archive = [
            Rumor.from_dict(r) for r in data.get("rumor_archive", [])
        ]
        world.active_adventures = [
            AdventureRun.from_dict(run) for run in data.get("active_adventures", [])
        ]
        world.completed_adventures = [
            AdventureRun.from_dict(run) for run in data.get("completed_adventures", [])
        ]
        world.memorials = {
            k: MemorialRecord.from_dict(v) for k, v in data.get("memorials", {}).items()
        }

        # PR-G: restore terrain/site/route layers if present;
        # otherwise derive from loaded grid.
        if "terrain_map" in data:
            world.terrain_map = TerrainMap.from_dict(data["terrain_map"])
            world.sites = [Site.from_dict(s) for s in data.get("sites", [])]
            world.routes = [RouteEdge.from_dict(r) for r in data.get("routes", [])]
            world._rebuild_site_index()
        else:
            world._build_terrain_from_grid()

        world.normalize_after_load()
        return world

    def __repr__(self) -> str:  # pragma: no cover
        return f"World(name={self.name!r}, year={self.year}, characters={len(self.characters)})"

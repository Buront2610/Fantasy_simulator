"""
location.py - LocationState dataclass for the Fantasy Simulator.

Replaces the old Location dataclass with a richer model that tracks internal
numeric state (prosperity, safety, etc.) separately from display labels.
See design doc §5.2 for the full specification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# ID generation
# ---------------------------------------------------------------------------


def make_location_id(canonical_name: str) -> str:
    """Generate a stable, lowercase string ID from a canonical location name.

    Examples:
        "Aethoria Capital" -> "aethoria_capital"
        "The Grey Pass"    -> "the_grey_pass"
        "Goblin Warrens"   -> "goblin_warrens"
    """
    slug = canonical_name.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


# ---------------------------------------------------------------------------
# Region defaults for migration
# ---------------------------------------------------------------------------

LOCATION_DEFAULTS: Dict[str, Dict[str, int]] = {
    "capital":  {"prosperity": 85, "safety": 80, "mood": 65, "danger": 15, "traffic": 90,
                 "rumor_heat": 60, "road_condition": 85},
    "city":     {"prosperity": 70, "safety": 65, "mood": 55, "danger": 25, "traffic": 70,
                 "rumor_heat": 45, "road_condition": 75},
    "village":  {"prosperity": 50, "safety": 55, "mood": 55, "danger": 30, "traffic": 35,
                 "rumor_heat": 20, "road_condition": 55},
    "forest":   {"prosperity": 10, "safety": 30, "mood": 40, "danger": 55, "traffic": 15,
                 "rumor_heat": 10, "road_condition": 35},
    "mountain": {"prosperity": 5,  "safety": 25, "mood": 35, "danger": 65, "traffic": 10,
                 "rumor_heat": 10, "road_condition": 30},
    "dungeon":  {"prosperity": 0,  "safety": 10, "mood": 20, "danger": 80, "traffic": 5,
                 "rumor_heat": 35, "road_condition": 20},
    "plains":   {"prosperity": 35, "safety": 45, "mood": 50, "danger": 35, "traffic": 30,
                 "rumor_heat": 15, "road_condition": 60},
    "sea":      {"prosperity": 0,  "safety": 20, "mood": 40, "danger": 60, "traffic": 25,
                 "rumor_heat": 20, "road_condition": 0},
}

# ---------------------------------------------------------------------------
# Display label thresholds (§5.3)
# ---------------------------------------------------------------------------

_PROSPERITY_LABELS: List[Tuple[int, int, str]] = [
    (0, 20, "ruined"), (20, 45, "declining"), (45, 75, "stable"), (75, 101, "thriving"),
]
_SAFETY_LABELS: List[Tuple[int, int, str]] = [
    (0, 20, "lawless"), (20, 45, "dangerous"), (45, 75, "tense"), (75, 101, "peaceful"),
]
_MOOD_LABELS: List[Tuple[int, int, str]] = [
    (0, 20, "grieving"), (20, 45, "anxious"), (45, 75, "calm"), (75, 101, "festive"),
]


def _derive_label(value: int, thresholds: List[Tuple[int, int, str]]) -> str:
    for lo, hi, label in thresholds:
        if lo <= value < hi:
            return label
    return thresholds[-1][2]


# ---------------------------------------------------------------------------
# LocationState dataclass
# ---------------------------------------------------------------------------

_ICONS: Dict[str, str] = {
    "city": "C",
    "village": "V",
    "forest": "F",
    "dungeon": "D",
    "mountain": "M",
    "plains": "P",
    "sea": "~",
}


@dataclass
class LocationState:
    """A single cell on the world grid with full state tracking.

    Attributes
    ----------
    id : str
        Stable string identifier derived from canonical_name.
    canonical_name : str
        The official display name of the location.
    description : str
        Flavour description.
    region_type : str
        One of: city, village, forest, dungeon, mountain, plains, sea.
    x, y : int
        Grid coordinates.
    prosperity, safety, mood, danger, traffic, rumor_heat, road_condition : int
        Internal state values clamped to [0, 100].
    visited : bool
        Whether any character has visited this location.
    controlling_faction_id : Optional[str]
        ID of the faction currently in control, if any.
    aliases : List[str]
        Alternative names / nicknames for this location.
    memorial_ids : List[str]
        IDs of memorials located here.
    recent_event_ids : List[str]
        IDs of recent events that occurred here.
    """

    id: str
    canonical_name: str
    description: str
    region_type: str
    x: int
    y: int

    prosperity: int = 50
    safety: int = 50
    mood: int = 50
    danger: int = 50
    traffic: int = 50
    rumor_heat: int = 30
    road_condition: int = 50

    visited: bool = False
    controlling_faction_id: Optional[str] = None
    aliases: List[str] = field(default_factory=list)
    memorial_ids: List[str] = field(default_factory=list)
    recent_event_ids: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.prosperity = self._clamp(self.prosperity)
        self.safety = self._clamp(self.safety)
        self.mood = self._clamp(self.mood)
        self.danger = self._clamp(self.danger)
        self.traffic = self._clamp(self.traffic)
        self.rumor_heat = self._clamp(self.rumor_heat)
        self.road_condition = self._clamp(self.road_condition)

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clamp(value: int) -> int:
        return max(0, min(100, value))

    @staticmethod
    def make_id(canonical_name: str) -> str:
        """Generate a stable ID from a canonical location name."""
        return make_location_id(canonical_name)

    # ------------------------------------------------------------------
    # Backward-compatible properties
    # ------------------------------------------------------------------

    @property
    def name(self) -> str:
        """Backward-compatible alias for canonical_name."""
        return self.canonical_name

    @property
    def icon(self) -> str:
        return _ICONS.get(self.region_type, "?")

    # ------------------------------------------------------------------
    # Derived display labels (§5.3)
    # ------------------------------------------------------------------

    @property
    def prosperity_label(self) -> str:
        return _derive_label(self.prosperity, _PROSPERITY_LABELS)

    @property
    def safety_label(self) -> str:
        return _derive_label(self.safety, _SAFETY_LABELS)

    @property
    def mood_label(self) -> str:
        return _derive_label(self.mood, _MOOD_LABELS)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "canonical_name": self.canonical_name,
            "name": self.canonical_name,  # backward-compat key
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
            "aliases": list(self.aliases),
            "memorial_ids": list(self.memorial_ids),
            "recent_event_ids": list(self.recent_event_ids),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LocationState":
        """Deserialise a LocationState.

        Accepts both new-format dicts (with ``id``/``canonical_name``) and
        old-format dicts (with only ``name``) for backward compatibility.
        """
        canonical_name = data.get("canonical_name") or data.get("name", "Unknown")
        loc_id = data.get("id") or make_location_id(canonical_name)
        return cls(
            id=loc_id,
            canonical_name=canonical_name,
            description=data.get("description", ""),
            region_type=data.get("region_type", "plains"),
            x=data["x"],
            y=data["y"],
            prosperity=data.get("prosperity", 50),
            safety=data.get("safety", 50),
            mood=data.get("mood", 50),
            danger=data.get("danger", 50),
            traffic=data.get("traffic", 50),
            rumor_heat=data.get("rumor_heat", 30),
            road_condition=data.get("road_condition", 50),
            visited=data.get("visited", False),
            controlling_faction_id=data.get("controlling_faction_id"),
            aliases=list(data.get("aliases", [])),
            memorial_ids=list(data.get("memorial_ids", [])),
            recent_event_ids=list(data.get("recent_event_ids", [])),
        )

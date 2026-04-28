"""Persistent location-state model for the world aggregate."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Protocol, Tuple

from .i18n import tr


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


def clamp_state(value: int) -> int:
    return max(0, min(100, int(value)))


def string_list_payload(payload: Any, *, field_name: str) -> List[str]:
    if payload is None:
        return []
    if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
        raise ValueError(f"{field_name} must be a list of strings")
    return list(payload)


def trace_list_payload(payload: Any, *, field_name: str) -> List[Dict[str, Any]]:
    if payload is None:
        return []
    if not isinstance(payload, list) or any(not isinstance(item, dict) for item in payload):
        raise ValueError(f"{field_name} must be a list of dicts")
    return [deepcopy(item) for item in payload]


def fallback_location_id(name: str) -> str:
    """Return a stable fallback id without depending on legacy world-data projections."""
    slug = str(name).lower().replace(" ", "_").replace("-", "_").replace("'", "")
    return f"loc_{slug}" if slug else "loc_unknown"


def neutral_location_state_defaults(_location_id: str, _region_type: str) -> Dict[str, int]:
    """Return conservative defaults for standalone LocationState deserialization."""
    return {
        "prosperity": 50,
        "safety": 50,
        "mood": 50,
        "danger": 20,
        "traffic": 30,
        "rumor_heat": 0,
        "road_condition": 70,
    }


FallbackLocationResolver = Callable[[str], str]
LocationIdNormalizer = Callable[[Any, str], str]
LocationDefaultsResolver = Callable[[str, str], Dict[str, int]]

_fallback_location_resolver: FallbackLocationResolver = fallback_location_id
_location_defaults_resolver: LocationDefaultsResolver = neutral_location_state_defaults


class SupportsSiteSeed(Protocol):
    location_id: str
    name: str
    description: str
    region_type: str
    x: int
    y: int


def configure_location_state_resolvers(
    *,
    fallback_resolver: FallbackLocationResolver | None = None,
    defaults_resolver: LocationDefaultsResolver | None = None,
) -> None:
    """Configure legacy classmethod defaults without making this module bundle-aware."""
    global _fallback_location_resolver, _location_defaults_resolver
    if fallback_resolver is not None:
        _fallback_location_resolver = fallback_resolver
    if defaults_resolver is not None:
        _location_defaults_resolver = defaults_resolver


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


@dataclass(slots=True)
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
    controlling_faction_id: str | None = None
    recent_event_ids: List[str] = field(default_factory=list)
    aliases: List[str] = field(default_factory=list)
    generated_endonym: str = ""
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
            setattr(self, field_name, clamp_state(getattr(self, field_name)))

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
            "generated_endonym": self.generated_endonym,
            "memorial_ids": list(self.memorial_ids),
            "live_traces": [deepcopy(trace) for trace in self.live_traces],
        }

    @classmethod
    def from_default_entry(
        cls,
        entry: Tuple[str, str, str, str, int, int],
        *,
        defaults_for_location: LocationDefaultsResolver | None = None,
    ) -> "LocationState":
        loc_id, canonical_name, description, region_type, x, y = entry
        defaults_resolver = defaults_for_location or _location_defaults_resolver
        defaults = defaults_resolver(loc_id, region_type)
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
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        normalize_location_id: LocationIdNormalizer | None = None,
        fallback_resolver: FallbackLocationResolver | None = None,
        defaults_for_location: LocationDefaultsResolver | None = None,
    ) -> "LocationState":
        canonical_name = data.get("canonical_name") or data.get("name", "")
        loc_id = data.get("id")
        if normalize_location_id is not None:
            loc_id = normalize_location_id(loc_id, canonical_name)
        elif not loc_id:
            resolved_fallback = fallback_resolver or _fallback_location_resolver
            loc_id = resolved_fallback(canonical_name)
        region_type = data["region_type"]
        defaults_resolver = defaults_for_location or _location_defaults_resolver
        defaults = defaults_resolver(loc_id, region_type)
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
            recent_event_ids=string_list_payload(data.get("recent_event_ids", []), field_name="recent_event_ids"),
            aliases=string_list_payload(data.get("aliases", []), field_name="aliases"),
            generated_endonym=str(data.get("generated_endonym", "")),
            memorial_ids=string_list_payload(data.get("memorial_ids", []), field_name="memorial_ids"),
            live_traces=trace_list_payload(data.get("live_traces", []), field_name="live_traces"),
        )


def location_state_from_site_seed(
    seed: SupportsSiteSeed,
    *,
    defaults_for_location: LocationDefaultsResolver,
    endonym_for_location: Callable[[str], str | None],
) -> LocationState:
    """Build a LocationState from an active setting-bundle site seed."""
    location = LocationState(
        id=seed.location_id,
        canonical_name=seed.name,
        description=seed.description,
        region_type=seed.region_type,
        x=seed.x,
        y=seed.y,
        **defaults_for_location(seed.location_id, seed.region_type),
    )
    endonym = endonym_for_location(seed.location_id)
    if endonym and endonym != location.canonical_name:
        location.generated_endonym = endonym
    return location

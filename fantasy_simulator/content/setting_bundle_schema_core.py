"""Core setting-bundle schema definitions and payload helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from ..rule_override_resolution import (
    resolve_event_impact_rule_overrides,
    resolve_propagation_rule_overrides,
)


def legacy_location_id_alias(name: str) -> str:
    """Generate the legacy fallback location-id alias for a site name."""
    slug = name.lower().replace(" ", "_").replace("-", "_").replace("'", "")
    return f"loc_{slug}"


def copy_rule_overrides(raw_rules: Any, *, field_name: str) -> Dict[str, Dict[str, Any]]:
    """Normalize nested override tables without coercing payload types."""
    if raw_rules is None:
        return {}
    if not isinstance(raw_rules, Mapping):
        raise ValueError(f"{field_name} must be an object")

    normalized: Dict[str, Dict[str, Any]] = {}
    for raw_section, raw_values in raw_rules.items():
        section = str(raw_section)
        if not isinstance(raw_values, Mapping):
            raise ValueError(f"{field_name}[{section!r}] must be an object")
        normalized[section] = {str(key): value for key, value in raw_values.items()}
    return normalized


def string_list_payload(payload: Any, *, field_name: str) -> List[str]:
    if payload is None:
        return []
    if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
        raise ValueError(f"{field_name} must be a list of strings")
    return list(payload)


def bool_payload(payload: Any, *, field_name: str) -> bool:
    if not isinstance(payload, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return payload


def merge_event_impact_rule_overrides(
    overrides: Mapping[str, Mapping[str, Any]] | None,
) -> Dict[str, Dict[str, int]]:
    """Backward-compatible wrapper around the domain-side rule resolver."""
    return resolve_event_impact_rule_overrides(overrides)


def merge_propagation_rule_overrides(
    overrides: Mapping[str, Mapping[str, Any]] | None,
) -> Dict[str, Dict[str, Any]]:
    """Backward-compatible wrapper around the domain-side rule resolver."""
    return resolve_propagation_rule_overrides(overrides)


@dataclass
class RaceDefinition:
    """Static race metadata for a setting bundle."""

    name: str
    description: str
    stat_bonuses: Dict[str, int] = field(default_factory=dict)
    lifespan_years: int | None = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "stat_bonuses": {key: int(value) for key, value in self.stat_bonuses.items()},
        }
        if self.lifespan_years is not None:
            payload["lifespan_years"] = int(self.lifespan_years)
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RaceDefinition":
        raw_lifespan = data.get("lifespan_years")
        lifespan_years = None if raw_lifespan is None else int(raw_lifespan)
        if lifespan_years is not None and lifespan_years <= 0:
            raise ValueError("lifespan_years must be positive")
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            stat_bonuses={
                key: int(value)
                for key, value in dict(data.get("stat_bonuses", {})).items()
            },
            lifespan_years=lifespan_years,
        )


@dataclass
class JobDefinition:
    """Static job metadata for a setting bundle."""

    name: str
    description: str
    primary_skills: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "primary_skills": list(self.primary_skills),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobDefinition":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            primary_skills=string_list_payload(data.get("primary_skills", []), field_name="primary_skills"),
        )


@dataclass
class SiteSeedDefinition:
    """A default location/site seed for bundle-driven world bootstrapping."""

    location_id: str
    name: str
    description: str
    region_type: str
    x: int
    y: int
    tags: List[str] = field(default_factory=list)
    language_key: str = ""
    native_name: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location_id": self.location_id,
            "name": self.name,
            "description": self.description,
            "region_type": self.region_type,
            "x": int(self.x),
            "y": int(self.y),
            "tags": list(self.tags),
            "language_key": self.language_key,
            "native_name": self.native_name,
        }

    def as_world_data_entry(self) -> tuple[str, str, str, str, int, int]:
        return (
            self.location_id,
            self.name,
            self.description,
            self.region_type,
            int(self.x),
            int(self.y),
        )

    def has_tag(self, tag: str) -> bool:
        """Return whether this seed carries the given semantic tag."""
        return tag in self.tags

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SiteSeedDefinition":
        return cls(
            location_id=data["location_id"],
            name=data["name"],
            description=data.get("description", ""),
            region_type=data.get("region_type", "plains"),
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            tags=string_list_payload(data.get("tags", []), field_name="tags"),
            language_key=str(data.get("language_key", "")),
            native_name=str(data.get("native_name", "")),
        )


@dataclass
class RouteSeedDefinition:
    """Static canonical route definition for bundle-backed topology."""

    route_id: str
    from_site_id: str
    to_site_id: str
    route_type: str = "road"
    distance: int = 1
    blocked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "from_site_id": self.from_site_id,
            "to_site_id": self.to_site_id,
            "route_type": self.route_type,
            "distance": int(self.distance),
            "blocked": bool(self.blocked),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RouteSeedDefinition":
        route_id = data["route_id"]
        from_site_id = data["from_site_id"]
        to_site_id = data["to_site_id"]
        if not isinstance(route_id, str) or not route_id:
            raise ValueError("route_id must be a non-empty string")
        if not isinstance(from_site_id, str) or not from_site_id:
            raise ValueError("from_site_id must be a non-empty string")
        if not isinstance(to_site_id, str) or not to_site_id:
            raise ValueError("to_site_id must be a non-empty string")
        return cls(
            route_id=route_id,
            from_site_id=from_site_id,
            to_site_id=to_site_id,
            route_type=str(data.get("route_type", "road")),
            distance=int(data.get("distance", 1)),
            blocked=bool_payload(data.get("blocked", False), field_name="blocked"),
        )


@dataclass
class NamingRulesDefinition:
    """Simple name pools for default character generation."""

    first_names_male: List[str] = field(default_factory=list)
    first_names_female: List[str] = field(default_factory=list)
    first_names_non_binary: List[str] = field(default_factory=list)
    last_names: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "first_names_male": list(self.first_names_male),
            "first_names_female": list(self.first_names_female),
            "first_names_non_binary": list(self.first_names_non_binary),
            "last_names": list(self.last_names),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NamingRulesDefinition":
        male = string_list_payload(data.get("first_names_male", []), field_name="first_names_male")
        female = string_list_payload(data.get("first_names_female", []), field_name="first_names_female")
        non_binary = string_list_payload(data.get("first_names_non_binary", []), field_name="first_names_non_binary")
        last_names = string_list_payload(data.get("last_names", []), field_name="last_names")
        if not non_binary:
            non_binary = male + female
        return cls(
            first_names_male=male,
            first_names_female=female,
            first_names_non_binary=non_binary,
            last_names=last_names,
        )


@dataclass
class GlossaryEntryDefinition:
    """Author-facing term definition for setting-specific lore words."""

    term: str
    definition: str = ""
    category: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "term": self.term,
            "definition": self.definition,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GlossaryEntryDefinition":
        return cls(
            term=data["term"],
            definition=str(data.get("definition", "")),
            category=str(data.get("category", "")),
        )


_copy_rule_overrides = copy_rule_overrides
_string_list_payload = string_list_payload
_bool_payload = bool_payload

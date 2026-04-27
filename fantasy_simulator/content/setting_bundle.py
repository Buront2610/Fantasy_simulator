"""Serializable setting-bundle schema and loader for static world data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping

from ..language.schema import (
    VALID_SOUND_CHANGE_CONTEXTS,
    VALID_SOUND_CHANGE_POSITIONS,
    SoundChangeRuleDefinition,
    sound_change_rules_from_payload,
)
from ..rule_override_resolution import (
    resolve_event_impact_rule_overrides,
    resolve_propagation_rule_overrides,
)


BUNDLES_DIR = Path(__file__).with_name("bundles")
DEFAULT_AETHORIA_BUNDLE_PATH = BUNDLES_DIR / "aethoria.json"


def legacy_location_id_alias(name: str) -> str:
    """Generate the legacy fallback location-id alias for a site name."""
    slug = name.lower().replace(" ", "_").replace("-", "_").replace("'", "")
    return f"loc_{slug}"


def _duplicate_values(items: List[str]) -> List[str]:
    """Return duplicate string values while preserving first duplicate order."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in items:
        if item in seen and item not in duplicates:
            duplicates.append(item)
        seen.add(item)
    return duplicates


def _setting_entry_key(name: str) -> str:
    """Return a stable inspection key for lightweight named setting entries."""
    return name.strip().lower().replace(" ", "_").replace("-", "_").replace("'", "")


def _copy_rule_overrides(raw_rules: Any, *, field_name: str) -> Dict[str, Dict[str, Any]]:
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


def _string_list_payload(payload: Any, *, field_name: str) -> List[str]:
    if payload is None:
        return []
    if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
        raise ValueError(f"{field_name} must be a list of strings")
    return list(payload)


def _bool_payload(payload: Any, *, field_name: str) -> bool:
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
class CalendarMonthDefinition:
    """One month entry in a world-specific calendar."""

    month_key: str
    display_name: str
    days: int
    season: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "month_key": self.month_key,
            "display_name": self.display_name,
            "days": int(self.days),
            "season": self.season,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarMonthDefinition":
        return cls(
            month_key=data["month_key"],
            display_name=data.get("display_name", data["month_key"]),
            days=max(1, int(data.get("days", 30))),
            season=data.get("season", ""),
        )


@dataclass
class CalendarDefinition:
    """Serializable calendar metadata for a world setting."""

    calendar_key: str
    display_name: str
    months: List[CalendarMonthDefinition] = field(default_factory=list)

    @property
    def months_per_year(self) -> int:
        return max(1, len(self.months))

    @property
    def days_per_year(self) -> int:
        if not self.months:
            return 30
        return sum(max(1, month.days) for month in self.months)

    def days_in_month(self, month: int) -> int:
        if not self.months:
            return 30
        month_index = max(1, min(self.months_per_year, month)) - 1
        return max(1, self.months[month_index].days)

    def month_definition(self, month: int) -> CalendarMonthDefinition:
        if not self.months:
            return CalendarMonthDefinition(
                month_key=f"month_{max(1, int(month))}",
                display_name=f"Month {max(1, int(month))}",
                days=30,
            )
        month_index = max(1, min(self.months_per_year, month)) - 1
        return self.months[month_index]

    def month_display_name(self, month: int) -> str:
        return self.month_definition(month).display_name

    def season_for_month(self, month: int) -> str:
        if not self.months:
            return "unknown"
        month_index = max(1, min(self.months_per_year, month)) - 1
        season = self.months[month_index].season
        return season or "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calendar_key": self.calendar_key,
            "display_name": self.display_name,
            "months": [month.to_dict() for month in self.months],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarDefinition":
        return cls(
            calendar_key=data.get("calendar_key", "default_calendar"),
            display_name=data.get("display_name", "Default Calendar"),
            months=[
                CalendarMonthDefinition.from_dict(item)
                for item in data.get("months", [])
            ],
        )


@dataclass
class RaceDefinition:
    """Static race metadata for a setting bundle."""

    name: str
    description: str
    stat_bonuses: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "stat_bonuses": {key: int(value) for key, value in self.stat_bonuses.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RaceDefinition":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            stat_bonuses={
                key: int(value)
                for key, value in dict(data.get("stat_bonuses", {})).items()
            },
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
            primary_skills=_string_list_payload(data.get("primary_skills", []), field_name="primary_skills"),
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
            tags=_string_list_payload(data.get("tags", []), field_name="tags"),
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
            blocked=_bool_payload(data.get("blocked", False), field_name="blocked"),
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
        male = _string_list_payload(data.get("first_names_male", []), field_name="first_names_male")
        female = _string_list_payload(data.get("first_names_female", []), field_name="first_names_female")
        non_binary = _string_list_payload(data.get("first_names_non_binary", []), field_name="first_names_non_binary")
        last_names = _string_list_payload(data.get("last_names", []), field_name="last_names")
        if not non_binary:
            non_binary = male + female
        return cls(
            first_names_male=male,
            first_names_female=female,
            first_names_non_binary=non_binary,
            last_names=last_names,
        )


@dataclass
class LanguageDefinition:
    """Serializable prototype language description for generated naming and vocabulary."""

    language_key: str
    display_name: str
    parent_key: str = ""
    seed_syllables: List[str] = field(default_factory=list)
    consonants: List[str] = field(default_factory=list)
    vowels: List[str] = field(default_factory=list)
    front_vowels: List[str] = field(default_factory=list)
    back_vowels: List[str] = field(default_factory=list)
    liquid_consonants: List[str] = field(default_factory=list)
    nasal_consonants: List[str] = field(default_factory=list)
    fricative_consonants: List[str] = field(default_factory=list)
    stop_consonants: List[str] = field(default_factory=list)
    syllable_templates: List[str] = field(default_factory=list)
    male_suffixes: List[str] = field(default_factory=list)
    female_suffixes: List[str] = field(default_factory=list)
    neutral_suffixes: List[str] = field(default_factory=list)
    surname_suffixes: List[str] = field(default_factory=list)
    name_stems: List[str] = field(default_factory=list)
    given_name_patterns: List[str] = field(default_factory=list)
    surname_patterns: List[str] = field(default_factory=list)
    toponym_stems: List[str] = field(default_factory=list)
    toponym_suffixes: List[str] = field(default_factory=list)
    toponym_patterns: List[str] = field(default_factory=list)
    sound_shifts: Dict[str, str] = field(default_factory=dict)
    sound_change_rules: List[SoundChangeRuleDefinition] = field(default_factory=list)
    evolution_rule_pool: List[SoundChangeRuleDefinition] = field(default_factory=list)
    inspiration_tags: List[str] = field(default_factory=list)
    lexicon_size: int = 24
    evolution_interval_years: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language_key": self.language_key,
            "display_name": self.display_name,
            "parent_key": self.parent_key,
            "seed_syllables": list(self.seed_syllables),
            "consonants": list(self.consonants),
            "vowels": list(self.vowels),
            "front_vowels": list(self.front_vowels),
            "back_vowels": list(self.back_vowels),
            "liquid_consonants": list(self.liquid_consonants),
            "nasal_consonants": list(self.nasal_consonants),
            "fricative_consonants": list(self.fricative_consonants),
            "stop_consonants": list(self.stop_consonants),
            "syllable_templates": list(self.syllable_templates),
            "male_suffixes": list(self.male_suffixes),
            "female_suffixes": list(self.female_suffixes),
            "neutral_suffixes": list(self.neutral_suffixes),
            "surname_suffixes": list(self.surname_suffixes),
            "name_stems": list(self.name_stems),
            "given_name_patterns": list(self.given_name_patterns),
            "surname_patterns": list(self.surname_patterns),
            "toponym_stems": list(self.toponym_stems),
            "toponym_suffixes": list(self.toponym_suffixes),
            "toponym_patterns": list(self.toponym_patterns),
            "sound_shifts": {str(source): str(target) for source, target in self.sound_shifts.items()},
            "sound_change_rules": [rule.to_dict() for rule in self.sound_change_rules],
            "evolution_rule_pool": [rule.to_dict() for rule in self.evolution_rule_pool],
            "inspiration_tags": list(self.inspiration_tags),
            "lexicon_size": int(self.lexicon_size),
            "evolution_interval_years": int(self.evolution_interval_years),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LanguageDefinition":
        raw_sound_shifts = data.get("sound_shifts", {})
        if raw_sound_shifts is None:
            raw_sound_shifts = {}
        if not isinstance(raw_sound_shifts, Mapping):
            raise ValueError("sound_shifts must be an object")
        return cls(
            language_key=data["language_key"],
            display_name=data.get("display_name", data["language_key"]),
            parent_key=data.get("parent_key", ""),
            seed_syllables=_string_list_payload(data.get("seed_syllables", []), field_name="seed_syllables"),
            consonants=_string_list_payload(data.get("consonants", []), field_name="consonants"),
            vowels=_string_list_payload(data.get("vowels", []), field_name="vowels"),
            front_vowels=_string_list_payload(data.get("front_vowels", []), field_name="front_vowels"),
            back_vowels=_string_list_payload(data.get("back_vowels", []), field_name="back_vowels"),
            liquid_consonants=_string_list_payload(
                data.get("liquid_consonants", []),
                field_name="liquid_consonants",
            ),
            nasal_consonants=_string_list_payload(
                data.get("nasal_consonants", []),
                field_name="nasal_consonants",
            ),
            fricative_consonants=_string_list_payload(
                data.get("fricative_consonants", []),
                field_name="fricative_consonants",
            ),
            stop_consonants=_string_list_payload(
                data.get("stop_consonants", []),
                field_name="stop_consonants",
            ),
            syllable_templates=_string_list_payload(
                data.get("syllable_templates", []),
                field_name="syllable_templates",
            ),
            male_suffixes=_string_list_payload(data.get("male_suffixes", []), field_name="male_suffixes"),
            female_suffixes=_string_list_payload(data.get("female_suffixes", []), field_name="female_suffixes"),
            neutral_suffixes=_string_list_payload(data.get("neutral_suffixes", []), field_name="neutral_suffixes"),
            surname_suffixes=_string_list_payload(data.get("surname_suffixes", []), field_name="surname_suffixes"),
            name_stems=_string_list_payload(data.get("name_stems", []), field_name="name_stems"),
            given_name_patterns=_string_list_payload(
                data.get("given_name_patterns", []),
                field_name="given_name_patterns",
            ),
            surname_patterns=_string_list_payload(
                data.get("surname_patterns", []),
                field_name="surname_patterns",
            ),
            toponym_stems=_string_list_payload(data.get("toponym_stems", []), field_name="toponym_stems"),
            toponym_suffixes=_string_list_payload(
                data.get("toponym_suffixes", []),
                field_name="toponym_suffixes",
            ),
            toponym_patterns=_string_list_payload(
                data.get("toponym_patterns", []),
                field_name="toponym_patterns",
            ),
            sound_shifts={str(source): str(target) for source, target in raw_sound_shifts.items()},
            sound_change_rules=sound_change_rules_from_payload(
                data.get("sound_change_rules", []),
                field_name="sound_change_rules",
            ),
            evolution_rule_pool=sound_change_rules_from_payload(
                data.get("evolution_rule_pool", []),
                field_name="evolution_rule_pool",
            ),
            inspiration_tags=_string_list_payload(data.get("inspiration_tags", []), field_name="inspiration_tags"),
            lexicon_size=max(8, int(data.get("lexicon_size", 24))),
            evolution_interval_years=max(0, int(data.get("evolution_interval_years", 0))),
        )


@dataclass
class LanguageCommunityDefinition:
    """Selectors that map race/tribe/region identity to a language."""

    community_key: str
    display_name: str
    language_key: str
    races: List[str] = field(default_factory=list)
    tribes: List[str] = field(default_factory=list)
    regions: List[str] = field(default_factory=list)
    priority: int = 0
    is_lingua_franca: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "community_key": self.community_key,
            "display_name": self.display_name,
            "language_key": self.language_key,
            "races": list(self.races),
            "tribes": list(self.tribes),
            "regions": list(self.regions),
            "priority": int(self.priority),
            "is_lingua_franca": bool(self.is_lingua_franca),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LanguageCommunityDefinition":
        return cls(
            community_key=data["community_key"],
            display_name=data.get("display_name", data["community_key"]),
            language_key=data["language_key"],
            races=_string_list_payload(data.get("races", []), field_name="races"),
            tribes=_string_list_payload(data.get("tribes", []), field_name="tribes"),
            regions=_string_list_payload(data.get("regions", []), field_name="regions"),
            priority=int(data.get("priority", 0)),
            is_lingua_franca=bool(data.get("is_lingua_franca", False)),
        )


@dataclass(frozen=True)
class SettingEntryInspection:
    """Typed inspection view for lightweight setting entries backed by names."""

    entry_type: str
    key: str
    display_name: str


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


@dataclass
class WorldDefinition:
    """Static lore metadata for a world setting bundle."""

    world_key: str
    display_name: str
    lore_text: str
    era: str = ""
    cultures: List[str] = field(default_factory=list)
    factions: List[str] = field(default_factory=list)
    glossary: List[GlossaryEntryDefinition] = field(default_factory=list)
    calendar: CalendarDefinition = field(default_factory=lambda: default_calendar_definition())
    races: List[RaceDefinition] = field(default_factory=list)
    jobs: List[JobDefinition] = field(default_factory=list)
    site_seeds: List[SiteSeedDefinition] = field(default_factory=list)
    route_seeds: List[RouteSeedDefinition] = field(default_factory=list)
    naming_rules: NamingRulesDefinition = field(default_factory=NamingRulesDefinition)
    languages: List[LanguageDefinition] = field(default_factory=list)
    language_communities: List[LanguageCommunityDefinition] = field(default_factory=list)
    event_impact_rules: Dict[str, Dict[str, int]] = field(default_factory=dict)
    propagation_rules: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def site_seed_index(self) -> Dict[str, SiteSeedDefinition]:
        """Return location_id -> site seed lookup for authoring helpers."""
        return {seed.location_id: seed for seed in self.site_seeds}

    def site_seed_by_id(self, location_id: str) -> SiteSeedDefinition | None:
        """Return the site seed for a given location id, if present."""
        return self.site_seed_index().get(location_id)

    def resident_site_ids(self) -> List[str]:
        """Return site ids tagged as reasonable resident defaults."""
        return [
            seed.location_id
            for seed in self.site_seeds
            if "default_resident" in seed.tags
        ]

    def capital_site_ids(self) -> List[str]:
        """Return site ids tagged as capitals."""
        return [
            seed.location_id
            for seed in self.site_seeds
            if "capital" in seed.tags
        ]

    def culture_entries(self) -> List[SettingEntryInspection]:
        """Return typed culture inspection entries while preserving legacy storage."""
        return [
            SettingEntryInspection(
                entry_type="culture",
                key=_setting_entry_key(culture),
                display_name=culture,
            )
            for culture in self.cultures
        ]

    def faction_entries(self) -> List[SettingEntryInspection]:
        """Return typed faction inspection entries while preserving legacy storage."""
        return [
            SettingEntryInspection(
                entry_type="faction",
                key=_setting_entry_key(faction),
                display_name=faction,
            )
            for faction in self.factions
        ]

    def glossary_entries(self) -> List[SettingEntryInspection]:
        """Return typed glossary inspection entries while preserving authored terms."""
        return [
            SettingEntryInspection(
                entry_type="glossary",
                key=_setting_entry_key(entry.term),
                display_name=entry.term,
            )
            for entry in self.glossary
        ]

    def site_counts_by_region_type(self) -> Dict[str, int]:
        """Return a stable region-type breakdown for authoring inspection."""
        counts: Dict[str, int] = {}
        for seed in self.site_seeds:
            counts[seed.region_type] = counts.get(seed.region_type, 0) + 1
        return dict(sorted(counts.items()))

    def route_counts_by_type(self) -> Dict[str, int]:
        """Return a stable route-type breakdown for authoring inspection."""
        counts: Dict[str, int] = {}
        for seed in self.route_seeds:
            counts[seed.route_type] = counts.get(seed.route_type, 0) + 1
        return dict(sorted(counts.items()))

    def community_keys_by_region(self) -> Dict[str, List[str]]:
        """Return region -> community keys mapping for bundle swap review."""
        mapping: Dict[str, List[str]] = {}
        for community in self.language_communities:
            for region_id in community.regions:
                mapping.setdefault(region_id, []).append(community.community_key)
        return {region_id: sorted(keys) for region_id, keys in sorted(mapping.items())}

    def site_ids_without_language_key(self) -> List[str]:
        """Return site ids that have no primary authored language."""
        return sorted(
            seed.location_id
            for seed in self.site_seeds
            if not seed.language_key.strip()
        )

    def site_ids_without_language_community(self) -> List[str]:
        """Return site ids not covered by any regional language community."""
        covered_region_ids = {
            region_id
            for community in self.language_communities
            for region_id in community.regions
        }
        return sorted(
            seed.location_id
            for seed in self.site_seeds
            if seed.location_id not in covered_region_ids
        )

    def site_ids_without_matching_language_community(self) -> List[str]:
        """Return site ids without a regional community for their primary language."""
        covered_language_regions = {
            (community.language_key, region_id)
            for community in self.language_communities
            for region_id in community.regions
        }
        return sorted(
            seed.location_id
            for seed in self.site_seeds
            if seed.language_key.strip()
            and (seed.language_key, seed.location_id) not in covered_language_regions
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "world_key": self.world_key,
            "display_name": self.display_name,
            "lore_text": self.lore_text,
            "era": self.era,
            "cultures": list(self.cultures),
            "factions": list(self.factions),
            "glossary": [entry.to_dict() for entry in self.glossary],
            "calendar": self.calendar.to_dict(),
            "races": [race.to_dict() for race in self.races],
            "jobs": [job.to_dict() for job in self.jobs],
            "site_seeds": [seed.to_dict() for seed in self.site_seeds],
            "route_seeds": [seed.to_dict() for seed in self.route_seeds],
            "naming_rules": self.naming_rules.to_dict(),
            "languages": [language.to_dict() for language in self.languages],
            "language_communities": [community.to_dict() for community in self.language_communities],
            "event_impact_rules": {
                kind: {attr: int(delta) for attr, delta in deltas.items()}
                for kind, deltas in self.event_impact_rules.items()
            },
            "propagation_rules": {
                kind: {attr: value for attr, value in deltas.items()}
                for kind, deltas in self.propagation_rules.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldDefinition":
        calendar = CalendarDefinition.from_dict(
            data.get("calendar", default_calendar_definition().to_dict())
        )
        return cls(
            world_key=data["world_key"],
            display_name=data["display_name"],
            lore_text=data["lore_text"],
            era=data.get("era", ""),
            cultures=_string_list_payload(data.get("cultures", []), field_name="cultures"),
            factions=_string_list_payload(data.get("factions", []), field_name="factions"),
            glossary=[
                GlossaryEntryDefinition.from_dict(item)
                for item in data.get("glossary", [])
            ],
            calendar=calendar,
            races=[
                RaceDefinition.from_dict(item)
                for item in data.get("races", [])
            ],
            jobs=[
                JobDefinition.from_dict(item)
                for item in data.get("jobs", [])
            ],
            site_seeds=[
                SiteSeedDefinition.from_dict(item)
                for item in data.get("site_seeds", [])
            ],
            route_seeds=[
                RouteSeedDefinition.from_dict(item)
                for item in data.get("route_seeds", [])
            ],
            naming_rules=NamingRulesDefinition.from_dict(data.get("naming_rules", {})),
            languages=[
                LanguageDefinition.from_dict(item)
                for item in data.get("languages", [])
            ],
            language_communities=[
                LanguageCommunityDefinition.from_dict(item)
                for item in data.get("language_communities", [])
            ],
            event_impact_rules=_copy_rule_overrides(
                data.get("event_impact_rules", {}),
                field_name="world_definition.event_impact_rules",
            ),
            propagation_rules=_copy_rule_overrides(
                data.get("propagation_rules", {}),
                field_name="world_definition.propagation_rules",
            ),
        )


@dataclass
class SettingBundle:
    """Serializable container for static world-definition data."""

    schema_version: int
    world_definition: WorldDefinition

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "world_definition": self.world_definition.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SettingBundle":
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            world_definition=WorldDefinition.from_dict(data["world_definition"]),
        )


@dataclass(frozen=True)
class SettingBundleAuthoringSummary:
    """Stable, non-UI summary for bundle inspection and swap review."""

    world_key: str
    display_name: str
    site_count: int
    route_count: int
    language_count: int
    culture_count: int = 0
    faction_count: int = 0
    glossary_count: int = 0
    language_community_count: int = 0
    resident_site_ids: List[str] = field(default_factory=list)
    capital_site_ids: List[str] = field(default_factory=list)
    culture_keys: List[str] = field(default_factory=list)
    faction_keys: List[str] = field(default_factory=list)
    glossary_keys: List[str] = field(default_factory=list)
    site_counts_by_region_type: Dict[str, int] = field(default_factory=dict)
    route_counts_by_type: Dict[str, int] = field(default_factory=dict)
    language_keys: List[str] = field(default_factory=list)
    community_keys_by_region: Dict[str, List[str]] = field(default_factory=dict)
    sites_with_native_names: List[str] = field(default_factory=list)
    site_ids_without_language_key: List[str] = field(default_factory=list)
    site_ids_without_language_community: List[str] = field(default_factory=list)
    site_ids_without_matching_language_community: List[str] = field(default_factory=list)


def build_setting_bundle_authoring_summary(bundle: SettingBundle) -> SettingBundleAuthoringSummary:
    """Return a compact summary suitable for authoring and swap validation."""
    world = bundle.world_definition
    return SettingBundleAuthoringSummary(
        world_key=world.world_key,
        display_name=world.display_name,
        site_count=len(world.site_seeds),
        route_count=len(world.route_seeds),
        language_count=len(world.languages),
        culture_count=len(world.cultures),
        faction_count=len(world.factions),
        glossary_count=len(world.glossary),
        language_community_count=len(world.language_communities),
        resident_site_ids=world.resident_site_ids(),
        capital_site_ids=world.capital_site_ids(),
        culture_keys=sorted(entry.key for entry in world.culture_entries()),
        faction_keys=sorted(entry.key for entry in world.faction_entries()),
        glossary_keys=sorted(entry.key for entry in world.glossary_entries()),
        site_counts_by_region_type=world.site_counts_by_region_type(),
        route_counts_by_type=world.route_counts_by_type(),
        language_keys=sorted(language.language_key for language in world.languages),
        community_keys_by_region=world.community_keys_by_region(),
        sites_with_native_names=sorted(
            seed.location_id for seed in world.site_seeds if seed.native_name.strip()
        ),
        site_ids_without_language_key=world.site_ids_without_language_key(),
        site_ids_without_language_community=world.site_ids_without_language_community(),
        site_ids_without_matching_language_community=world.site_ids_without_matching_language_community(),
    )


def default_calendar_definition() -> CalendarDefinition:
    """Return the bundled Aethorian default calendar."""

    return CalendarDefinition(
        calendar_key="aethorian_reckoning",
        display_name="Aethorian Reckoning",
        months=[
            CalendarMonthDefinition("embermorn", "Embermorn", 30, season="winter"),
            CalendarMonthDefinition("frostwane", "Frostwane", 30, season="winter"),
            CalendarMonthDefinition("raincall", "Raincall", 30, season="spring"),
            CalendarMonthDefinition("bloomtide", "Bloomtide", 30, season="spring"),
            CalendarMonthDefinition("suncrest", "Suncrest", 30, season="spring"),
            CalendarMonthDefinition("highsun", "Highsun", 30, season="summer"),
            CalendarMonthDefinition("goldleaf", "Goldleaf", 30, season="summer"),
            CalendarMonthDefinition("hearthwane", "Hearthwane", 30, season="summer"),
            CalendarMonthDefinition("duskmarch", "Duskmarch", 30, season="autumn"),
            CalendarMonthDefinition("cinderfall", "Cinderfall", 30, season="autumn"),
            CalendarMonthDefinition("longshade", "Longshade", 30, season="autumn"),
            CalendarMonthDefinition("nightfrost", "Nightfrost", 30, season="winter"),
        ],
    )


@lru_cache(maxsize=1)
def _default_aethoria_bundle_data() -> Dict[str, Any]:
    try:
        return json.loads(DEFAULT_AETHORIA_BUNDLE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Bundled Aethoria setting not found: {DEFAULT_AETHORIA_BUNDLE_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Bundled Aethoria setting JSON is invalid: {DEFAULT_AETHORIA_BUNDLE_PATH}: {exc.msg}"
        ) from exc


def _backfill_route_seeds_if_missing(
    bundle: SettingBundle,
    *,
    route_seeds_were_present: bool,
) -> None:
    """Populate canonical route seeds for legacy bundles that only ship site seeds."""
    world = bundle.world_definition
    if route_seeds_were_present or not world.site_seeds:
        return

    from ..terrain import build_default_terrain

    width = max(seed.x for seed in world.site_seeds) + 1
    height = max(seed.y for seed in world.site_seeds) + 1
    _terrain_map, _sites, routes = build_default_terrain(
        width=width,
        height=height,
        locations=[seed.as_world_data_entry() for seed in world.site_seeds],
    )
    world.route_seeds = [
        RouteSeedDefinition(
            route_id=route.route_id,
            from_site_id=route.from_site_id,
            to_site_id=route.to_site_id,
            route_type=route.route_type,
            distance=route.distance,
            blocked=route.blocked,
        )
        for route in routes
    ]


def _known_community_race_names(world: WorldDefinition) -> set[str]:
    """Return race names allowed in language community selectors."""
    known_races = {race.name for race in world.races}
    if world.world_key == "aethoria":
        default_world = _default_aethoria_bundle_data().get("world_definition", {})
        for race_data in default_world.get("races", []):
            race_name = str(race_data.get("name", ""))
            if race_name:
                known_races.add(race_name)
    return known_races


def _validate_bundle_identity(bundle: SettingBundle, world: WorldDefinition, *, source: str) -> None:
    if bundle.schema_version < 1:
        raise ValueError(f"Setting bundle {source} has invalid schema_version: {bundle.schema_version}")
    if not world.world_key:
        raise ValueError(f"Setting bundle {source} must define world_definition.world_key")
    if not world.display_name:
        raise ValueError(f"Setting bundle {source} must define world_definition.display_name")
    if not world.lore_text:
        raise ValueError(f"Setting bundle {source} must define world_definition.lore_text")


def _validate_bundle_unique_names(world: WorldDefinition, *, source: str) -> None:
    blank_cultures = [culture for culture in world.cultures if not culture.strip()]
    if blank_cultures:
        raise ValueError(f"Setting bundle {source} contains blank culture names")

    duplicate_cultures = _duplicate_values(world.cultures)
    if duplicate_cultures:
        raise ValueError(
            f"Setting bundle {source} contains duplicate culture names: {', '.join(duplicate_cultures)}"
        )
    duplicate_culture_keys = _duplicate_values([entry.key for entry in world.culture_entries()])
    if duplicate_culture_keys:
        raise ValueError(
            f"Setting bundle {source} contains duplicate culture inspection keys: "
            f"{', '.join(duplicate_culture_keys)}"
        )

    blank_factions = [faction for faction in world.factions if not faction.strip()]
    if blank_factions:
        raise ValueError(f"Setting bundle {source} contains blank faction names")

    duplicate_factions = _duplicate_values(world.factions)
    if duplicate_factions:
        raise ValueError(
            f"Setting bundle {source} contains duplicate faction names: {', '.join(duplicate_factions)}"
        )
    duplicate_faction_keys = _duplicate_values([entry.key for entry in world.faction_entries()])
    if duplicate_faction_keys:
        raise ValueError(
            f"Setting bundle {source} contains duplicate faction inspection keys: "
            f"{', '.join(duplicate_faction_keys)}"
        )

    blank_glossary_terms = [entry.term for entry in world.glossary if not entry.term.strip()]
    if blank_glossary_terms:
        raise ValueError(f"Setting bundle {source} contains blank glossary terms")

    glossary_terms = [entry.term for entry in world.glossary]
    duplicate_glossary_terms = _duplicate_values(glossary_terms)
    if duplicate_glossary_terms:
        raise ValueError(
            f"Setting bundle {source} contains duplicate glossary terms: {', '.join(duplicate_glossary_terms)}"
        )
    duplicate_glossary_keys = _duplicate_values([entry.key for entry in world.glossary_entries()])
    if duplicate_glossary_keys:
        raise ValueError(
            f"Setting bundle {source} contains duplicate glossary inspection keys: "
            f"{', '.join(duplicate_glossary_keys)}"
        )

    race_names = [race.name for race in world.races]
    duplicate_races = _duplicate_values(race_names)
    if duplicate_races:
        raise ValueError(
            f"Setting bundle {source} contains duplicate race names: {', '.join(duplicate_races)}"
        )

    job_names = [job.name for job in world.jobs]
    duplicate_jobs = _duplicate_values(job_names)
    if duplicate_jobs:
        raise ValueError(
            f"Setting bundle {source} contains duplicate job names: {', '.join(duplicate_jobs)}"
        )

    language_keys = [language.language_key for language in world.languages]
    duplicate_language_keys = _duplicate_values(language_keys)
    if duplicate_language_keys:
        raise ValueError(
            f"Setting bundle {source} contains duplicate language keys: {', '.join(duplicate_language_keys)}"
        )

    community_keys = [community.community_key for community in world.language_communities]
    duplicate_community_keys = _duplicate_values(community_keys)
    if duplicate_community_keys:
        raise ValueError(
            f"Setting bundle {source} contains duplicate language community keys: {', '.join(duplicate_community_keys)}"
        )


def _validate_site_seeds(world: WorldDefinition, *, source: str) -> tuple[List[str], set[str]]:
    site_ids = [seed.location_id for seed in world.site_seeds]
    duplicate_site_ids = _duplicate_values(site_ids)
    if duplicate_site_ids:
        raise ValueError(
            f"Setting bundle {source} contains duplicate site seed ids: {', '.join(duplicate_site_ids)}"
        )

    site_names = [seed.name for seed in world.site_seeds]
    duplicate_site_names = _duplicate_values(site_names)
    if duplicate_site_names:
        raise ValueError(
            f"Setting bundle {source} contains duplicate site seed names: {', '.join(duplicate_site_names)}"
        )

    alias_to_canonical: Dict[str, str] = {}
    canonical_ids = set(site_ids)
    for seed in world.site_seeds:
        alias = legacy_location_id_alias(seed.name)
        previous = alias_to_canonical.get(alias)
        if previous is not None and previous != seed.location_id:
            raise ValueError(f"Setting bundle {source} contains ambiguous legacy location id aliases")
        if alias in canonical_ids and alias != seed.location_id:
            raise ValueError(f"Setting bundle {source} contains ambiguous legacy location id aliases")
        alias_to_canonical[alias] = seed.location_id

    site_coords = [(seed.x, seed.y) for seed in world.site_seeds]
    if site_coords and len(site_coords) != len(set(site_coords)):
        raise ValueError(f"Setting bundle {source} contains duplicate site seed coordinates")
    if any(seed.x < 0 or seed.y < 0 for seed in world.site_seeds):
        raise ValueError(f"Setting bundle {source} contains negative site seed coordinates")

    return site_ids, canonical_ids


def _validate_route_seeds(world: WorldDefinition, canonical_ids: set[str], *, source: str) -> None:
    route_ids = [seed.route_id for seed in world.route_seeds]
    duplicate_route_ids = _duplicate_values(route_ids)
    if duplicate_route_ids:
        raise ValueError(
            f"Setting bundle {source} contains duplicate route ids: {', '.join(duplicate_route_ids)}"
        )

    route_pairs = [
        tuple(sorted((seed.from_site_id, seed.to_site_id)))
        for seed in world.route_seeds
    ]
    duplicate_route_pairs = _duplicate_values([f"{a}->{b}" for a, b in route_pairs])
    if duplicate_route_pairs:
        raise ValueError(
            f"Setting bundle {source} contains duplicate route pairs: {', '.join(duplicate_route_pairs)}"
        )

    for route in world.route_seeds:
        if route.from_site_id == route.to_site_id:
            raise ValueError(f"Setting bundle {source} contains a self-loop route: {route.route_id}")
        if route.from_site_id not in canonical_ids or route.to_site_id not in canonical_ids:
            raise ValueError(
                f"Setting bundle {source} route {route.route_id} references an unknown site seed"
            )
        if route.distance < 1:
            raise ValueError(f"Setting bundle {source} route {route.route_id} must have distance >= 1")


def _validate_naming_rules(world: WorldDefinition, *, source: str) -> None:
    naming = world.naming_rules
    has_first_name_rules = (
        naming.first_names_male
        or naming.first_names_female
        or naming.first_names_non_binary
    )
    if has_first_name_rules and not naming.first_names_male:
        raise ValueError(f"Setting bundle {source} must provide first_names_male when naming rules are defined")
    if has_first_name_rules and not naming.first_names_female:
        raise ValueError(f"Setting bundle {source} must provide first_names_female when naming rules are defined")
    if has_first_name_rules and not naming.last_names:
        raise ValueError(f"Setting bundle {source} must provide last_names when naming rules are defined")


def _validate_language_features(language: LanguageDefinition, *, source: str) -> None:
    overlap = set(language.consonants) & set(language.vowels)
    if overlap:
        raise ValueError(
            f"Setting bundle {source} has overlapping consonants/vowels in {language.language_key}: "
            f"{', '.join(sorted(overlap))}"
        )
    for feature_name, feature_values, allowed_values in (
        ("front_vowels", language.front_vowels, language.vowels),
        ("back_vowels", language.back_vowels, language.vowels),
        ("liquid_consonants", language.liquid_consonants, language.consonants),
        ("nasal_consonants", language.nasal_consonants, language.consonants),
        ("fricative_consonants", language.fricative_consonants, language.consonants),
        ("stop_consonants", language.stop_consonants, language.consonants),
    ):
        unknown_values = [value for value in feature_values if value not in allowed_values]
        if unknown_values:
            raise ValueError(
                f"Setting bundle {source} has {feature_name} outside the base inventory in "
                f"{language.language_key}: {', '.join(sorted(unknown_values))}"
            )


def _validate_language_sound_change_rules(language: LanguageDefinition, *, source: str) -> None:
    for rule_group_name, rules in (
        ("sound_change_rules", language.sound_change_rules),
        ("evolution_rule_pool", language.evolution_rule_pool),
    ):
        seen_rule_keys: set[str] = set()
        for index, rule in enumerate(rules):
            if not rule.source:
                raise ValueError(
                    f"Setting bundle {source} has empty sound change source in {language.language_key}: "
                    f"{rule_group_name}[{index}]"
                )
            if rule.position not in VALID_SOUND_CHANGE_POSITIONS:
                raise ValueError(
                    f"Setting bundle {source} has invalid sound change position in {language.language_key}: "
                    f"{rule.position}"
                )
            if rule.before not in VALID_SOUND_CHANGE_CONTEXTS or rule.after not in VALID_SOUND_CHANGE_CONTEXTS:
                raise ValueError(
                    f"Setting bundle {source} has invalid sound change context in {language.language_key}: "
                    f"{rule.before}/{rule.after}"
                )
            if rule.rule_key:
                if rule.rule_key in seen_rule_keys:
                    raise ValueError(
                        f"Setting bundle {source} has duplicate sound change rule_key in "
                        f"{language.language_key}: {rule.rule_key}"
                    )
                seen_rule_keys.add(rule.rule_key)


def _validate_language_patterns(language: LanguageDefinition, *, source: str) -> None:
    for pattern_group_name, patterns in (
        ("given_name_patterns", language.given_name_patterns),
        ("surname_patterns", language.surname_patterns),
        ("toponym_patterns", language.toponym_patterns),
    ):
        for pattern in patterns:
            if any(marker not in "RrLXY" for marker in pattern):
                raise ValueError(
                    f"Setting bundle {source} has invalid {pattern_group_name} token in "
                    f"{language.language_key}: {pattern}"
                )
    for template in language.syllable_templates:
        if any(marker not in "CV" for marker in template):
            raise ValueError(
                f"Setting bundle {source} has invalid syllable template in "
                f"{language.language_key}: {template}"
            )


def _validate_language_inheritance(language_index: Dict[str, LanguageDefinition], *, source: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def _visit_language(language_key: str) -> None:
        if language_key in visited:
            return
        if language_key in visiting:
            raise ValueError(f"Setting bundle {source} contains cyclic language inheritance")
        visiting.add(language_key)
        parent_key = language_index[language_key].parent_key
        if parent_key:
            _visit_language(parent_key)
        visiting.remove(language_key)
        visited.add(language_key)

    for language_key in language_index:
        _visit_language(language_key)


def _validate_languages(world: WorldDefinition, *, source: str) -> Dict[str, LanguageDefinition]:
    language_index = {language.language_key: language for language in world.languages}
    for language in world.languages:
        if not language.language_key:
            raise ValueError(f"Setting bundle {source} must define language_key for each language")
        if not language.display_name:
            raise ValueError(f"Setting bundle {source} must define display_name for each language")
        if language.parent_key and language.parent_key not in language_index:
            raise ValueError(
                f"Setting bundle {source} references unknown parent language: {language.parent_key}"
            )
        _validate_language_features(language, source=source)
        if language.evolution_interval_years < 0:
            raise ValueError(
                f"Setting bundle {source} has negative evolution_interval_years in {language.language_key}"
            )
        _validate_language_sound_change_rules(language, source=source)
        _validate_language_patterns(language, source=source)

    _validate_language_inheritance(language_index, source=source)
    return language_index


def _validate_language_communities(
    world: WorldDefinition,
    language_index: Dict[str, LanguageDefinition],
    site_ids: List[str],
    *,
    source: str,
) -> None:
    known_community_races = _known_community_race_names(world)
    for community in world.language_communities:
        if community.language_key not in language_index:
            raise ValueError(
                f"Setting bundle {source} references unknown language community target: {community.language_key}"
            )
        unknown_races = [race for race in community.races if race not in known_community_races]
        if unknown_races:
            raise ValueError(
                f"Setting bundle {source} references unknown community races: {', '.join(unknown_races)}"
            )
        unknown_regions = [
            region for region in community.regions
            if region not in site_ids
        ]
        if unknown_regions:
            raise ValueError(
                f"Setting bundle {source} references unknown community regions: {', '.join(unknown_regions)}"
            )


def _validate_site_language_references(
    world: WorldDefinition,
    language_index: Dict[str, LanguageDefinition],
    *,
    source: str,
) -> None:
    for seed in world.site_seeds:
        if seed.native_name.strip() and not seed.language_key:
            raise ValueError(
                f"Setting bundle {source} site {seed.location_id} defines native_name without language_key"
            )
        if seed.language_key and seed.language_key not in language_index:
            raise ValueError(
                f"Setting bundle {source} references unknown site language: {seed.language_key}"
            )


def _validate_rule_overrides(world: WorldDefinition, *, source: str) -> None:
    event_impact_overrides = {
        str(kind): {str(attr): delta for attr, delta in deltas.items()}
        for kind, deltas in world.event_impact_rules.items()
    }
    try:
        merge_event_impact_rule_overrides(event_impact_overrides)
    except ValueError as exc:
        raise ValueError(f"Setting bundle {source} has invalid world_definition.event_impact_rules: {exc}") from exc

    propagation_overrides = {
        str(section): {str(key): value for key, value in values.items()}
        for section, values in world.propagation_rules.items()
    }
    try:
        merge_propagation_rule_overrides(propagation_overrides)
    except ValueError as exc:
        raise ValueError(f"Setting bundle {source} has invalid world_definition.propagation_rules: {exc}") from exc


def validate_setting_bundle(bundle: SettingBundle, *, source: str) -> None:
    world = bundle.world_definition
    _validate_bundle_identity(bundle, world, source=source)
    _validate_bundle_unique_names(world, source=source)
    site_ids, canonical_ids = _validate_site_seeds(world, source=source)
    _validate_route_seeds(world, canonical_ids, source=source)
    _validate_naming_rules(world, source=source)
    language_index = _validate_languages(world, source=source)
    _validate_language_communities(world, language_index, site_ids, source=source)
    _validate_site_language_references(world, language_index, source=source)
    _validate_rule_overrides(world, source=source)


def bundle_from_dict_validated(data: Dict[str, Any], *, source: str) -> SettingBundle:
    """Construct a SettingBundle and enforce bundle invariants."""
    try:
        bundle = SettingBundle.from_dict(data)
    except KeyError as exc:
        missing = exc.args[0]
        raise ValueError(f"Setting bundle {source} is missing required field: {missing}") from exc
    world_definition_data = data.get("world_definition", {})
    route_seeds_were_present = (
        isinstance(world_definition_data, Mapping)
        and "route_seeds" in world_definition_data
    )
    _backfill_route_seeds_if_missing(
        bundle,
        route_seeds_were_present=route_seeds_were_present,
    )
    validate_setting_bundle(bundle, source=source)
    return bundle


def default_aethoria_bundle(
    *,
    display_name: str | None = None,
    lore_text: str | None = None,
) -> SettingBundle:
    """Return the default bundled Aethoria setting as a mutable copy."""

    bundle = bundle_from_dict_validated(_default_aethoria_bundle_data(), source=str(DEFAULT_AETHORIA_BUNDLE_PATH))
    if display_name is not None:
        bundle.world_definition.display_name = display_name
    if lore_text is not None:
        bundle.world_definition.lore_text = lore_text
    return bundle


def load_setting_bundle(path: str | Path) -> SettingBundle:
    """Load a setting bundle from a JSON file."""

    bundle_path = Path(path)
    try:
        data = json.loads(bundle_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Setting bundle not found: {bundle_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid setting bundle JSON in {bundle_path}: {exc.msg}") from exc
    return bundle_from_dict_validated(data, source=str(bundle_path))

"""Language schema definitions for setting bundles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping

from ..language.schema import (
    SoundChangeRuleDefinition,
    sound_change_rules_from_payload,
)
from .setting_bundle_schema_core import string_list_payload


@dataclass
class LanguageDefinition:
    """Serializable prototype language description for generated naming and vocabulary."""

    language_key: str
    display_name: str
    parent_key: str = ""
    family_key: str = ""
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
            "family_key": self.family_key,
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
            family_key=data.get("family_key", ""),
            seed_syllables=string_list_payload(data.get("seed_syllables", []), field_name="seed_syllables"),
            consonants=string_list_payload(data.get("consonants", []), field_name="consonants"),
            vowels=string_list_payload(data.get("vowels", []), field_name="vowels"),
            front_vowels=string_list_payload(data.get("front_vowels", []), field_name="front_vowels"),
            back_vowels=string_list_payload(data.get("back_vowels", []), field_name="back_vowels"),
            liquid_consonants=string_list_payload(
                data.get("liquid_consonants", []),
                field_name="liquid_consonants",
            ),
            nasal_consonants=string_list_payload(
                data.get("nasal_consonants", []),
                field_name="nasal_consonants",
            ),
            fricative_consonants=string_list_payload(
                data.get("fricative_consonants", []),
                field_name="fricative_consonants",
            ),
            stop_consonants=string_list_payload(
                data.get("stop_consonants", []),
                field_name="stop_consonants",
            ),
            syllable_templates=string_list_payload(
                data.get("syllable_templates", []),
                field_name="syllable_templates",
            ),
            male_suffixes=string_list_payload(data.get("male_suffixes", []), field_name="male_suffixes"),
            female_suffixes=string_list_payload(data.get("female_suffixes", []), field_name="female_suffixes"),
            neutral_suffixes=string_list_payload(data.get("neutral_suffixes", []), field_name="neutral_suffixes"),
            surname_suffixes=string_list_payload(data.get("surname_suffixes", []), field_name="surname_suffixes"),
            name_stems=string_list_payload(data.get("name_stems", []), field_name="name_stems"),
            given_name_patterns=string_list_payload(
                data.get("given_name_patterns", []),
                field_name="given_name_patterns",
            ),
            surname_patterns=string_list_payload(
                data.get("surname_patterns", []),
                field_name="surname_patterns",
            ),
            toponym_stems=string_list_payload(data.get("toponym_stems", []), field_name="toponym_stems"),
            toponym_suffixes=string_list_payload(
                data.get("toponym_suffixes", []),
                field_name="toponym_suffixes",
            ),
            toponym_patterns=string_list_payload(
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
            inspiration_tags=string_list_payload(data.get("inspiration_tags", []), field_name="inspiration_tags"),
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
            races=string_list_payload(data.get("races", []), field_name="races"),
            tribes=string_list_payload(data.get("tribes", []), field_name="tribes"),
            regions=string_list_payload(data.get("regions", []), field_name="regions"),
            priority=int(data.get("priority", 0)),
            is_lingua_franca=bool(data.get("is_lingua_franca", False)),
        )


@dataclass(frozen=True)
class LanguageFamilyDefinition:
    """Authoring/UI grouping for related languages without replacing parent_key lineage."""

    family_key: str
    display_name: str
    proto_language_key: str = ""
    origin_region_ids: List[str] = field(default_factory=list)
    cultural_tags: List[str] = field(default_factory=list)
    phonology_profile_key: str = ""
    naming_profile_key: str = ""
    semantic_domain_tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "family_key": self.family_key,
            "display_name": self.display_name,
            "proto_language_key": self.proto_language_key,
            "origin_region_ids": list(self.origin_region_ids),
            "cultural_tags": list(self.cultural_tags),
            "phonology_profile_key": self.phonology_profile_key,
            "naming_profile_key": self.naming_profile_key,
            "semantic_domain_tags": list(self.semantic_domain_tags),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LanguageFamilyDefinition":
        return cls(
            family_key=data["family_key"],
            display_name=data.get("display_name", data["family_key"]),
            proto_language_key=data.get("proto_language_key", ""),
            origin_region_ids=string_list_payload(data.get("origin_region_ids", []), field_name="origin_region_ids"),
            cultural_tags=string_list_payload(data.get("cultural_tags", []), field_name="cultural_tags"),
            phonology_profile_key=data.get("phonology_profile_key", ""),
            naming_profile_key=data.get("naming_profile_key", ""),
            semantic_domain_tags=string_list_payload(
                data.get("semantic_domain_tags", []),
                field_name="semantic_domain_tags",
            ),
        )


@dataclass(frozen=True)
class SemanticRootDefinition:
    """Shared semantic meaning used by authored or generated toponyms."""

    root_key: str
    meaning_key: str
    gloss_en: str
    gloss_ja: str = ""
    semantic_tags: List[str] = field(default_factory=list)
    allowed_roles: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "root_key": self.root_key,
            "meaning_key": self.meaning_key,
            "gloss_en": self.gloss_en,
            "gloss_ja": self.gloss_ja,
            "semantic_tags": list(self.semantic_tags),
            "allowed_roles": list(self.allowed_roles),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SemanticRootDefinition":
        return cls(
            root_key=data["root_key"],
            meaning_key=data.get("meaning_key", data["root_key"]),
            gloss_en=data.get("gloss_en", data["root_key"]),
            gloss_ja=data.get("gloss_ja", ""),
            semantic_tags=string_list_payload(data.get("semantic_tags", []), field_name="semantic_tags"),
            allowed_roles=string_list_payload(data.get("allowed_roles", []), field_name="allowed_roles"),
        )


@dataclass(frozen=True)
class LanguageRootRealization:
    """Language-specific surface form for one shared semantic root."""

    language_key: str
    root_key: str
    surface: str
    archaic_surface: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language_key": self.language_key,
            "root_key": self.root_key,
            "surface": self.surface,
            "archaic_surface": self.archaic_surface,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LanguageRootRealization":
        return cls(
            language_key=data["language_key"],
            root_key=data["root_key"],
            surface=data["surface"],
            archaic_surface=data.get("archaic_surface", ""),
            notes=data.get("notes", ""),
        )

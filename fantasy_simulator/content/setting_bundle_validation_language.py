"""Language and language-reference validation for setting bundles."""

from __future__ import annotations

from typing import Dict, List

from ..language.schema import VALID_SOUND_CHANGE_CONTEXTS, VALID_SOUND_CHANGE_POSITIONS
from .setting_bundle_schema import LanguageDefinition, WorldDefinition
from .setting_bundle_source import default_aethoria_bundle_data


def known_community_race_names(world: WorldDefinition) -> set[str]:
    """Return race names allowed in language community selectors."""
    known_races = {race.name for race in world.races}
    if world.world_key == "aethoria":
        default_world = default_aethoria_bundle_data().get("world_definition", {})
        for race_data in default_world.get("races", []):
            race_name = str(race_data.get("name", ""))
            if race_name:
                known_races.add(race_name)
    return known_races


def validate_language_features(language: LanguageDefinition, *, source: str) -> None:
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


def validate_language_sound_change_rules(language: LanguageDefinition, *, source: str) -> None:
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


def validate_language_patterns(language: LanguageDefinition, *, source: str) -> None:
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


def validate_language_inheritance(language_index: Dict[str, LanguageDefinition], *, source: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit_language(language_key: str) -> None:
        if language_key in visited:
            return
        if language_key in visiting:
            raise ValueError(f"Setting bundle {source} contains cyclic language inheritance")
        visiting.add(language_key)
        parent_key = language_index[language_key].parent_key
        if parent_key:
            visit_language(parent_key)
        visiting.remove(language_key)
        visited.add(language_key)

    for language_key in language_index:
        visit_language(language_key)


def validate_languages(world: WorldDefinition, *, source: str) -> Dict[str, LanguageDefinition]:
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
        validate_language_features(language, source=source)
        if language.evolution_interval_years < 0:
            raise ValueError(
                f"Setting bundle {source} has negative evolution_interval_years in {language.language_key}"
            )
        validate_language_sound_change_rules(language, source=source)
        validate_language_patterns(language, source=source)

    validate_language_inheritance(language_index, source=source)
    return language_index


def validate_language_communities(
    world: WorldDefinition,
    language_index: Dict[str, LanguageDefinition],
    site_ids: List[str],
    *,
    source: str,
) -> None:
    known_community_races = known_community_race_names(world)
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


def validate_site_language_references(
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

"""Validation helpers and invariants for setting bundles."""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List

from ..language.schema import VALID_SOUND_CHANGE_CONTEXTS, VALID_SOUND_CHANGE_POSITIONS
from .setting_bundle_inspection import setting_entry_key as _setting_entry_key
from .setting_bundle_schema import (
    LanguageDefinition,
    SettingBundle,
    WorldDefinition,
    legacy_location_id_alias,
    merge_event_impact_rule_overrides,
    merge_propagation_rule_overrides,
)
from .setting_bundle_source import default_aethoria_bundle_data


def duplicate_values(items: Iterable[str]) -> List[str]:
    """Return duplicate string values while preserving first duplicate order."""
    seen: set[str] = set()
    duplicates: list[str] = []
    for item in items:
        if item in seen and item not in duplicates:
            duplicates.append(item)
        seen.add(item)
    return duplicates


def validate_named_entries(
    values: List[str],
    *,
    source: str,
    entry_label: str,
    key_label: str | None = None,
    key_resolver: Callable[[str], str] | None = None,
) -> None:
    """Validate blank names, duplicate names, and optional duplicate inspection keys."""
    blank_values = [value for value in values if not value.strip()]
    if blank_values:
        raise ValueError(f"Setting bundle {source} contains blank {entry_label} names")

    duplicate_names = duplicate_values(values)
    if duplicate_names:
        raise ValueError(
            f"Setting bundle {source} contains duplicate {entry_label} names: {', '.join(duplicate_names)}"
        )

    if key_resolver is None:
        return

    duplicate_keys = duplicate_values([key_resolver(value) for value in values])
    if duplicate_keys:
        label = key_label or f"{entry_label} inspection keys"
        raise ValueError(
            f"Setting bundle {source} contains duplicate {label}: {', '.join(duplicate_keys)}"
        )


def _known_community_race_names(world: WorldDefinition) -> set[str]:
    """Return race names allowed in language community selectors."""
    known_races = {race.name for race in world.races}
    if world.world_key == "aethoria":
        default_world = default_aethoria_bundle_data().get("world_definition", {})
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
    validate_named_entries(
        world.cultures,
        source=source,
        entry_label="culture",
        key_label="culture inspection keys",
        key_resolver=_setting_entry_key,
    )
    validate_named_entries(
        world.factions,
        source=source,
        entry_label="faction",
        key_label="faction inspection keys",
        key_resolver=_setting_entry_key,
    )

    blank_glossary_terms = [entry.term for entry in world.glossary if not entry.term.strip()]
    if blank_glossary_terms:
        raise ValueError(f"Setting bundle {source} contains blank glossary terms")

    glossary_terms = [entry.term for entry in world.glossary]
    duplicate_glossary_terms = duplicate_values(glossary_terms)
    if duplicate_glossary_terms:
        raise ValueError(
            f"Setting bundle {source} contains duplicate glossary terms: {', '.join(duplicate_glossary_terms)}"
        )
    duplicate_glossary_keys = duplicate_values([entry.key for entry in world.glossary_entries()])
    if duplicate_glossary_keys:
        raise ValueError(
            f"Setting bundle {source} contains duplicate glossary inspection keys: "
            f"{', '.join(duplicate_glossary_keys)}"
        )

    race_names = [race.name for race in world.races]
    duplicate_races = duplicate_values(race_names)
    if duplicate_races:
        raise ValueError(
            f"Setting bundle {source} contains duplicate race names: {', '.join(duplicate_races)}"
        )

    job_names = [job.name for job in world.jobs]
    duplicate_jobs = duplicate_values(job_names)
    if duplicate_jobs:
        raise ValueError(
            f"Setting bundle {source} contains duplicate job names: {', '.join(duplicate_jobs)}"
        )

    language_keys = [language.language_key for language in world.languages]
    duplicate_language_keys = duplicate_values(language_keys)
    if duplicate_language_keys:
        raise ValueError(
            f"Setting bundle {source} contains duplicate language keys: {', '.join(duplicate_language_keys)}"
        )

    community_keys = [community.community_key for community in world.language_communities]
    duplicate_community_keys = duplicate_values(community_keys)
    if duplicate_community_keys:
        raise ValueError(
            f"Setting bundle {source} contains duplicate language community keys: {', '.join(duplicate_community_keys)}"
        )


def _validate_site_seeds(world: WorldDefinition, *, source: str) -> tuple[List[str], set[str]]:
    site_ids = [seed.location_id for seed in world.site_seeds]
    duplicate_site_ids = duplicate_values(site_ids)
    if duplicate_site_ids:
        raise ValueError(
            f"Setting bundle {source} contains duplicate site seed ids: {', '.join(duplicate_site_ids)}"
        )

    site_names = [seed.name for seed in world.site_seeds]
    duplicate_site_names = duplicate_values(site_names)
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
    duplicate_route_ids = duplicate_values(route_ids)
    if duplicate_route_ids:
        raise ValueError(
            f"Setting bundle {source} contains duplicate route ids: {', '.join(duplicate_route_ids)}"
        )

    route_pairs = [
        tuple(sorted((seed.from_site_id, seed.to_site_id)))
        for seed in world.route_seeds
    ]
    duplicate_route_pairs = duplicate_values([f"{a}->{b}" for a, b in route_pairs])
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

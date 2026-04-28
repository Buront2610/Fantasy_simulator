"""World, topology, and rule override validation for setting bundles."""

from __future__ import annotations

from typing import List

from .setting_bundle_inspection import setting_entry_key as _setting_entry_key
from .setting_bundle_schema import (
    SettingBundle,
    WorldDefinition,
    legacy_location_id_alias,
    merge_event_impact_rule_overrides,
    merge_propagation_rule_overrides,
)
from .setting_bundle_validation_common import duplicate_values, validate_named_entries


def validate_bundle_identity(bundle: SettingBundle, world: WorldDefinition, *, source: str) -> None:
    if bundle.schema_version < 1:
        raise ValueError(f"Setting bundle {source} has invalid schema_version: {bundle.schema_version}")
    if not world.world_key:
        raise ValueError(f"Setting bundle {source} must define world_definition.world_key")
    if not world.display_name:
        raise ValueError(f"Setting bundle {source} must define world_definition.display_name")
    if not world.lore_text:
        raise ValueError(f"Setting bundle {source} must define world_definition.lore_text")


def validate_bundle_unique_names(world: WorldDefinition, *, source: str) -> None:
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


def validate_site_seeds(world: WorldDefinition, *, source: str) -> tuple[List[str], set[str]]:
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

    alias_to_canonical: dict[str, str] = {}
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


def validate_route_seeds(world: WorldDefinition, canonical_ids: set[str], *, source: str) -> None:
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


def validate_naming_rules(world: WorldDefinition, *, source: str) -> None:
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


def validate_rule_overrides(world: WorldDefinition, *, source: str) -> None:
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

"""Validation entry point for setting bundles."""

from __future__ import annotations

from .setting_bundle_schema import SettingBundle
from .setting_bundle_validation_language import (
    validate_language_communities,
    validate_languages,
    validate_site_language_references,
)
from .setting_bundle_validation_world import (
    validate_bundle_identity,
    validate_bundle_unique_names,
    validate_naming_rules,
    validate_route_seeds,
    validate_rule_overrides,
    validate_site_seeds,
)


def validate_setting_bundle(bundle: SettingBundle, *, source: str) -> None:
    world = bundle.world_definition
    validate_bundle_identity(bundle, world, source=source)
    validate_bundle_unique_names(world, source=source)
    site_ids, canonical_ids = validate_site_seeds(world, source=source)
    validate_route_seeds(world, canonical_ids, source=source)
    validate_naming_rules(world, source=source)
    language_index = validate_languages(world, source=source)
    validate_language_communities(world, language_index, site_ids, source=source)
    validate_site_language_references(world, language_index, source=source)
    validate_rule_overrides(world, source=source)

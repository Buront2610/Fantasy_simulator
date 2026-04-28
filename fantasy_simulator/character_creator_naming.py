"""Naming and bundle lookup helpers for character creation."""

from __future__ import annotations

import json
import random
from typing import Any

from .content.setting_bundle import NamingRulesDefinition, SettingBundle
from .language_engine import LanguageEngine


GENDERS = ["Male", "Female", "Non-binary"]


def random_name(gender: str, naming_rules: NamingRulesDefinition, rng: Any = random) -> str:
    """Return a generated full name from resolved naming rules."""
    if gender == "Male":
        first = rng.choice(naming_rules.first_names_male)
    elif gender == "Female":
        first = rng.choice(naming_rules.first_names_female)
    else:
        first = rng.choice(naming_rules.first_names_non_binary)
    last = rng.choice(naming_rules.last_names)
    return f"{first} {last}"


class CharacterCreatorNamingMixin:
    setting_bundle: SettingBundle | None
    _fallback_bundle: SettingBundle | None
    _language_engine: LanguageEngine | None
    _language_engine_signature: str

    def _default_bundle(self) -> SettingBundle:
        raise NotImplementedError

    def _effective_bundle(self) -> SettingBundle:
        """Return the active bundle for race/job/name lookup."""
        return self.setting_bundle if self.setting_bundle is not None else self._default_bundle()

    @property
    def naming_rules(self) -> NamingRulesDefinition:
        default_rules = self._default_bundle().world_definition.naming_rules
        bundle = self._effective_bundle()
        rules = bundle.world_definition.naming_rules
        male = list(rules.first_names_male or default_rules.first_names_male)
        female = list(rules.first_names_female or default_rules.first_names_female)
        non_binary = list(rules.first_names_non_binary or (male + female) or default_rules.first_names_non_binary)
        last_names = list(rules.last_names or default_rules.last_names)
        return NamingRulesDefinition(
            first_names_male=male,
            first_names_female=female,
            first_names_non_binary=non_binary,
            last_names=last_names,
        )

    def naming_rules_for_identity(
        self,
        *,
        race: str | None = None,
        tribe: str | None = None,
        region: str | None = None,
    ) -> NamingRulesDefinition:
        if self._bundle_prefers_explicit_naming_rules():
            return self.naming_rules
        language_rules = self._language_engine_for_bundle().naming_rules_for_identity(
            race=race,
            tribe=tribe,
            region=region,
        )
        if language_rules is not None:
            return language_rules
        return self.naming_rules

    def _bundle_prefers_explicit_naming_rules(self) -> bool:
        """Return whether explicit bundle naming rules should override generated languages."""
        if self.setting_bundle is None:
            return False
        authored = self.setting_bundle.world_definition.naming_rules.to_dict()
        default = self._default_bundle().world_definition.naming_rules.to_dict()
        if authored == default:
            return False
        return any(
            authored.get(field_name)
            for field_name in (
                "first_names_male",
                "first_names_female",
                "first_names_non_binary",
                "last_names",
            )
        )

    def _language_engine_for_bundle(self) -> LanguageEngine:
        bundle = self._effective_bundle()
        signature = json.dumps(
            {
                "languages": [language.to_dict() for language in bundle.world_definition.languages],
                "language_communities": [
                    community.to_dict() for community in bundle.world_definition.language_communities
                ],
            },
            sort_keys=True,
        )
        if self._language_engine is None or self._language_engine_signature != signature:
            self._language_engine = LanguageEngine(bundle.world_definition)
            self._language_engine_signature = signature
        return self._language_engine

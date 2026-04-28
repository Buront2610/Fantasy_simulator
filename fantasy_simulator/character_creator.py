"""
character_creator.py - Interactive and programmatic character creation facade.
"""

from __future__ import annotations

import random
from typing import Any, Optional

from .character import Character
from .character_creator_builders import create_random_character, create_template_character
from .character_creator_catalog import CharacterCreatorCatalogMixin
from .character_creator_interactive import CharacterCreatorInteractiveMixin
from .character_creator_naming import CharacterCreatorNamingMixin
from .content.setting_bundle import SettingBundle, default_aethoria_bundle
from .content.world_data import ALL_SKILLS
from .language_engine import LanguageEngine


class CharacterCreator(
    CharacterCreatorNamingMixin,
    CharacterCreatorCatalogMixin,
    CharacterCreatorInteractiveMixin,
):
    """Factory for creating Character instances."""

    def __init__(self, setting_bundle: SettingBundle | None = None) -> None:
        self.setting_bundle = setting_bundle
        self._fallback_bundle: SettingBundle | None = None
        self._language_engine: LanguageEngine | None = None
        self._language_engine_signature: str = ""

    def _default_bundle(self) -> SettingBundle:
        """Return a cached default bundle snapshot for compatibility fallbacks."""
        if self._fallback_bundle is None:
            self._fallback_bundle = default_aethoria_bundle()
        return self._fallback_bundle

    def _effective_bundle(self) -> SettingBundle:
        """Return the active authoring bundle, falling back to Aethoria."""
        return self.setting_bundle or self._default_bundle()

    def create_random(
        self,
        name: Optional[str] = None,
        rng: Any = random,
        *,
        tribe: str | None = None,
        region: str | None = None,
    ) -> Character:
        race_entries, job_entries = self._require_race_and_job_entries()
        race_entries = self._race_entries_for_context(tribe=tribe, region=region)
        return create_random_character(
            race_entries=race_entries,
            job_entries=job_entries,
            naming_rules_for_identity=self.naming_rules_for_identity,
            extra_skill_pool=ALL_SKILLS,
            name=name,
            rng=rng,
            tribe=tribe,
            region=region,
        )

    def create_from_template(
        self,
        template_name: str,
        name: Optional[str] = None,
        rng: Any = random,
        *,
        tribe: str | None = None,
        region: str | None = None,
    ) -> Character:
        if not self._supports_aethoria_templates():
            raise ValueError("Character templates are only available for Aethoria-compatible bundles")
        return create_template_character(
            template_name=template_name,
            naming_rules_for_identity=self.naming_rules_for_identity,
            name=name,
            rng=rng,
            tribe=tribe,
            region=region,
        )

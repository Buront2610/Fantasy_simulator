"""Profile and toponym helpers for :mod:`fantasy_simulator.language.engine`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..content.setting_bundle import LanguageDefinition, NamingRulesDefinition


@dataclass(frozen=True)
class GeneratedLanguageProfile:
    language_key: str
    display_name: str
    lineage: List[str]
    lexicon: List[str]
    naming_rules: NamingRulesDefinition


class LanguageEngineProfileMixin:
    """Build and cache generated language profiles."""

    _language_index: Dict[str, LanguageDefinition]
    _profile_cache: Dict[str, GeneratedLanguageProfile]
    _toponym_cache: Dict[tuple[str, str, str], str]

    def describe_language_lineage(self, language_key: str) -> List[str]:
        return list(self.profile(language_key).lineage)

    def profile(self, language_key: str) -> GeneratedLanguageProfile:
        cached = self._profile_cache.get(language_key)
        if cached is not None:
            return cached
        language = self._language_index[language_key]
        parent_profile = self.profile(language.parent_key) if language.parent_key else None
        lineage = list(parent_profile.lineage) if parent_profile is not None else []
        lineage.append(language.display_name)
        lexicon = self._build_lexicon(language)
        naming_rules = self._build_naming_rules(language, lexicon)
        profile = GeneratedLanguageProfile(
            language_key=language.language_key,
            display_name=language.display_name,
            lineage=lineage,
            lexicon=lexicon,
            naming_rules=naming_rules,
        )
        self._profile_cache[language_key] = profile
        return profile

    def generate_toponym(
        self,
        language_key: str,
        *,
        seed_key: str,
        region_type: str = "",
    ) -> str:
        cache_key = (language_key, seed_key, region_type)
        cached = self._toponym_cache.get(cache_key)
        if cached is not None:
            return cached
        name = self._name_generator.generate_toponym(
            language_key,
            seed_key=seed_key,
            region_type=region_type,
            lexicon=self.profile(language_key).lexicon,
        )
        self._toponym_cache[cache_key] = name
        return name

    def _build_lexicon(self, language: LanguageDefinition) -> List[str]:
        parent_lexicon = self.profile(language.parent_key).lexicon if language.parent_key else ()
        return self._lexicon_generator.build_lexicon(language, parent_lexicon=parent_lexicon)

    def _build_naming_rules(self, language: LanguageDefinition, lexicon: List[str]) -> NamingRulesDefinition:
        return self._name_generator.build_naming_rules(language, lexicon)

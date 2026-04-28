"""Language generation service with structured phonology and runtime evolution."""

from __future__ import annotations

from typing import Dict, Mapping

from ..content.setting_bundle import (
    LanguageDefinition,
    NamingRulesDefinition,
    WorldDefinition,
)
from .engine_evolution import LanguageEngineEvolutionMixin
from .engine_profiles import GeneratedLanguageProfile, LanguageEngineProfileMixin
from .engine_sound import (
    _FALLBACK_EVOLUTION_TARGETS,
    LanguageEngineSoundMixin,
    fallback_evolution_targets as _fallback_evolution_targets,
)
from .evolution import LanguageEvolutionPlanner
from .lexicon import DEFAULT_CONSONANTS, DEFAULT_VOWELS, LanguageLexiconGenerator
from .naming import LanguageNameGenerator
from .resolver import LanguageResolver
from .state import LanguageRuntimeState


def fallback_evolution_targets() -> Dict[str, list[str]]:
    """Expose fallback drift candidates from the historical engine import path."""
    return _fallback_evolution_targets()


class LanguageEngine(
    LanguageEngineEvolutionMixin,
    LanguageEngineProfileMixin,
    LanguageEngineSoundMixin,
):
    """Generate deterministic naming pools from a world's language tree."""

    def __init__(
        self,
        world_definition: WorldDefinition,
        *,
        runtime_states: Mapping[str, LanguageRuntimeState] | None = None,
    ) -> None:
        self.world_definition = world_definition
        self._language_index = {
            language.language_key: language
            for language in world_definition.languages
        }
        self._runtime_states = dict(runtime_states or {})
        self._resolver = LanguageResolver(world_definition, self._language_index)
        self._name_generator = LanguageNameGenerator(
            self._language_index,
            runtime_state=self.runtime_state,
        )
        self._lexicon_generator = LanguageLexiconGenerator(
            evolve_surface_form=self.evolve_surface_form,
            resolved_list=self._resolved_list,
        )
        self._evolution_planner = LanguageEvolutionPlanner(
            self._language_index,
            fallback_targets=_FALLBACK_EVOLUTION_TARGETS,
            evolve_surface_form=self.evolve_surface_form,
            evolve_surface_form_with_extra_rules=self._evolve_surface_form_with_extra_rules,
            effective_sound_shift_map=self.effective_sound_shift_map,
            resolved_list=self._resolved_list,
            default_consonants=DEFAULT_CONSONANTS,
            default_vowels=DEFAULT_VOWELS,
        )
        self._profile_cache: Dict[str, GeneratedLanguageProfile] = {}
        self._toponym_cache: Dict[tuple[str, str, str], str] = {}

    def has_languages(self) -> bool:
        return bool(self._language_index)

    def resolve_language(
        self,
        *,
        race: str | None = None,
        tribe: str | None = None,
        region: str | None = None,
    ) -> LanguageDefinition | None:
        return self._resolver.resolve_language(race=race, tribe=tribe, region=region)

    def naming_rules_for_identity(
        self,
        *,
        race: str | None = None,
        tribe: str | None = None,
        region: str | None = None,
    ) -> NamingRulesDefinition | None:
        language = self.resolve_language(race=race, tribe=tribe, region=region)
        if language is None:
            return None
        return self.profile(language.language_key).naming_rules

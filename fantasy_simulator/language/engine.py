"""Language generation service with structured phonology and runtime evolution."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Mapping, Sequence

from ..content.setting_bundle import (
    LanguageDefinition,
    NamingRulesDefinition,
    WorldDefinition,
)
from .phonology import default_feature_sets
from .evolution import LanguageEvolutionPlanner
from .lexicon import DEFAULT_CONSONANTS, DEFAULT_VOWELS, LanguageLexiconGenerator
from .naming import LanguageNameGenerator, shorten_stem, tidy_word
from .resolver import LanguageResolver
from .schema import SoundChangeRuleDefinition
from .state import LanguageEvolutionRecord, LanguageRuntimeState
from .surface import SurfaceFormEvolver


_FALLBACK_EVOLUTION_TARGETS: Dict[str, List[str]] = {
    "k": ["ch", "kh"],
    "kh": ["ch", "h"],
    "ch": ["sh", "s"],
    "g": ["gh", "y"],
    "gh": ["y", "w"],
    "t": ["th", "s"],
    "d": ["dh", "z"],
    "dh": ["z", "d"],
    "s": ["sh", "th"],
    "sh": ["s", "ch"],
    "th": ["s", "d"],
    "v": ["w", "f"],
    "r": ["rh", "l"],
    "rh": ["r", "l"],
    "a": ["ae", "e"],
    "e": ["ei", "i"],
    "ei": ["i", "e"],
    "i": ["ie", "e"],
    "ie": ["i", "ye"],
    "o": ["ou", "u"],
    "ou": ["u", "o"],
    "u": ["oo", "o"],
    "oo": ["u", "ou"],
    "ae": ["e", "ai"],
    "ai": ["e", "ae"],
    "ia": ["ya", "ie"],
    "ya": ["ia", "a"],
    "ea": ["e", "ia"],
}


def fallback_evolution_targets() -> Dict[str, List[str]]:
    """Expose fallback drift candidates from a single source of truth."""
    return {source: list(targets) for source, targets in _FALLBACK_EVOLUTION_TARGETS.items()}


@dataclass(frozen=True)
class GeneratedLanguageProfile:
    language_key: str
    display_name: str
    lineage: List[str]
    lexicon: List[str]
    naming_rules: NamingRulesDefinition


class LanguageEngine:
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

    def runtime_state(self, language_key: str) -> LanguageRuntimeState:
        state = self._runtime_states.get(language_key)
        if state is None:
            state = LanguageRuntimeState(language_key=language_key)
            self._runtime_states[language_key] = state
        return state

    def runtime_states_snapshot(self) -> Dict[str, LanguageRuntimeState]:
        return {
            key: LanguageRuntimeState.from_dict(state.to_dict())
            for key, state in self._runtime_states.items()
        }

    def invalidate_caches(self) -> None:
        self._profile_cache = {}
        self._toponym_cache = {}

    def describe_language_lineage(self, language_key: str) -> List[str]:
        return list(self.profile(language_key).lineage)

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

    def evolve_surface_form(self, language_key: str, text: str) -> str:
        return self._evolve_surface_form(language_key, text, include_lineage=True)

    def available_evolution_rules(self, language_key: str) -> List[SoundChangeRuleDefinition]:
        return self._evolution_planner.available_evolution_rules(language_key)

    def effective_sound_shift_map(self, language_key: str) -> Dict[str, str]:
        language = self._language_index[language_key]
        mapping: Dict[str, str] = {}
        if language.parent_key:
            mapping.update(self.effective_sound_shift_map(language.parent_key))
        mapping.update(language.sound_shifts)
        for rule in list(language.sound_change_rules) + list(self.runtime_state(language_key).applied_rules):
            if rule.before or rule.after or rule.position != "any" or not rule.source:
                continue
            mapping[rule.source] = rule.target
        return mapping

    def effective_sound_change_rules(
        self,
        language_key: str,
        *,
        include_lineage: bool = False,
    ) -> List[SoundChangeRuleDefinition]:
        language = self._language_index[language_key]
        rules: List[SoundChangeRuleDefinition] = []
        if include_lineage and language.parent_key:
            rules.extend(self.effective_sound_change_rules(language.parent_key, include_lineage=True))
        rules.extend(self._effective_sound_change_rules(language))
        return rules

    def derive_evolution_record(
        self,
        language_key: str,
        *,
        year: int,
        evolution_history: Sequence[LanguageEvolutionRecord],
    ) -> LanguageEvolutionRecord | None:
        language = self._language_index.get(language_key)
        if language is None:
            return None
        profile = self.profile(language_key)
        runtime_state = self.runtime_state(language_key)
        return self._evolution_planner.derive_evolution_record(
            language_key,
            year=year,
            evolution_history=evolution_history,
            lexicon=profile.lexicon,
            naming_last_names=profile.naming_rules.last_names,
            runtime_state=runtime_state,
        )

    def apply_evolution_record(self, record: LanguageEvolutionRecord) -> bool:
        state = self.runtime_state(record.language_key)
        changed = False
        rule = record.to_rule_definition()
        if rule is not None and not any(existing.rule_key == rule.rule_key for existing in state.applied_rules):
            state.applied_rules.append(rule)
            changed = True
        if record.added_name_stem and record.added_name_stem not in state.derived_name_stems:
            state.derived_name_stems.append(record.added_name_stem)
            changed = True
        if record.added_toponym_suffix and record.added_toponym_suffix not in state.derived_toponym_suffixes:
            state.derived_toponym_suffixes.append(record.added_toponym_suffix)
            changed = True
        if changed:
            self.invalidate_caches()
        return changed

    @staticmethod
    def shorten_stem(value: str, max_length: int = 4) -> str:
        cleaned = "".join(char for char in value.lower() if char.isalpha())
        return shorten_stem(cleaned, max_length=max_length)

    def _evolve_surface_form_with_extra_rules(
        self,
        language_key: str,
        text: str,
        extra_rules: Sequence[SoundChangeRuleDefinition],
    ) -> str:
        return self._evolve_surface_form(
            language_key,
            text,
            include_lineage=True,
            extra_rules=extra_rules,
        )

    def _evolve_surface_form(
        self,
        language_key: str,
        text: str,
        *,
        include_lineage: bool,
        extra_rules: Sequence[SoundChangeRuleDefinition] = (),
    ) -> str:
        language = self._language_index[language_key]
        consonants = self._resolved_list(language, "consonants", DEFAULT_CONSONANTS)
        vowels = self._resolved_list(language, "vowels", DEFAULT_VOWELS)
        rules = self.effective_sound_change_rules(
            language_key,
            include_lineage=include_lineage,
        ) + list(extra_rules)
        evolver = SurfaceFormEvolver(
            consonants=consonants,
            vowels=vowels,
            rules=rules,
            feature_sets=self._feature_sets(language, vowels=vowels, consonants=consonants, rules=rules),
        )
        return tidy_word(evolver.evolve(text))

    def _legacy_rules(self, language: LanguageDefinition) -> List[SoundChangeRuleDefinition]:
        return [
            SoundChangeRuleDefinition(
                rule_key=f"legacy:{language.language_key}:{source}>{target}",
                source=source,
                target=target,
            )
            for source, target in language.sound_shifts.items()
            if source
        ]

    def _effective_sound_change_rules(self, language: LanguageDefinition) -> List[SoundChangeRuleDefinition]:
        runtime_state = self.runtime_state(language.language_key)
        return self._legacy_rules(language) + list(language.sound_change_rules) + list(runtime_state.applied_rules)

    def _feature_sets(
        self,
        language: LanguageDefinition,
        *,
        vowels: Sequence[str],
        consonants: Sequence[str],
        rules: Sequence[SoundChangeRuleDefinition] | None = None,
    ) -> Mapping[str, set[str]]:
        extra_segments = list(language.sound_shifts) + list(language.sound_shifts.values())
        effective_rules = rules if rules is not None else self._effective_sound_change_rules(language)
        for rule in effective_rules:
            extra_segments.extend([rule.source, rule.target])
        for rule in language.evolution_rule_pool:
            extra_segments.extend([rule.source, rule.target])
        feature_sets = dict(
            default_feature_sets(
                vowels=vowels,
                consonants=consonants,
                additional_segments=extra_segments,
            )
        )
        if language.front_vowels:
            feature_sets["front_vowel"] |= {value.lower() for value in language.front_vowels}
        if language.back_vowels:
            feature_sets["back_vowel"] |= {value.lower() for value in language.back_vowels}
        if language.liquid_consonants:
            feature_sets["liquid"] |= {value.lower() for value in language.liquid_consonants}
        if language.nasal_consonants:
            feature_sets["nasal"] |= {value.lower() for value in language.nasal_consonants}
        if language.stop_consonants:
            feature_sets["stop"] |= {value.lower() for value in language.stop_consonants}
        if language.fricative_consonants:
            feature_sets["fricative"] |= {value.lower() for value in language.fricative_consonants}
        return feature_sets

    def _resolved_list(self, language: LanguageDefinition, attribute: str, default: List[str]) -> List[str]:
        values = list(getattr(language, attribute))
        if values:
            return values
        if language.parent_key:
            return self._resolved_list(self._language_index[language.parent_key], attribute, default)
        return list(default)

    def _build_lexicon(self, language: LanguageDefinition) -> List[str]:
        parent_lexicon = self.profile(language.parent_key).lexicon if language.parent_key else ()
        return self._lexicon_generator.build_lexicon(language, parent_lexicon=parent_lexicon)

    def _build_naming_rules(self, language: LanguageDefinition, lexicon: List[str]) -> NamingRulesDefinition:
        return self._name_generator.build_naming_rules(language, lexicon)

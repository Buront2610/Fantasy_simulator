"""Sound-change helpers for :mod:`fantasy_simulator.language.engine`."""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence

from ..content.setting_bundle import LanguageDefinition
from .lexicon import DEFAULT_CONSONANTS, DEFAULT_VOWELS
from .naming import tidy_word
from .phonology import default_feature_sets
from .schema import SoundChangeRuleDefinition
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


class LanguageEngineSoundMixin:
    """Resolve inherited phonology and apply sound-change rules."""

    _language_index: Dict[str, LanguageDefinition]

    def evolve_surface_form(self, language_key: str, text: str) -> str:
        return self._evolve_surface_form(language_key, text, include_lineage=True)

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

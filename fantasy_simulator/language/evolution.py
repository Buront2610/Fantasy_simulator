"""Language evolution planning service."""

from __future__ import annotations

import random
from typing import Callable, Dict, List, Mapping, Sequence

from ..content.setting_bundle import LanguageDefinition
from .naming import shorten_stem, stable_seed
from .presets import PRESET_EVOLUTION_RULES
from .schema import SoundChangeRuleDefinition
from .state import LanguageEvolutionRecord, LanguageRuntimeState


class LanguageEvolutionPlanner:
    """Derive deterministic historical sound-change records."""

    def __init__(
        self,
        language_index: Mapping[str, LanguageDefinition],
        *,
        fallback_targets: Mapping[str, Sequence[str]],
        evolve_surface_form: Callable[[str, str], str],
        evolve_surface_form_with_extra_rules: Callable[[str, str, Sequence[SoundChangeRuleDefinition]], str],
        effective_sound_shift_map: Callable[[str], Dict[str, str]],
        resolved_list: Callable[[LanguageDefinition, str, List[str]], List[str]],
        default_consonants: List[str],
        default_vowels: List[str],
    ) -> None:
        self._language_index = language_index
        self._fallback_targets = {
            source: list(targets) for source, targets in fallback_targets.items()
        }
        self._evolve_surface_form = evolve_surface_form
        self._evolve_surface_form_with_extra_rules = evolve_surface_form_with_extra_rules
        self._effective_sound_shift_map = effective_sound_shift_map
        self._resolved_list = resolved_list
        self._default_consonants = list(default_consonants)
        self._default_vowels = list(default_vowels)

    def available_evolution_rules(self, language_key: str) -> List[SoundChangeRuleDefinition]:
        language = self._language_index[language_key]
        inherited: List[SoundChangeRuleDefinition] = []
        if language.parent_key:
            inherited.extend(self.available_evolution_rules(language.parent_key))
        explicit = inherited + list(language.evolution_rule_pool)
        preset_rules: List[SoundChangeRuleDefinition] = []
        for tag in language.inspiration_tags:
            preset_rules.extend(PRESET_EVOLUTION_RULES.get(tag, []))
        return explicit + preset_rules

    def derive_evolution_record(
        self,
        language_key: str,
        *,
        year: int,
        evolution_history: Sequence[LanguageEvolutionRecord],
        lexicon: Sequence[str],
        naming_last_names: Sequence[str],
        runtime_state: LanguageRuntimeState,
    ) -> LanguageEvolutionRecord | None:
        language = self._language_index.get(language_key)
        if language is None:
            return None
        applied_rule_keys = {
            record.rule_key
            for record in evolution_history
            if record.language_key == language_key and record.rule_key
        }
        candidates = [
            rule
            for rule in self.available_evolution_rules(language_key)
            if rule.source and rule.rule_key not in applied_rule_keys
        ]
        rng = random.Random(stable_seed(language_key, str(year), str(len(evolution_history))))
        sample_forms = (language.seed_syllables or []) + list(lexicon)
        selected_rule = self._select_productive_rule(
            language_key,
            candidates,
            rng=rng,
            sample_forms=sample_forms,
        )
        if selected_rule is None:
            selected_rule = self._fallback_evolution_rule(language, lexicon, rng)
        if selected_rule is None:
            return None

        applied_rule = SoundChangeRuleDefinition(
            rule_key=selected_rule.rule_key,
            source=selected_rule.source,
            target=selected_rule.target,
            before=selected_rule.before,
            after=selected_rule.after,
            position=selected_rule.position,
            description=selected_rule.description,
            weight=selected_rule.weight,
        )
        added_name_stem = self._derive_name_stem(
            language,
            lexicon=lexicon,
            runtime_state=runtime_state,
        )
        added_toponym_suffix = self._derive_toponym_suffix(
            language,
            lexicon=lexicon,
            naming_last_names=naming_last_names,
            runtime_state=runtime_state,
        )

        return LanguageEvolutionRecord(
            year=year,
            language_key=language_key,
            source_token=applied_rule.source,
            target_token=applied_rule.target,
            added_name_stem=added_name_stem,
            added_toponym_suffix=added_toponym_suffix,
            rule_key=applied_rule.rule_key,
            rule_before=applied_rule.before,
            rule_after=applied_rule.after,
            rule_position=applied_rule.position,
            rule_description=applied_rule.description,
        )

    def _derive_name_stem(
        self,
        language: LanguageDefinition,
        *,
        lexicon: Sequence[str],
        runtime_state: LanguageRuntimeState,
    ) -> str:
        stem_candidates = list(
            dict.fromkeys(
                (language.name_stems or [])
                + runtime_state.derived_name_stems
                + list(lexicon)
            )
        )
        for base_name_stem in stem_candidates:
            candidate = shorten_stem(
                self._evolve_surface_form(language.language_key, base_name_stem),
                max_length=4,
            )
            if candidate and candidate not in runtime_state.derived_name_stems and candidate not in language.name_stems:
                return candidate
        return ""

    def _derive_toponym_suffix(
        self,
        language: LanguageDefinition,
        *,
        lexicon: Sequence[str],
        naming_last_names: Sequence[str],
        runtime_state: LanguageRuntimeState,
    ) -> str:
        suffix_candidates = list(
            dict.fromkeys(
                list(language.toponym_suffixes or language.surname_suffixes or naming_last_names)
                + runtime_state.derived_toponym_suffixes
                + list(lexicon)
            )
        )
        for base_suffix in suffix_candidates:
            candidate = shorten_stem(
                self._evolve_surface_form(language.language_key, base_suffix),
                max_length=4,
            )
            if (
                candidate
                and len(candidate) >= 2
                and candidate not in runtime_state.derived_toponym_suffixes
                and candidate not in language.toponym_suffixes
            ):
                return candidate
        return ""

    def _select_productive_rule(
        self,
        language_key: str,
        rules: Sequence[SoundChangeRuleDefinition],
        *,
        rng: random.Random,
        sample_forms: Sequence[str],
    ) -> SoundChangeRuleDefinition | None:
        weighted: List[SoundChangeRuleDefinition] = []
        for rule in rules:
            weighted.extend([rule] * max(1, int(rule.weight)))
        while weighted:
            candidate = rng.choice(weighted)
            weighted = [rule for rule in weighted if rule.rule_key != candidate.rule_key]
            if self._rule_changes_any_form(language_key, candidate, sample_forms):
                return candidate
        return None

    def _fallback_evolution_rule(
        self,
        language: LanguageDefinition,
        sample_forms: Sequence[str],
        rng: random.Random,
    ) -> SoundChangeRuleDefinition | None:
        tokens = list(
            dict.fromkeys(
                self._resolved_list(language, "consonants", self._default_consonants)
                + self._resolved_list(language, "vowels", self._default_vowels)
            )
        )
        effective_map = self._effective_sound_shift_map(language.language_key)
        candidates = [token for token in tokens if token in self._fallback_targets]
        if not candidates:
            return None
        source = rng.choice(candidates)
        targets = [
            target
            for target in self._fallback_targets[source]
            if effective_map.get(source) != target
        ]
        if not targets:
            return None
        target = rng.choice(targets)
        candidate = SoundChangeRuleDefinition(
            rule_key=f"fallback:{language.language_key}:{source}>{target}:{len(effective_map)}",
            source=source,
            target=target,
            description="Fallback phonological drift.",
        )
        if self._rule_changes_any_form(language.language_key, candidate, sample_forms):
            return candidate
        return None

    def _rule_changes_any_form(
        self,
        language_key: str,
        rule: SoundChangeRuleDefinition,
        sample_forms: Sequence[str],
    ) -> bool:
        for form in sample_forms:
            if self._evolve_surface_form_with_extra_rules(
                language_key,
                form,
                [rule],
            ) != self._evolve_surface_form(language_key, form):
                return True
        return False

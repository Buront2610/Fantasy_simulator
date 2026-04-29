"""Runtime evolution helpers for :mod:`fantasy_simulator.language.engine`."""

from __future__ import annotations

from typing import Dict, List, Sequence

from .naming import shorten_stem
from .schema import SoundChangeRuleDefinition
from .state import LanguageEvolutionRecord, LanguageRuntimeState


class LanguageEngineEvolutionMixin:
    """Expose runtime-state snapshots and language evolution operations."""

    _runtime_states: Dict[str, LanguageRuntimeState]

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

    def available_evolution_rules(self, language_key: str) -> List[SoundChangeRuleDefinition]:
        return self._evolution_planner.available_evolution_rules(language_key)

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

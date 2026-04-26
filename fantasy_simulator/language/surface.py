"""Surface-form phonology service."""

from __future__ import annotations

from typing import Mapping, Sequence

from .phonology import apply_sound_change_rules, build_segment_inventory
from .schema import SoundChangeRuleDefinition


class SurfaceFormEvolver:
    """Apply a prepared sound-change pipeline to one surface form."""

    def __init__(
        self,
        *,
        consonants: Sequence[str],
        vowels: Sequence[str],
        rules: Sequence[SoundChangeRuleDefinition],
        feature_sets: Mapping[str, set[str]],
    ) -> None:
        self._rules = list(rules)
        self._inventory = build_segment_inventory(
            consonants,
            vowels,
            [rule.source for rule in self._rules],
            [rule.target for rule in self._rules],
        )
        self._feature_sets = feature_sets

    def evolve(self, text: str) -> str:
        return apply_sound_change_rules(
            text,
            rules=self._rules,
            inventory=self._inventory,
            feature_sets=self._feature_sets,
        )

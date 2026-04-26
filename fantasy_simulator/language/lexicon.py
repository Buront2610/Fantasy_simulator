"""Deterministic lexicon generation for language profiles."""

from __future__ import annotations

import random
from typing import Callable, List, Sequence

from ..content.setting_bundle import LanguageDefinition
from .naming import dedupe_preserve_order, stable_seed


DEFAULT_CONSONANTS = ["b", "d", "f", "g", "k", "l", "m", "n", "r", "s", "t", "th", "v"]
DEFAULT_VOWELS = ["a", "e", "i", "o", "u", "ae", "ia"]
DEFAULT_TEMPLATES = ["CV", "CVC", "VC"]
FALLBACK_LEXICON = ["aran", "sela", "torin"]


class LanguageLexiconGenerator:
    """Build deterministic lexicons from language seeds, inheritance, and phonology."""

    def __init__(
        self,
        evolve_surface_form: Callable[[str, str], str],
        resolved_list: Callable[[LanguageDefinition, str, List[str]], List[str]],
    ) -> None:
        self._evolve_surface_form = evolve_surface_form
        self._resolved_list = resolved_list

    def build_lexicon(
        self,
        language: LanguageDefinition,
        *,
        parent_lexicon: Sequence[str] = (),
    ) -> List[str]:
        seeds = dedupe_preserve_order(language.seed_syllables)
        words: List[str] = []
        if language.parent_key:
            words.extend(
                self._evolve_surface_form(language.language_key, root)
                for root in parent_lexicon
            )
        words.extend(self._evolve_surface_form(language.language_key, seed) for seed in seeds)
        rng = random.Random(stable_seed(language.language_key, "lexicon"))
        attempts = 0
        while len(dedupe_preserve_order(words)) < language.lexicon_size and attempts < language.lexicon_size * 20:
            words.append(self._invent_word(language, rng))
            attempts += 1
        unique_words = dedupe_preserve_order(words)
        if not unique_words:
            unique_words = list(FALLBACK_LEXICON)
        return unique_words[:language.lexicon_size]

    def _make_syllable(
        self,
        rng: random.Random,
        consonants: List[str],
        vowels: List[str],
        templates: List[str],
    ) -> str:
        template = rng.choice(templates)
        chunks: List[str] = []
        for marker in template:
            if marker == "C":
                chunks.append(rng.choice(consonants))
            elif marker == "V":
                chunks.append(rng.choice(vowels))
            else:
                chunks.append(marker.lower())
        return "".join(chunks)

    def _invent_word(self, language: LanguageDefinition, rng: random.Random) -> str:
        consonants = self._resolved_list(language, "consonants", DEFAULT_CONSONANTS)
        vowels = self._resolved_list(language, "vowels", DEFAULT_VOWELS)
        templates = self._resolved_list(language, "syllable_templates", DEFAULT_TEMPLATES)
        syllables = rng.choice((1, 2, 2, 3))
        raw = "".join(self._make_syllable(rng, consonants, vowels, templates) for _ in range(syllables))
        return self._evolve_surface_form(language.language_key, raw)

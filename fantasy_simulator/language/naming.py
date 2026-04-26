"""Generated naming and toponym helpers."""

from __future__ import annotations

import hashlib
import random
from typing import Callable, Iterable, List, Mapping

from ..content.setting_bundle import LanguageDefinition, NamingRulesDefinition
from .state import LanguageRuntimeState


_DEFAULT_VOWELS = ["a", "e", "i", "o", "u", "ae", "ia"]
_DEFAULT_MALE_SUFFIXES = ["an", "or", "ion", "ar"]
_DEFAULT_FEMALE_SUFFIXES = ["a", "eth", "iel", "wen"]
_DEFAULT_NEUTRAL_SUFFIXES = ["en", "ir", "is", "el"]
_DEFAULT_SURNAME_SUFFIXES = ["dor", "ion", "wyn", "mark"]
_DEFAULT_TOPONYM_SUFFIXES = ["al", "eth", "or", "um"]
_DEFAULT_GIVEN_PATTERNS = ["RX", "RLX", "RrX"]
_DEFAULT_SURNAME_PATTERNS = ["RY", "RLY", "RrY"]
_DEFAULT_TOPONYM_PATTERNS = ["RY", "RLY", "RrY"]
_NAME_POOL_SIZE = 18
_MAX_GIVEN_LENGTH = 12
_MAX_SURNAME_LENGTH = 14
_MAX_TOPONYM_LENGTH = 16


def stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    unique: List[str] = []
    for value in values:
        normalized = str(value).strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def tidy_word(text: str) -> str:
    result = text.lower().replace(" ", "")
    for repeated in ("aaa", "eee", "iii", "ooo", "uuu"):
        while repeated in result:
            result = result.replace(repeated, repeated[:2])
    collapsed: List[str] = []
    for char in result:
        if len(collapsed) >= 2 and collapsed[-1] == collapsed[-2] == char:
            continue
        collapsed.append(char)
    return "".join(collapsed)


def format_name(text: str) -> str:
    cleaned = tidy_word(text)
    return cleaned[:1].upper() + cleaned[1:]


def shorten_stem(value: str, max_length: int = 4) -> str:
    cleaned = "".join(char for char in value.lower() if char.isalpha())
    cleaned = cleaned[:max_length]
    if len(cleaned) > 2 and cleaned[-1] == cleaned[-2]:
        cleaned = cleaned[:-1]
    return cleaned


class LanguageNameGenerator:
    """Build deterministic name pools and toponyms for one language tree."""

    def __init__(
        self,
        language_index: Mapping[str, LanguageDefinition],
        *,
        runtime_state: Callable[[str], LanguageRuntimeState],
    ) -> None:
        self._language_index = language_index
        self._runtime_state = runtime_state

    def generate_toponym(
        self,
        language_key: str,
        *,
        seed_key: str,
        region_type: str,
        lexicon: List[str],
    ) -> str:
        language = self._language_index[language_key]
        stems = self.toponym_stems(language, lexicon)
        vowels = self._resolved_list(language, "vowels", _DEFAULT_VOWELS)
        suffixes = self._resolved_list(
            language,
            "toponym_suffixes",
            self._resolved_list(language, "surname_suffixes", _DEFAULT_TOPONYM_SUFFIXES),
        )
        suffixes = dedupe_preserve_order(suffixes + self._runtime_state(language_key).derived_toponym_suffixes)
        patterns = self._resolved_list(language, "toponym_patterns", _DEFAULT_TOPONYM_PATTERNS)
        rng = random.Random(stable_seed(language_key, "toponym", seed_key, region_type))
        return self._generate_patterned_word(
            stems=stems,
            suffixes=suffixes,
            vowels=vowels,
            patterns=patterns,
            rng=rng,
            max_length=_MAX_TOPONYM_LENGTH,
        )

    def build_naming_rules(self, language: LanguageDefinition, lexicon: List[str]) -> NamingRulesDefinition:
        male_suffixes = self._resolved_list(language, "male_suffixes", _DEFAULT_MALE_SUFFIXES)
        female_suffixes = self._resolved_list(language, "female_suffixes", _DEFAULT_FEMALE_SUFFIXES)
        neutral_suffixes = self._resolved_list(language, "neutral_suffixes", _DEFAULT_NEUTRAL_SUFFIXES)
        surname_suffixes = self._resolved_list(language, "surname_suffixes", _DEFAULT_SURNAME_SUFFIXES)
        runtime_state = self._runtime_state(language.language_key)
        surname_suffixes = dedupe_preserve_order(surname_suffixes + runtime_state.derived_toponym_suffixes)
        given_patterns = self._resolved_list(language, "given_name_patterns", _DEFAULT_GIVEN_PATTERNS)
        surname_patterns = self._resolved_list(language, "surname_patterns", _DEFAULT_SURNAME_PATTERNS)
        return NamingRulesDefinition(
            first_names_male=self._build_name_pool(
                language=language,
                lexicon=lexicon,
                patterns=given_patterns,
                suffixes=male_suffixes,
                label="male",
                max_length=_MAX_GIVEN_LENGTH,
            ),
            first_names_female=self._build_name_pool(
                language=language,
                lexicon=lexicon,
                patterns=given_patterns,
                suffixes=female_suffixes,
                label="female",
                max_length=_MAX_GIVEN_LENGTH,
            ),
            first_names_non_binary=self._build_name_pool(
                language=language,
                lexicon=lexicon,
                patterns=given_patterns,
                suffixes=neutral_suffixes,
                label="neutral",
                max_length=_MAX_GIVEN_LENGTH,
            ),
            last_names=self._build_name_pool(
                language=language,
                lexicon=self.toponym_stems(language, lexicon),
                patterns=surname_patterns,
                suffixes=surname_suffixes,
                label="surname",
                max_length=_MAX_SURNAME_LENGTH,
            ),
        )

    def name_stems(self, language: LanguageDefinition, lexicon: List[str]) -> List[str]:
        runtime_state = self._runtime_state(language.language_key)
        explicit = dedupe_preserve_order(language.name_stems + runtime_state.derived_name_stems)
        if explicit:
            return explicit
        seeds = dedupe_preserve_order(language.seed_syllables)
        derived = [
            shorten_stem(seed, max_length=4)
            for seed in seeds + lexicon
        ]
        stems = dedupe_preserve_order([stem for stem in derived if stem])
        if stems:
            return stems
        return ["ar", "el", "tor"]

    def toponym_stems(self, language: LanguageDefinition, lexicon: List[str]) -> List[str]:
        explicit = dedupe_preserve_order(language.toponym_stems)
        if explicit:
            return explicit
        return self.name_stems(language, lexicon)

    def _resolved_list(self, language: LanguageDefinition, attribute: str, default: List[str]) -> List[str]:
        values = list(getattr(language, attribute))
        if values:
            return values
        if language.parent_key:
            return self._resolved_list(self._language_index[language.parent_key], attribute, default)
        return list(default)

    @staticmethod
    def _join_chunks(chunks: List[str]) -> str:
        result = ""
        for chunk in chunks:
            if not chunk:
                continue
            if not result:
                result = chunk
                continue
            if result[-1] == chunk[0]:
                result += chunk[1:]
            elif result[-1] in "aeiou" and chunk[0] in "aeiou":
                result += chunk[1:]
            else:
                result += chunk
        return tidy_word(result)

    @staticmethod
    def _stem_variant(stem: str, short: bool) -> str:
        if not short:
            return stem
        return shorten_stem(stem, max_length=3) or stem[:3]

    def _render_pattern(
        self,
        pattern: str,
        *,
        stems: List[str],
        suffixes: List[str],
        vowels: List[str],
        rng: random.Random,
    ) -> str:
        primary = rng.choice(stems)
        secondary = rng.choice([stem for stem in stems if stem != primary] or stems)
        chunks: List[str] = []
        for marker in pattern:
            if marker == "R":
                chunks.append(self._stem_variant(primary, short=False))
            elif marker == "r":
                chunks.append(self._stem_variant(secondary, short=True))
            elif marker == "L":
                chunks.append(rng.choice(vowels))
            elif marker in {"X", "Y"}:
                chunks.append(rng.choice(suffixes))
        return self._join_chunks(chunks)

    @staticmethod
    def _is_pleasant_word(word: str, *, max_length: int) -> bool:
        if not 3 <= len(word) <= max_length:
            return False
        if len(word) >= 4 and word[-4:-2] == word[-2:]:
            return False
        if any(word[index:index + 2] == word[index + 2:index + 4] for index in range(len(word) - 3)):
            return False
        return True

    def _generate_patterned_word(
        self,
        *,
        stems: List[str],
        suffixes: List[str],
        vowels: List[str],
        patterns: List[str],
        rng: random.Random,
        max_length: int,
    ) -> str:
        attempts = 0
        while attempts < 80:
            rendered = self._render_pattern(
                rng.choice(patterns),
                stems=stems,
                suffixes=suffixes,
                vowels=vowels,
                rng=rng,
            )
            attempts += 1
            if self._is_pleasant_word(rendered, max_length=max_length):
                return format_name(rendered)
        fallback = self._join_chunks([rng.choice(stems), rng.choice(suffixes or [""])]).strip()
        return format_name(fallback[:max_length])

    def _build_name_pool(
        self,
        *,
        language: LanguageDefinition,
        lexicon: List[str],
        patterns: List[str],
        suffixes: List[str],
        label: str,
        max_length: int,
    ) -> List[str]:
        rng = random.Random(stable_seed(language.language_key, label))
        stems = self.name_stems(language, lexicon)
        vowels = self._resolved_list(language, "vowels", _DEFAULT_VOWELS)
        names: List[str] = []
        attempts = 0
        while len(names) < _NAME_POOL_SIZE and attempts < _NAME_POOL_SIZE * 40:
            candidate = self._generate_patterned_word(
                stems=stems,
                suffixes=suffixes,
                vowels=vowels,
                patterns=patterns,
                rng=rng,
                max_length=max_length,
            )
            attempts += 1
            if candidate not in names:
                names.append(candidate)
        if not names:
            names.append(
                self._generate_patterned_word(
                    stems=stems or ["ar"],
                    suffixes=suffixes or ["an"],
                    vowels=vowels or ["a"],
                    patterns=patterns or ["RX"],
                    rng=rng,
                    max_length=max_length,
                )
            )
        return names

"""Language generation service with structured phonology and runtime evolution."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Dict, Iterable, List, Mapping, Sequence

from ..content.setting_bundle import (
    LanguageCommunityDefinition,
    LanguageDefinition,
    NamingRulesDefinition,
    WorldDefinition,
)
from .phonology import apply_sound_change_rules, build_segment_inventory, default_feature_sets
from .presets import PRESET_EVOLUTION_RULES
from .schema import SoundChangeRuleDefinition
from .state import LanguageEvolutionRecord, LanguageRuntimeState


_DEFAULT_CONSONANTS = ["b", "d", "f", "g", "k", "l", "m", "n", "r", "s", "t", "th", "v"]
_DEFAULT_VOWELS = ["a", "e", "i", "o", "u", "ae", "ia"]
_DEFAULT_TEMPLATES = ["CV", "CVC", "VC"]
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


def _stable_seed(*parts: str) -> int:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    unique: List[str] = []
    for value in values:
        normalized = str(value).strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _tidy_word(text: str) -> str:
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


def _format_name(text: str) -> str:
    cleaned = _tidy_word(text)
    return cleaned[:1].upper() + cleaned[1:]


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
        best_match: LanguageCommunityDefinition | None = None
        best_rank = (-1, -1)
        for community in self.world_definition.language_communities:
            matched_dimensions = 0
            selector_count = 0
            if community.races:
                selector_count += 1
                if race not in community.races:
                    continue
                matched_dimensions += 1
            if community.tribes:
                selector_count += 1
                if tribe not in community.tribes:
                    continue
                matched_dimensions += 1
            if community.regions:
                selector_count += 1
                if region not in community.regions:
                    continue
                matched_dimensions += 1
            if selector_count == 0 and not community.is_lingua_franca:
                continue
            rank = (matched_dimensions, community.priority)
            if rank > best_rank:
                best_rank = rank
                best_match = community

        if best_match is not None:
            return self._language_index.get(best_match.language_key)

        if race is not None or tribe is not None or region is not None:
            return None

        lingua_francas = [
            community
            for community in self.world_definition.language_communities
            if community.is_lingua_franca
        ]
        if lingua_francas:
            lingua_franca = max(lingua_francas, key=lambda community: community.priority)
            return self._language_index.get(lingua_franca.language_key)

        if len(self.world_definition.languages) == 1:
            return self.world_definition.languages[0]
        return None

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
        language = self._language_index[language_key]
        lexicon = self.profile(language_key).lexicon
        stems = self._toponym_stems(language, lexicon)
        vowels = self._resolved_list(language, "vowels", _DEFAULT_VOWELS)
        suffixes = self._resolved_list(
            language,
            "toponym_suffixes",
            self._resolved_list(language, "surname_suffixes", _DEFAULT_TOPONYM_SUFFIXES),
        )
        suffixes = _dedupe_preserve_order(suffixes + self.runtime_state(language_key).derived_toponym_suffixes)
        patterns = self._resolved_list(language, "toponym_patterns", _DEFAULT_TOPONYM_PATTERNS)
        rng = random.Random(_stable_seed(language_key, "toponym", seed_key, region_type))
        name = self._generate_patterned_word(
            stems=stems,
            suffixes=suffixes,
            vowels=vowels,
            patterns=patterns,
            rng=rng,
            max_length=_MAX_TOPONYM_LENGTH,
        )
        self._toponym_cache[cache_key] = name
        return name

    def evolve_surface_form(self, language_key: str, text: str) -> str:
        language = self._language_index[language_key]
        consonants = self._resolved_list(language, "consonants", _DEFAULT_CONSONANTS)
        vowels = self._resolved_list(language, "vowels", _DEFAULT_VOWELS)
        rules = self._effective_sound_change_rules(language)
        inventory = build_segment_inventory(
            consonants,
            vowels,
            [rule.source for rule in rules],
            [rule.target for rule in rules],
        )
        feature_sets = self._feature_sets(language, vowels=vowels, consonants=consonants)
        return _tidy_word(
            apply_sound_change_rules(
                text,
                rules=rules,
                inventory=inventory,
                feature_sets=feature_sets,
            )
        )

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

    def effective_sound_shift_map(self, language_key: str) -> Dict[str, str]:
        language = self._language_index[language_key]
        mapping = dict(language.sound_shifts)
        for rule in list(language.sound_change_rules) + list(self.runtime_state(language_key).applied_rules):
            if rule.before or rule.after or rule.position != "any" or not rule.source:
                continue
            mapping[rule.source] = rule.target
        return mapping

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
        rng = random.Random(_stable_seed(language_key, str(year), str(len(evolution_history))))
        selected_rule = self._select_productive_rule(
            language_key,
            candidates,
            rng=rng,
            sample_forms=(language.seed_syllables or []) + profile.lexicon,
        )
        if selected_rule is None:
            selected_rule = self._fallback_evolution_rule(language, profile.lexicon, rng)
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
        added_name_stem = ""
        stem_candidates = list(
            dict.fromkeys(
                (language.name_stems or [])
                + runtime_state.derived_name_stems
                + profile.lexicon
            )
        )
        for base_name_stem in stem_candidates:
            candidate = self.shorten_stem(self.evolve_surface_form(language_key, base_name_stem), max_length=4)
            if candidate and candidate not in runtime_state.derived_name_stems and candidate not in language.name_stems:
                added_name_stem = candidate
                break

        added_toponym_suffix = ""
        suffix_candidates = list(
            dict.fromkeys(
                list(language.toponym_suffixes or language.surname_suffixes or profile.naming_rules.last_names)
                + runtime_state.derived_toponym_suffixes
                + profile.lexicon
            )
        )
        for base_suffix in suffix_candidates:
            candidate = self.shorten_stem(self.evolve_surface_form(language_key, base_suffix), max_length=4)
            if (
                candidate
                and len(candidate) >= 2
                and candidate not in runtime_state.derived_toponym_suffixes
                and candidate not in language.toponym_suffixes
            ):
                added_toponym_suffix = candidate
                break

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
        cleaned = cleaned[:max_length]
        if len(cleaned) > 2 and cleaned[-1] == cleaned[-2]:
            cleaned = cleaned[:-1]
        return cleaned

    @staticmethod
    def _weighted_choice(
        rules: Sequence[SoundChangeRuleDefinition],
        rng: random.Random,
    ) -> SoundChangeRuleDefinition | None:
        if not rules:
            return None
        weighted: List[SoundChangeRuleDefinition] = []
        for rule in rules:
            weighted.extend([rule] * max(1, int(rule.weight)))
        return rng.choice(weighted)

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
                self._resolved_list(language, "consonants", _DEFAULT_CONSONANTS)
                + self._resolved_list(language, "vowels", _DEFAULT_VOWELS)
            )
        )
        effective_map = self.effective_sound_shift_map(language.language_key)
        candidates = [token for token in tokens if token in _FALLBACK_EVOLUTION_TARGETS]
        if not candidates:
            return None
        source = rng.choice(candidates)
        targets = [
            target
            for target in _FALLBACK_EVOLUTION_TARGETS[source]
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
            if self._evolve_surface_form_with_extra_rules(language_key, form, [rule]) != self.evolve_surface_form(
                language_key,
                form,
            ):
                return True
        return False

    def _evolve_surface_form_with_extra_rules(
        self,
        language_key: str,
        text: str,
        extra_rules: Sequence[SoundChangeRuleDefinition],
    ) -> str:
        language = self._language_index[language_key]
        consonants = self._resolved_list(language, "consonants", _DEFAULT_CONSONANTS)
        vowels = self._resolved_list(language, "vowels", _DEFAULT_VOWELS)
        rules = self._effective_sound_change_rules(language) + list(extra_rules)
        inventory = build_segment_inventory(
            consonants,
            vowels,
            [rule.source for rule in rules],
            [rule.target for rule in rules],
        )
        feature_sets = self._feature_sets(language, vowels=vowels, consonants=consonants)
        return _tidy_word(
            apply_sound_change_rules(
                text,
                rules=rules,
                inventory=inventory,
                feature_sets=feature_sets,
            )
        )

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
    ) -> Mapping[str, set[str]]:
        extra_segments = list(language.sound_shifts) + list(language.sound_shifts.values())
        for rule in self._effective_sound_change_rules(language):
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
        consonants = self._resolved_list(language, "consonants", _DEFAULT_CONSONANTS)
        vowels = self._resolved_list(language, "vowels", _DEFAULT_VOWELS)
        templates = self._resolved_list(language, "syllable_templates", _DEFAULT_TEMPLATES)
        syllables = rng.choice((1, 2, 2, 3))
        raw = "".join(self._make_syllable(rng, consonants, vowels, templates) for _ in range(syllables))
        return self.evolve_surface_form(language.language_key, raw)

    def _build_lexicon(self, language: LanguageDefinition) -> List[str]:
        seeds = _dedupe_preserve_order(language.seed_syllables)
        words: List[str] = []
        if language.parent_key:
            parent_profile = self.profile(language.parent_key)
            words.extend(self.evolve_surface_form(language.language_key, root) for root in parent_profile.lexicon)
        words.extend(self.evolve_surface_form(language.language_key, seed) for seed in seeds)
        rng = random.Random(_stable_seed(language.language_key, "lexicon"))
        attempts = 0
        while len(_dedupe_preserve_order(words)) < language.lexicon_size and attempts < language.lexicon_size * 20:
            words.append(self._invent_word(language, rng))
            attempts += 1
        unique_words = _dedupe_preserve_order(words)
        if not unique_words:
            unique_words = ["aran", "sela", "torin"]
        return unique_words[:language.lexicon_size]

    def _name_stems(self, language: LanguageDefinition, lexicon: List[str]) -> List[str]:
        runtime_state = self.runtime_state(language.language_key)
        explicit = _dedupe_preserve_order(language.name_stems + runtime_state.derived_name_stems)
        if explicit:
            return explicit
        seeds = _dedupe_preserve_order(language.seed_syllables)
        derived = [
            self.shorten_stem(seed, max_length=4)
            for seed in seeds + lexicon
        ]
        stems = _dedupe_preserve_order([stem for stem in derived if stem])
        if stems:
            return stems
        return ["ar", "el", "tor"]

    def _toponym_stems(self, language: LanguageDefinition, lexicon: List[str]) -> List[str]:
        explicit = _dedupe_preserve_order(language.toponym_stems)
        if explicit:
            return explicit
        return self._name_stems(language, lexicon)

    def _join_chunks(self, chunks: List[str]) -> str:
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
        return _tidy_word(result)

    def _stem_variant(self, stem: str, short: bool) -> str:
        if not short:
            return stem
        return self.shorten_stem(stem, max_length=3) or stem[:3]

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
                return _format_name(rendered)
        fallback = self._join_chunks([rng.choice(stems), rng.choice(suffixes or [""])]).strip()
        return _format_name(fallback[:max_length])

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
        rng = random.Random(_stable_seed(language.language_key, label))
        stems = self._name_stems(language, lexicon)
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

    def _build_naming_rules(self, language: LanguageDefinition, lexicon: List[str]) -> NamingRulesDefinition:
        male_suffixes = self._resolved_list(language, "male_suffixes", _DEFAULT_MALE_SUFFIXES)
        female_suffixes = self._resolved_list(language, "female_suffixes", _DEFAULT_FEMALE_SUFFIXES)
        neutral_suffixes = self._resolved_list(language, "neutral_suffixes", _DEFAULT_NEUTRAL_SUFFIXES)
        surname_suffixes = self._resolved_list(language, "surname_suffixes", _DEFAULT_SURNAME_SUFFIXES)
        runtime_state = self.runtime_state(language.language_key)
        surname_suffixes = _dedupe_preserve_order(surname_suffixes + runtime_state.derived_toponym_suffixes)
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
                lexicon=self._toponym_stems(language, lexicon),
                patterns=surname_patterns,
                suffixes=surname_suffixes,
                label="surname",
                max_length=_MAX_SURNAME_LENGTH,
            ),
        )

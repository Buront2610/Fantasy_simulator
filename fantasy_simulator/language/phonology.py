"""Tokenization and conditional sound change helpers."""

from __future__ import annotations

from typing import Iterable, List, Mapping, Sequence

from .schema import SoundChangeRuleDefinition


_FRONT_VOWEL_HINTS = ("e", "i", "y", "ae", "ie", "ei")
_BACK_VOWEL_HINTS = ("a", "o", "u", "ou", "oo", "ia")
_LIQUID_HINTS = ("l", "r", "rh")
_NASAL_HINTS = ("m", "n", "ng")
_STOP_HINTS = ("p", "b", "t", "d", "k", "g", "q", "c")
_FRICATIVE_HINTS = ("f", "v", "s", "z", "sh", "th", "dh", "gh", "h", "ch")


def build_segment_inventory(*segment_groups: Iterable[str]) -> List[str]:
    segments: List[str] = []
    seen: set[str] = set()
    for group in segment_groups:
        for raw_segment in group:
            segment = str(raw_segment).lower()
            if not segment or segment in seen:
                continue
            seen.add(segment)
            segments.append(segment)
    segments.sort(key=len, reverse=True)
    return segments


def tokenize_sequence(text: str, inventory: Sequence[str]) -> List[str]:
    lowered = text.lower()
    tokens: List[str] = []
    index = 0
    while index < len(lowered):
        matched = ""
        for segment in inventory:
            if lowered.startswith(segment, index):
                matched = segment
                break
        if matched:
            tokens.append(matched)
            index += len(matched)
        else:
            tokens.append(lowered[index])
            index += 1
    return tokens


def untokenize(tokens: Sequence[str]) -> str:
    return "".join(tokens)


def _matches_descriptor(token: str | None, descriptor: str, feature_sets: Mapping[str, set[str]]) -> bool:
    if descriptor in {"", "any"}:
        return True
    if descriptor == "boundary":
        return token is None
    if token is None:
        return False
    if descriptor == "vowel":
        return token in feature_sets["vowel"]
    if descriptor == "front_vowel":
        return token in feature_sets["front_vowel"]
    if descriptor == "back_vowel":
        return token in feature_sets["back_vowel"]
    if descriptor == "consonant":
        return token in feature_sets["consonant"]
    if descriptor == "liquid":
        return token in feature_sets["liquid"]
    if descriptor == "nasal":
        return token in feature_sets["nasal"]
    if descriptor == "stop":
        return token in feature_sets["stop"]
    if descriptor == "fricative":
        return token in feature_sets["fricative"]
    return False


def _matches_position(position: str, *, start: int, end: int, token_count: int) -> bool:
    if position == "any":
        return True
    if position == "initial":
        return start == 0
    if position == "final":
        return end == token_count
    if position == "medial":
        return start > 0 and end < token_count
    return False


def _apply_rule_once(
    tokens: List[str],
    *,
    rule: SoundChangeRuleDefinition,
    inventory: Sequence[str],
    feature_sets: Mapping[str, set[str]],
) -> List[str]:
    source_tokens = tokenize_sequence(rule.source, inventory)
    target_tokens = tokenize_sequence(rule.target, inventory) if rule.target else []
    if not source_tokens:
        return list(tokens)

    transformed: List[str] = []
    index = 0
    while index < len(tokens):
        end = index + len(source_tokens)
        window = tokens[index:end]
        if window != source_tokens:
            transformed.append(tokens[index])
            index += 1
            continue
        previous_token = tokens[index - 1] if index > 0 else None
        next_token = tokens[end] if end < len(tokens) else None
        if (
            _matches_position(rule.position, start=index, end=end, token_count=len(tokens))
            and _matches_descriptor(previous_token, rule.before, feature_sets)
            and _matches_descriptor(next_token, rule.after, feature_sets)
        ):
            transformed.extend(target_tokens)
            index = end
            continue
        transformed.append(tokens[index])
        index += 1
    return transformed


def apply_sound_change_rules(
    text: str,
    *,
    rules: Sequence[SoundChangeRuleDefinition],
    inventory: Sequence[str],
    feature_sets: Mapping[str, set[str]],
    max_passes: int = 12,
) -> str:
    tokens = tokenize_sequence(text, inventory)
    seen: set[tuple[str, ...]] = set()
    passes = 0
    while tuple(tokens) not in seen and passes < max_passes:
        seen.add(tuple(tokens))
        updated = list(tokens)
        for rule in rules:
            updated = _apply_rule_once(
                updated,
                rule=rule,
                inventory=inventory,
                feature_sets=feature_sets,
            )
        if updated == tokens:
            break
        tokens = updated
        passes += 1
    return untokenize(tokens)


def _classify_additional_segment(feature_sets: dict[str, set[str]], token: str) -> None:
    if any(token.startswith(hint) or hint in token for hint in _FRONT_VOWEL_HINTS + _BACK_VOWEL_HINTS):
        feature_sets["vowel"].add(token)
        if any(token.startswith(hint) or hint in token for hint in _FRONT_VOWEL_HINTS):
            feature_sets["front_vowel"].add(token)
        if any(token.startswith(hint) or hint in token for hint in _BACK_VOWEL_HINTS):
            feature_sets["back_vowel"].add(token)
        return
    if any(hint in token for hint in _LIQUID_HINTS):
        feature_sets["consonant"].add(token)
        feature_sets["liquid"].add(token)
    if any(hint in token for hint in _NASAL_HINTS):
        feature_sets["consonant"].add(token)
        feature_sets["nasal"].add(token)
    if any(token.startswith(hint) for hint in _STOP_HINTS):
        feature_sets["consonant"].add(token)
        feature_sets["stop"].add(token)
    if any(token.startswith(hint) or hint in token for hint in _FRICATIVE_HINTS):
        feature_sets["consonant"].add(token)
        feature_sets["fricative"].add(token)


def default_feature_sets(
    *,
    vowels: Sequence[str],
    consonants: Sequence[str],
    additional_segments: Iterable[str] = (),
) -> Mapping[str, set[str]]:
    vowel_set = {value.lower() for value in vowels}
    consonant_set = {value.lower() for value in consonants}
    feature_sets = {
        "vowel": vowel_set,
        "front_vowel": {
            token for token in vowel_set
            if any(token.startswith(hint) or hint in token for hint in _FRONT_VOWEL_HINTS)
        },
        "back_vowel": {
            token for token in vowel_set
            if any(token.startswith(hint) or hint in token for hint in _BACK_VOWEL_HINTS)
        },
        "consonant": consonant_set,
        "liquid": {
            token for token in consonant_set
            if any(hint in token for hint in _LIQUID_HINTS)
        },
        "nasal": {
            token for token in consonant_set
            if any(hint in token for hint in _NASAL_HINTS)
        },
        "stop": {
            token for token in consonant_set
            if any(token.startswith(hint) for hint in _STOP_HINTS)
        },
        "fricative": {
            token for token in consonant_set
            if any(token.startswith(hint) or hint in token for hint in _FRICATIVE_HINTS)
        },
    }
    for segment in additional_segments:
        normalized = str(segment).lower()
        if normalized:
            _classify_additional_segment(feature_sets, normalized)
    return feature_sets

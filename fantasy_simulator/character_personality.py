"""Personality profiles and relationship affinity helpers."""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any, Mapping

from .i18n import tr


PERSONALITY_TRAITS: tuple[str, ...] = (
    "openness",
    "discipline",
    "extraversion",
    "agreeableness",
    "stability",
)
DEFAULT_PERSONALITY_SCORE = 50


@dataclass(frozen=True)
class PersonalityAffinity:
    score: int
    factor_keys: tuple[str, ...]


@dataclass(frozen=True)
class PersonalityContext:
    profile: dict[str, int]
    factor_keys: tuple[str, ...] = ()
    cause_event_ids: tuple[str, ...] = ()


def clamp_personality_score(value: Any) -> int:
    return max(0, min(100, int(value)))


def neutral_personality() -> dict[str, int]:
    return {trait: DEFAULT_PERSONALITY_SCORE for trait in PERSONALITY_TRAITS}


def normalize_personality(payload: Mapping[str, Any] | None) -> dict[str, int]:
    if payload is None:
        return neutral_personality()
    if not isinstance(payload, Mapping):
        raise ValueError("personality must be a mapping")
    normalized = neutral_personality()
    for trait, value in payload.items():
        if trait not in PERSONALITY_TRAITS:
            raise ValueError(f"unknown personality trait: {trait}")
        normalized[str(trait)] = clamp_personality_score(value)
    return normalized


def generate_personality(rng: Any = random) -> dict[str, int]:
    return {
        trait: clamp_personality_score(round(rng.triangular(10, 90, 50)))
        for trait in PERSONALITY_TRAITS
    }


def generate_personality_for_character(character: Any) -> dict[str, int]:
    rng = random.Random(_personality_seed(character))
    return generate_personality(rng)


def personality_context_from_events(
    character: Any,
    event_records: Any,
    *,
    limit: int = 6,
) -> PersonalityContext:
    """Return how recent experiences color a character's current temperament."""
    profile = normalize_personality(getattr(character, "personality", None))
    char_id = getattr(character, "char_id", "")
    if not char_id:
        return PersonalityContext(profile=profile)

    deltas = {trait: 0 for trait in PERSONALITY_TRAITS}
    factor_keys: list[str] = []
    cause_event_ids: list[str] = []
    considered = 0
    for record in reversed(list(event_records or [])):
        actor_ids = set(getattr(record, "secondary_actor_ids", []))
        primary_actor_id = getattr(record, "primary_actor_id", None)
        if isinstance(primary_actor_id, str) and primary_actor_id:
            actor_ids.add(primary_actor_id)
        if char_id not in actor_ids:
            continue
        considered += 1
        _apply_personality_context_record(character, record, deltas, factor_keys)
        record_id = getattr(record, "record_id", "")
        if isinstance(record_id, str) and record_id:
            cause_event_ids.append(record_id)
        if considered >= limit:
            break

    if not factor_keys:
        return PersonalityContext(profile=profile)
    adjusted = {
        trait: clamp_personality_score(profile[trait] + max(-12, min(12, deltas[trait])))
        for trait in PERSONALITY_TRAITS
    }
    return PersonalityContext(
        profile=adjusted,
        factor_keys=tuple(dict.fromkeys(factor_keys)),
        cause_event_ids=tuple(dict.fromkeys(cause_event_ids)),
    )


def personality_affinity(first: Mapping[str, int], second: Mapping[str, int]) -> PersonalityAffinity:
    first_profile = normalize_personality(first)
    second_profile = normalize_personality(second)
    if first_profile == neutral_personality() and second_profile == neutral_personality():
        return PersonalityAffinity(score=0, factor_keys=("balanced",))
    average_gap = sum(abs(first_profile[trait] - second_profile[trait]) for trait in PERSONALITY_TRAITS) / len(
        PERSONALITY_TRAITS
    )
    score = round((55 - average_gap) / 5)
    score += round((_average_trait(first_profile, second_profile, "agreeableness") - 50) / 15)
    score += round((_average_trait(first_profile, second_profile, "stability") - 50) / 25)
    if abs(first_profile["extraversion"] - second_profile["extraversion"]) >= 45:
        score -= 3
    if abs(first_profile["openness"] - second_profile["openness"]) >= 45:
        score -= 2
    return PersonalityAffinity(
        score=max(-15, min(15, score)),
        factor_keys=tuple(_affinity_factor_keys(first_profile, second_profile, average_gap)),
    )


def relationship_delta_from_personality(first: Mapping[str, int], second: Mapping[str, int]) -> int:
    return round(personality_affinity(first, second).score / 2)


def romance_delta_from_personality(first: Mapping[str, int], second: Mapping[str, int]) -> int:
    return max(-6, min(8, round(personality_affinity(first, second).score / 2)))


def marriage_threshold_adjustment(first: Mapping[str, int], second: Mapping[str, int]) -> int:
    score = personality_affinity(first, second).score
    if score >= 8:
        return -5
    if score <= -8:
        return 8
    return 0


def render_personality_summary(personality: Mapping[str, int]) -> str:
    profile = normalize_personality(personality)
    parts = [
        tr(f"personality_trait_{trait}", value=profile[trait], level=tr(_personality_level_key(profile[trait])))
        for trait in PERSONALITY_TRAITS
    ]
    return tr("personality_summary", traits=" / ".join(parts))


def render_affinity_factors(factor_keys: tuple[str, ...]) -> str:
    return ", ".join(tr(f"personality_affinity_{key}") for key in factor_keys)


def render_personality_context_factors(factor_keys: tuple[str, ...]) -> str:
    return ", ".join(tr(f"personality_context_{key}") for key in factor_keys)


def _average_trait(first: Mapping[str, int], second: Mapping[str, int], trait: str) -> float:
    return (first[trait] + second[trait]) / 2


def _personality_seed(character: Any) -> int:
    parts = (
        str(getattr(character, "name", "")),
        str(getattr(character, "gender", "")),
        str(getattr(character, "race", "")),
        str(getattr(character, "job", "")),
        str(getattr(character, "age", "")),
    )
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _affinity_factor_keys(first: Mapping[str, int], second: Mapping[str, int], average_gap: float) -> list[str]:
    factors: list[str] = []
    if _average_trait(first, second, "agreeableness") >= 65:
        factors.append("shared_kindness")
    elif _average_trait(first, second, "agreeableness") <= 35:
        factors.append("low_trust")
    if _average_trait(first, second, "stability") >= 65:
        factors.append("steady_pair")
    elif _average_trait(first, second, "stability") <= 35:
        factors.append("volatile_pair")
    if _average_trait(first, second, "openness") >= 65:
        factors.append("shared_curiosity")
    if _average_trait(first, second, "discipline") >= 65:
        factors.append("shared_discipline")
    if abs(first["extraversion"] - second["extraversion"]) >= 45:
        factors.append("social_mismatch")
    if average_gap >= 35:
        factors.append("outlook_gap")
    return factors or ["balanced"]


def _apply_personality_context_record(
    character: Any,
    record: Any,
    deltas: dict[str, int],
    factor_keys: list[str],
) -> None:
    kind = getattr(record, "kind", "")
    primary_actor_id = getattr(record, "primary_actor_id", None)
    secondary_actor_ids = set(getattr(record, "secondary_actor_ids", []))
    char_id = getattr(character, "char_id", "")
    if kind == "dying_rescued":
        if primary_actor_id == char_id:
            _add_context_delta(
                deltas,
                factor_keys,
                "rescued_gratitude",
                agreeableness=4,
                stability=-3,
            )
        elif char_id in secondary_actor_ids:
            _add_context_delta(
                deltas,
                factor_keys,
                "rescuer_responsibility",
                discipline=3,
                agreeableness=2,
                stability=-2,
            )
    elif kind in {"condition_worsened", "adventure_injured"}:
        _add_context_delta(deltas, factor_keys, "recent_fear", stability=-4, extraversion=-2)
    elif kind == "death":
        _add_context_delta(deltas, factor_keys, "grief", stability=-5, agreeableness=-2, extraversion=-2)
    elif kind in {"battle", "battle_fatal"}:
        _add_context_delta(deltas, factor_keys, "combat_tension", discipline=3, stability=-2)
    elif kind in {"adventure_returned", "adventure_discovery"}:
        _add_context_delta(deltas, factor_keys, "recent_wonder", openness=4, extraversion=2)
    elif kind == "injury_recovery":
        _add_context_delta(deltas, factor_keys, "relief", stability=3, agreeableness=2)


def _add_context_delta(
    deltas: dict[str, int],
    factor_keys: list[str],
    factor_key: str,
    **trait_deltas: int,
) -> None:
    factor_keys.append(factor_key)
    for trait, delta in trait_deltas.items():
        if trait in deltas:
            deltas[trait] += delta


def _personality_level_key(value: int) -> str:
    if value >= 67:
        return "personality_level_high"
    if value <= 33:
        return "personality_level_low"
    return "personality_level_mid"

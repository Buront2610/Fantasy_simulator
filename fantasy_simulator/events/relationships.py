"""Relationship event helpers for EventSystem."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List

from ..character_model.personality import (
    PersonalityAffinity,
    PersonalityContext,
    PersonalityFeatAffinity,
    marriage_threshold_adjustment,
    personality_affinity,
    personality_feat_affinity,
    personality_context_from_events,
    relationship_delta_from_personality,
    render_affinity_factors,
    render_personality_feat_factors,
    render_personality_context_factors,
    romance_delta_from_personality,
)
from ..event_causality import latest_pair_event_ids, pair_cause_event_ids
from ..event_models import EventResult, generate_record_id
from ..event_story import prefix_description_with_story_hook
from ..i18n import tr

if TYPE_CHECKING:
    from ..character import Character
    from ..world import World


CATALYST_EVENT_KINDS: tuple[str, ...] = (
    "dying_rescued",
    "adventure_returned",
    "adventure_returned_injured",
    "adventure_discovery",
    "adventure_injured",
    "battle",
    "battle_fatal",
    "romance",
    "relationship_value_alignment",
    "relationship_value_reconsidered",
)
CATALYST_RELATION_TAGS: tuple[str, ...] = ("savior", "rescued", "co_parent", "family", "shared_values")
PERSONALITY_TURNING_POINT_KINDS: tuple[str, ...] = (
    "relationship_reconciliation",
    "relationship_conflict",
    "relationship_mentorship",
    "relationship_betrayal",
    "relationship_comfort",
    "relationship_value_alignment",
    "relationship_value_clash",
    "relationship_value_reconsidered",
)


@dataclass(frozen=True)
class RelationshipCatalyst:
    score: int = 0
    factor_keys: tuple[str, ...] = ()
    cause_event_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelationshipPersonality:
    first_context: PersonalityContext
    second_context: PersonalityContext
    affinity: PersonalityAffinity
    feature_affinity: PersonalityFeatAffinity
    factor_text: str
    context_factor_keys: tuple[str, ...]
    cause_event_ids: tuple[str, ...]


def _relationship_personality(world: "World", char1: "Character", char2: "Character") -> RelationshipPersonality:
    event_records = getattr(world, "event_records", [])
    first_context = personality_context_from_events(char1, event_records)
    second_context = personality_context_from_events(char2, event_records)
    affinity = personality_affinity(first_context.profile, second_context.profile)
    feature_affinity = personality_feat_affinity(
        getattr(char1, "personality_feats", []),
        getattr(char2, "personality_feats", []),
    )
    context_factor_keys = tuple(dict.fromkeys([*first_context.factor_keys, *second_context.factor_keys]))
    factor_parts = [render_affinity_factors(affinity.factor_keys)]
    if feature_affinity.factor_keys:
        factor_parts.append(render_personality_feat_factors(feature_affinity.factor_keys))
    if context_factor_keys:
        factor_parts.append(render_personality_context_factors(context_factor_keys))
    return RelationshipPersonality(
        first_context=first_context,
        second_context=second_context,
        affinity=affinity,
        feature_affinity=feature_affinity,
        factor_text="; ".join(part for part in factor_parts if part),
        context_factor_keys=context_factor_keys,
        cause_event_ids=tuple(dict.fromkeys([*first_context.cause_event_ids, *second_context.cause_event_ids])),
    )


def _pair_history_cause_ids(
    world: "World",
    char1: "Character",
    char2: "Character",
    *,
    relation_tags: tuple[str, ...] = (),
    event_kinds: tuple[str, ...] = (),
    limit: int = 2,
) -> List[str]:
    return pair_cause_event_ids(
        world,
        char1,
        char2,
        relation_tags=relation_tags,
        event_kinds=event_kinds,
        limit=limit,
    )


def _relationship_catalyst(world: "World", char1: "Character", char2: "Character") -> RelationshipCatalyst:
    factor_scores: dict[str, int] = {}
    if _has_any_pair_tag(char1, char2, ("savior", "rescued")):
        factor_scores["rescue_debt"] = 8
    if _has_any_pair_tag(char1, char2, ("co_parent", "family")):
        factor_scores["family_bond"] = 6
    if _has_any_pair_tag(char1, char2, ("shared_values",)):
        factor_scores["shared_values"] = 5

    event_records = getattr(world, "event_records", [])
    pair_ids = (char1.char_id, char2.char_id)
    cause_event_ids: list[str] = []
    cause_event_ids.extend(
        pair_cause_event_ids(
            world,
            char1,
            char2,
            relation_tags=CATALYST_RELATION_TAGS,
            event_kinds=CATALYST_EVENT_KINDS,
            limit=4,
        )
    )
    cause_event_ids.extend(latest_pair_event_ids(event_records, pair_ids, CATALYST_EVENT_KINDS, limit=4))
    recent_kinds = _recent_pair_event_kinds(event_records, pair_ids, CATALYST_EVENT_KINDS, limit=4)
    if "dying_rescued" in recent_kinds:
        factor_scores["rescue_debt"] = max(factor_scores.get("rescue_debt", 0), 8)
    if any(kind.startswith("adventure_") for kind in recent_kinds):
        factor_scores["shared_adventure"] = max(factor_scores.get("shared_adventure", 0), 5)
    if "romance" in recent_kinds:
        factor_scores["prior_romance"] = max(factor_scores.get("prior_romance", 0), 4)
    if "battle" in recent_kinds or "battle_fatal" in recent_kinds:
        factor_scores["hard_won_respect"] = max(factor_scores.get("hard_won_respect", 0), 3)
    if "relationship_value_alignment" in recent_kinds:
        factor_scores["shared_values"] = max(factor_scores.get("shared_values", 0), 5)

    if not factor_scores:
        return RelationshipCatalyst()
    ordered = tuple(sorted(factor_scores, key=lambda key: (-factor_scores[key], key)))
    return RelationshipCatalyst(
        score=min(10, sum(factor_scores.values())),
        factor_keys=ordered,
        cause_event_ids=tuple(dict.fromkeys(cause_event_ids)),
    )


def _catalyst_delta(affinity_score: int, catalyst: RelationshipCatalyst) -> int:
    if catalyst.score <= 0 or affinity_score >= 0:
        return 0
    return min(catalyst.score, abs(affinity_score))


def _has_any_pair_tag(char1: "Character", char2: "Character", tags: tuple[str, ...]) -> bool:
    return any(char1.has_relation_tag(char2.char_id, tag) or char2.has_relation_tag(char1.char_id, tag) for tag in tags)


def _recent_pair_event_kinds(
    event_records: Any,
    actor_ids: tuple[str, str],
    allowed_kinds: tuple[str, ...],
    *,
    limit: int,
) -> tuple[str, ...]:
    required_actor_ids = {actor_id for actor_id in actor_ids if actor_id}
    found: list[str] = []
    for record in reversed(list(event_records)):
        kind = getattr(record, "kind", "")
        if kind not in allowed_kinds:
            continue
        record_actor_ids = set(getattr(record, "secondary_actor_ids", []))
        primary_actor_id = getattr(record, "primary_actor_id", None)
        if isinstance(primary_actor_id, str) and primary_actor_id:
            record_actor_ids.add(primary_actor_id)
        if not required_actor_ids.issubset(record_actor_ids):
            continue
        found.append(kind)
        if len(found) >= limit:
            break
    return tuple(found)


def _catalyst_metadata(catalyst: RelationshipCatalyst, catalyst_delta: int) -> dict[str, Any]:
    if catalyst.score <= 0:
        return {}
    return {
        "relationship_catalyst_bonus": catalyst_delta,
        "relationship_catalyst_factor_keys": list(catalyst.factor_keys),
        "relationship_catalyst_factors": ", ".join(
            tr(f"relationship_catalyst_{factor_key}") for factor_key in catalyst.factor_keys
        ),
    }


def _personality_metadata(personality: RelationshipPersonality, relationship_delta: int) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "personality_affinity": personality.affinity.score,
        "personality_factor_keys": list(personality.affinity.factor_keys),
        "personality_factors": personality.factor_text,
        "relationship_delta": relationship_delta,
    }
    if personality.context_factor_keys:
        payload["personality_context_factor_keys"] = list(personality.context_factor_keys)
        payload["personality_context_factors"] = render_personality_context_factors(personality.context_factor_keys)
    if personality.feature_affinity.factor_keys:
        payload["personality_feature_score"] = personality.feature_affinity.score
        payload["personality_feature_factor_keys"] = list(personality.feature_affinity.factor_keys)
        payload["personality_feature_factors"] = render_personality_feat_factors(
            personality.feature_affinity.factor_keys
        )
    return payload


def _relationship_moment_key(
    personality: RelationshipPersonality,
    catalyst: RelationshipCatalyst,
    relationship_delta: int,
) -> str:
    feature_factors = set(personality.feature_affinity.factor_keys)
    affinity_factors = set(personality.affinity.factor_keys)
    context_factors = set(personality.context_factor_keys)
    catalyst_factors = set(catalyst.factor_keys)
    if personality.affinity.score < 0 and catalyst.score > 0:
        return "relationship_moment_unlikely_catalyst"
    if "temper_balanced" in feature_factors:
        return "relationship_moment_temper_balanced"
    if feature_factors.intersection({"vow_vs_impulse", "home_vs_distance"}):
        return "relationship_moment_feature_clash"
    if context_factors.intersection({"grief", "recent_fear", "rescued_gratitude"}):
        return "relationship_moment_vulnerable"
    if catalyst_factors.intersection({"rescue_debt", "hard_won_respect"}):
        return "relationship_moment_shared_ordeal"
    if affinity_factors.intersection({"shared_curiosity", "shared_discipline"}):
        return "relationship_moment_shared_pursuit"
    if affinity_factors.intersection({"social_mismatch", "outlook_gap", "low_trust"}):
        return "relationship_moment_mismatch"
    if affinity_factors.intersection({"shared_kindness", "steady_pair"}):
        return "relationship_moment_trust"
    if relationship_delta > 10:
        return "relationship_moment_spark"
    if relationship_delta < 0:
        return "relationship_moment_friction"
    return "relationship_moment_measured"


def _relationship_delta_from_personality_state(personality: RelationshipPersonality) -> int:
    return max(
        -9,
        min(
            9,
            relationship_delta_from_personality(
                personality.first_context.profile,
                personality.second_context.profile,
            ) + personality.feature_affinity.score,
        ),
    )


def _romance_delta_from_personality_state(personality: RelationshipPersonality) -> int:
    return max(
        -8,
        min(
            10,
            romance_delta_from_personality(
                personality.first_context.profile,
                personality.second_context.profile,
            ) + personality.feature_affinity.score,
        ),
    )


def _relationship_metadata(
    summary_key: str,
    render_params: Dict[str, Any],
    cause_event_ids: List[str],
    **extra: Any,
) -> Dict[str, Any]:
    return {
        "cause_event_ids": list(dict.fromkeys(cause_event_ids)),
        "summary_key": summary_key,
        "render_params": render_params,
        **extra,
    }


def _anniversary_result(
    char1: "Character",
    char2: "Character",
    world: "World",
) -> EventResult:
    cause_event_ids = _pair_history_cause_ids(
        world,
        char1,
        char2,
        relation_tags=("spouse",),
        event_kinds=("marriage", "anniversary"),
    )
    desc = tr("marriage_anniversary", name1=char1.name, name2=char2.name)
    char1.add_history(tr("history_anniversary", year=world.year, name=char2.name))
    char2.add_history(tr("history_anniversary", year=world.year, name=char1.name))
    return EventResult(
        description=desc,
        affected_characters=[char1.char_id, char2.char_id],
        event_type="anniversary",
        year=world.year,
        metadata=_relationship_metadata(
            "events.marriage_anniversary.summary",
            {"name1": char1.name, "name2": char2.name},
            cause_event_ids,
        ),
    )


def _romance_result(
    *,
    char1: "Character",
    char2: "Character",
    world: "World",
    description_key: str,
    summary_key: str,
    relationship_delta: int,
) -> EventResult:
    cause_event_ids = _pair_history_cause_ids(world, char1, char2, event_kinds=("meeting", "romance"))
    personality = _relationship_personality(world, char1, char2)
    personality_delta = _romance_delta_from_personality_state(personality)
    catalyst = _relationship_catalyst(world, char1, char2)
    catalyst_delta = _catalyst_delta(personality.affinity.score, catalyst)
    applied_delta = relationship_delta + personality_delta + catalyst_delta
    char1.update_mutual_relationship(char2, applied_delta)
    catalyst_payload = _catalyst_metadata(catalyst, catalyst_delta)
    personality_payload = _personality_metadata(personality, applied_delta)
    relationship_moment_key = _relationship_moment_key(personality, catalyst, applied_delta)
    relationship_moment = " " + tr(relationship_moment_key)
    desc = tr(
        description_key,
        name1=char1.name,
        name2=char2.name,
        location=world.location_name(char1.location_id),
        relationship_moment=relationship_moment,
    )
    return EventResult(
        description=desc,
        affected_characters=[char1.char_id, char2.char_id],
        stat_changes={},
        event_type="romance",
        year=world.year,
        metadata=_relationship_metadata(
            summary_key,
            {
                "name1": char1.name,
                "name2": char2.name,
                "location_id": char1.location_id,
                "relationship_moment_key": relationship_moment_key,
                **personality_payload,
                **catalyst_payload,
            },
            [*cause_event_ids, *personality.cause_event_ids, *catalyst.cause_event_ids],
            **personality_payload,
            **catalyst_payload,
        ),
    )


def _marriage_relation_tag_updates(
    char1: "Character",
    char2: "Character",
    source_event_id: str,
) -> List[Dict[str, str]]:
    char1.add_relation_tag(char2.char_id, "spouse", source_event_id=source_event_id)
    char2.add_relation_tag(char1.char_id, "spouse", source_event_id=source_event_id)
    return [
        {"source": char1.char_id, "target": char2.char_id, "tag": "spouse"},
        {"source": char2.char_id, "target": char1.char_id, "tag": "spouse"},
    ]


def _marriage_stat_changes(char1: "Character", char2: "Character") -> Dict[str, Dict[str, int]]:
    stat_changes = {
        char1.char_id: {"wisdom": 2, "charisma": 1},
        char2.char_id: {"wisdom": 2, "charisma": 1},
    }
    char1.apply_stat_delta(stat_changes[char1.char_id])
    char2.apply_stat_delta(stat_changes[char2.char_id])
    return stat_changes


def _marriage_result(
    char1: "Character",
    char2: "Character",
    world: "World",
    rng: Any,
) -> EventResult:
    char1.spouse_id = char2.char_id
    char2.spouse_id = char1.char_id
    char1.update_mutual_relationship(char2, 20)
    catalyst = _relationship_catalyst(world, char1, char2)
    personality = _relationship_personality(world, char1, char2)
    catalyst_payload = _catalyst_metadata(catalyst, _catalyst_delta(
        personality.affinity.score,
        catalyst,
    ))
    personality_payload = _personality_metadata(personality, 20)
    marriage_source_id = generate_record_id(rng)
    cause_event_ids = _pair_history_cause_ids(
        world,
        char1,
        char2,
        relation_tags=("friend",),
        event_kinds=("meeting", "romance"),
        limit=3,
    )
    relation_tag_updates = _marriage_relation_tag_updates(char1, char2, marriage_source_id)
    stat_changes = _marriage_stat_changes(char1, char2)

    desc = tr(
        "marriage_happened",
        name1=char1.name,
        race1=char1.race,
        job1=char1.job,
        name2=char2.name,
        race2=char2.race,
        job2=char2.job,
        location=world.location_name(char1.location_id),
    )
    char1.add_history(tr(
        "history_married", year=world.year, name=char2.name,
        location=world.location_name(char1.location_id),
    ))
    char2.add_history(tr(
        "history_married", year=world.year, name=char1.name,
        location=world.location_name(char2.location_id),
    ))
    return EventResult(
        description=desc,
        affected_characters=[char1.char_id, char2.char_id],
        stat_changes=stat_changes,
        event_type="marriage",
        year=world.year,
        metadata=_relationship_metadata(
            "events.marriage.summary",
            {
                "name1": char1.name,
                "race1": char1.race,
                "job1": char1.job,
                "name2": char2.name,
                "race2": char2.race,
                "job2": char2.job,
                "location_id": char1.location_id,
                **personality_payload,
                **catalyst_payload,
            },
            [*cause_event_ids, *personality.cause_event_ids, *catalyst.cause_event_ids],
            relation_tag_updates=relation_tag_updates,
            record_id=marriage_source_id,
            **personality_payload,
            **catalyst_payload,
        ),
    )


def resolve_marriage_event(
    char1: "Character",
    char2: "Character",
    world: "World",
    rng: Any = random,
) -> EventResult:
    """Resolve romance, anniversary, or marriage between two characters."""
    rel1 = char1.get_relationship(char2.char_id)
    rel2 = char2.get_relationship(char1.char_id)
    avg_rel = (rel1 + rel2) / 2
    catalyst = _relationship_catalyst(world, char1, char2)
    personality = _relationship_personality(world, char1, char2)
    threshold_adjustment = marriage_threshold_adjustment(
        personality.first_context.profile,
        personality.second_context.profile,
    )
    threshold_adjustment -= personality.feature_affinity.score
    threshold_adjustment -= _catalyst_delta(personality.affinity.score, catalyst)
    required_single = 35 + threshold_adjustment
    required_average = 40 + threshold_adjustment

    if char1.spouse_id == char2.char_id and char2.spouse_id == char1.char_id:
        return _anniversary_result(char1, char2, world)

    if char1.spouse_id not in (None, char2.char_id) or char2.spouse_id not in (None, char1.char_id):
        return _romance_result(
            char1=char1,
            char2=char2,
            world=world,
            description_key="romance_commitments_blocked",
            summary_key="events.romance_commitments_blocked.summary",
            relationship_delta=3,
        )

    if (
        char1.age < 18
        or char2.age < 18
        or rel1 < required_single
        or rel2 < required_single
        or avg_rel < required_average
    ):
        return _romance_result(
            char1=char1,
            char2=char2,
            world=world,
            description_key="romance_growing_closer",
            summary_key="events.romance_growing_closer.summary",
            relationship_delta=20,
        )

    return _marriage_result(char1, char2, world, rng)


def _meeting_relation_tag_updates(
    char1: "Character",
    char2: "Character",
    avg_after: int,
    rng: Any,
) -> tuple[List[Dict[str, str]], str | None]:
    relation_tag_updates: List[Dict[str, str]] = []
    meeting_source_id = generate_record_id(rng) if avg_after >= 50 or avg_after <= -50 else None
    if avg_after >= 50:
        tag = "friend"
    elif avg_after <= -50:
        tag = "rival"
    else:
        return relation_tag_updates, meeting_source_id
    _remove_opposed_relation_tag(char1, char2.char_id, tag)
    _remove_opposed_relation_tag(char2, char1.char_id, tag)
    char1.add_relation_tag(char2.char_id, tag)
    char2.add_relation_tag(char1.char_id, tag)
    return [
        {"source": char1.char_id, "target": char2.char_id, "tag": tag},
        {"source": char2.char_id, "target": char1.char_id, "tag": tag},
    ], meeting_source_id


def _add_mutual_relation_tag(
    char1: "Character",
    char2: "Character",
    tag1: str,
    tag2: str,
    source_event_id: str,
) -> List[Dict[str, str]]:
    char1.add_relation_tag(char2.char_id, tag1, source_event_id=source_event_id)
    char2.add_relation_tag(char1.char_id, tag2, source_event_id=source_event_id)
    return [
        {"source": char1.char_id, "target": char2.char_id, "tag": tag1},
        {"source": char2.char_id, "target": char1.char_id, "tag": tag2},
    ]


def _remove_opposed_relation_tag(character: "Character", target_id: str, tag: str) -> None:
    opposed = {"friend": "rival", "rival": "friend"}.get(tag)
    if opposed is None:
        return
    tags = character.relation_tags.get(target_id)
    if tags is None:
        return
    character.relation_tags[target_id] = [current for current in tags if current != opposed]
    if not character.relation_tags[target_id]:
        del character.relation_tags[target_id]


def _remove_relation_tag(character: "Character", target_id: str, tag: str) -> None:
    tags = character.relation_tags.get(target_id)
    if tags is None:
        return
    character.relation_tags[target_id] = [current for current in tags if current != tag]
    if not character.relation_tags[target_id]:
        del character.relation_tags[target_id]


def _meeting_description_key(avg_after: int) -> str:
    if avg_after > 10:
        return "meeting_positive"
    if avg_after > 0:
        return "meeting_pleasant"
    if avg_after == 0:
        return "meeting_neutral"
    return "meeting_negative"


def _relationship_turning_point_key(
    char1: "Character",
    char2: "Character",
    personality: RelationshipPersonality,
    catalyst: RelationshipCatalyst,
) -> str:
    rel1 = char1.get_relationship(char2.char_id)
    rel2 = char2.get_relationship(char1.char_id)
    avg_rel = round((rel1 + rel2) / 2)
    context = set(personality.context_factor_keys)
    feature_factors = set(personality.feature_affinity.factor_keys)
    affinity_factors = set(personality.affinity.factor_keys)
    first_profile = personality.first_context.profile
    second_profile = personality.second_context.profile
    if avg_rel <= -35 and catalyst.score >= 5:
        return "reconciliation"
    value_rift_key = _value_rift_turning_point_key(char1, char2, avg_rel, catalyst)
    if value_rift_key:
        return value_rift_key
    if feature_factors.intersection({"vow_vs_impulse", "home_vs_distance"}) and avg_rel < 30:
        return "value_clash"
    if (
        feature_factors.intersection({"shared_features", "hard_won_courage"})
        or affinity_factors.intersection({"shared_curiosity", "shared_discipline"})
    ) and avg_rel >= -10:
        return "value_alignment"
    if avg_rel >= 35 and (
        abs(char1.age - char2.age) >= 10
        or max(first_profile["discipline"], second_profile["discipline"]) >= 68
        or max(first_profile["openness"], second_profile["openness"]) >= 72
    ):
        return "mentorship"
    if avg_rel <= -45 or (
        "combat_tension" in context
        and min(first_profile["agreeableness"], second_profile["agreeableness"]) <= 35
    ):
        return "betrayal"
    if context.intersection({"grief", "recent_fear", "rescued_gratitude", "relief"}):
        return "comfort"
    return "conflict" if personality.affinity.score < 0 else "comfort"


def _value_rift_turning_point_key(
    char1: "Character",
    char2: "Character",
    avg_rel: int,
    catalyst: RelationshipCatalyst,
) -> str:
    if not _has_any_pair_tag(char1, char2, ("value_rift",)):
        return ""
    if catalyst.score >= 5:
        return "value_reconsidered"
    if avg_rel < 20:
        return "value_clash"
    return ""


def _relationship_turning_point_delta(
    key: str,
    personality: RelationshipPersonality,
    catalyst: RelationshipCatalyst,
) -> int:
    if key == "reconciliation":
        return 16 + max(0, catalyst.score // 2)
    if key == "mentorship":
        return 10 + max(0, personality.affinity.score // 3)
    if key == "betrayal":
        return -24 + min(0, personality.affinity.score // 2)
    if key == "comfort":
        return 9 + max(0, personality.affinity.score // 4)
    if key == "value_alignment":
        return 12 + max(0, personality.feature_affinity.score)
    if key == "value_clash":
        return -14 + min(0, personality.feature_affinity.score)
    if key == "value_reconsidered":
        return 8 + max(0, catalyst.score // 2)
    return -10 + min(0, personality.affinity.score // 3)


def _relationship_turning_point_tags(
    key: str,
    char1: "Character",
    char2: "Character",
    source_event_id: str,
) -> List[Dict[str, str]]:
    if key == "mentorship":
        if char1.age >= char2.age:
            return _add_mutual_relation_tag(char1, char2, "mentor", "disciple", source_event_id)
        return _add_mutual_relation_tag(char1, char2, "disciple", "mentor", source_event_id)
    if key == "betrayal":
        _remove_opposed_relation_tag(char1, char2.char_id, "rival")
        _remove_opposed_relation_tag(char2, char1.char_id, "rival")
        return _add_mutual_relation_tag(char1, char2, "betrayer", "rival", source_event_id)
    if key in {"reconciliation", "comfort", "value_alignment"}:
        _remove_opposed_relation_tag(char1, char2.char_id, "friend")
        _remove_opposed_relation_tag(char2, char1.char_id, "friend")
        updates = _add_mutual_relation_tag(char1, char2, "friend", "friend", source_event_id)
        if key == "value_alignment":
            updates.extend(_add_mutual_relation_tag(char1, char2, "shared_values", "shared_values", source_event_id))
        return updates
    if key == "value_reconsidered":
        _remove_opposed_relation_tag(char1, char2.char_id, "friend")
        _remove_opposed_relation_tag(char2, char1.char_id, "friend")
        _remove_relation_tag(char1, char2.char_id, "value_rift")
        _remove_relation_tag(char2, char1.char_id, "value_rift")
        updates = _add_mutual_relation_tag(char1, char2, "friend", "friend", source_event_id)
        updates.extend(_add_mutual_relation_tag(char1, char2, "shared_values", "shared_values", source_event_id))
        return updates
    if key == "value_clash":
        _remove_opposed_relation_tag(char1, char2.char_id, "rival")
        _remove_opposed_relation_tag(char2, char1.char_id, "rival")
        updates = _add_mutual_relation_tag(char1, char2, "rival", "rival", source_event_id)
        updates.extend(_add_mutual_relation_tag(char1, char2, "value_rift", "value_rift", source_event_id))
        return updates
    return []


def _relationship_turning_point_reason_key(
    key: str,
    personality: RelationshipPersonality,
    catalyst: RelationshipCatalyst,
) -> str:
    context = set(personality.context_factor_keys)
    catalyst_factors = set(catalyst.factor_keys)
    affinity_factors = set(personality.affinity.factor_keys)
    if key == "value_reconsidered":
        return "relationship_turning_point_reason_value_reconsidered"
    if personality.affinity.score < 0 and catalyst.score > 0:
        return "relationship_turning_point_reason_unlikely_bond"
    if "rescue_debt" in catalyst_factors or "rescued_gratitude" in context:
        return "relationship_turning_point_reason_rescue_debt"
    if context.intersection({"grief", "recent_fear"}):
        return "relationship_turning_point_reason_vulnerability"
    if "combat_tension" in context:
        return "relationship_turning_point_reason_combat_tension"
    if key == "mentorship":
        if "shared_curiosity" in affinity_factors:
            return "relationship_turning_point_reason_shared_curiosity"
        return "relationship_turning_point_reason_guidance"
    if key == "betrayal":
        if affinity_factors.intersection({"low_trust", "outlook_gap", "social_mismatch"}):
            return "relationship_turning_point_reason_mistrust"
        return "relationship_turning_point_reason_old_grudge"
    if key == "conflict":
        return "relationship_turning_point_reason_mismatch"
    if key == "value_alignment":
        if personality.feature_affinity.factor_keys:
            return "relationship_turning_point_reason_shared_features"
        return "relationship_turning_point_reason_shared_values"
    if key == "value_clash":
        if personality.feature_affinity.factor_keys:
            return "relationship_turning_point_reason_feature_clash"
        return "relationship_turning_point_reason_value_clash"
    if affinity_factors.intersection({"shared_kindness", "steady_pair"}):
        return "relationship_turning_point_reason_trust"
    return "relationship_turning_point_reason_shared_history"


def resolve_relationship_turning_point_event(
    char1: "Character",
    char2: "Character",
    world: "World",
    rng: Any = random,
) -> EventResult:
    """Resolve a personality-driven turning point between two characters."""
    personality = _relationship_personality(world, char1, char2)
    catalyst = _relationship_catalyst(world, char1, char2)
    key = _relationship_turning_point_key(char1, char2, personality, catalyst)
    delta = _relationship_turning_point_delta(key, personality, catalyst)
    char1.update_mutual_relationship(char2, delta, delta + rng.randint(-3, 3))
    rel1_after = char1.get_relationship(char2.char_id)
    rel2_after = char2.get_relationship(char1.char_id)
    avg_after = round((rel1_after + rel2_after) / 2)
    source_event_id = generate_record_id(rng)
    relation_tag_updates = _relationship_turning_point_tags(key, char1, char2, source_event_id)
    personality_payload = _personality_metadata(personality, delta)
    catalyst_payload = _catalyst_metadata(catalyst, _catalyst_delta(personality.affinity.score, catalyst))
    reason_key = _relationship_turning_point_reason_key(key, personality, catalyst)
    cause_event_ids = _pair_history_cause_ids(
        world,
        char1,
        char2,
        relation_tags=("friend", "rival", "mentor", "disciple", "savior", "rescued", "shared_values", "value_rift"),
        event_kinds=(
            "meeting",
            "romance",
            "battle",
            "battle_fatal",
            "dying_rescued",
            *PERSONALITY_TURNING_POINT_KINDS,
        ),
        limit=4,
    )
    location = world.location_name(char1.location_id)
    desc = tr(
        f"relationship_{key}",
        name1=char1.name,
        name2=char2.name,
        location=location,
        relationship_a=rel1_after,
        relationship_b=rel2_after,
        relationship_avg=avg_after,
        turning_point_reason=tr(reason_key),
    )
    char1.add_history(tr(f"history_relationship_{key}", year=world.year, name=char2.name, location=location))
    char2.add_history(tr(f"history_relationship_{key}", year=world.year, name=char1.name, location=location))
    render_params = {
        "name1": char1.name,
        "name2": char2.name,
        "location_id": char1.location_id,
        "relationship_a": rel1_after,
        "relationship_b": rel2_after,
        "relationship_avg": avg_after,
        "turning_point_reason_key": reason_key,
        **personality_payload,
        **catalyst_payload,
    }
    return EventResult(
        description=desc,
        affected_characters=[char1.char_id, char2.char_id],
        event_type=f"relationship_{key}",
        year=world.year,
        metadata=_relationship_metadata(
            f"events.relationship_{key}.summary",
            render_params,
            [*cause_event_ids, *personality.cause_event_ids, *catalyst.cause_event_ids],
            relation_tag_updates=relation_tag_updates,
            record_id=source_event_id,
            **personality_payload,
            **catalyst_payload,
        ),
    )


def resolve_meeting_event(
    char1: "Character",
    char2: "Character",
    world: "World",
    rng: Any = random,
) -> EventResult:
    """Resolve a meeting and its relationship-tag side effects."""
    base_delta = rng.randint(-15, 25)
    personality = _relationship_personality(world, char1, char2)
    personality_delta = _relationship_delta_from_personality_state(personality)
    catalyst = _relationship_catalyst(world, char1, char2)
    catalyst_delta = _catalyst_delta(personality.affinity.score, catalyst)
    delta = base_delta + personality_delta + catalyst_delta
    char1.update_relationship(char2.char_id, delta)
    char2.update_relationship(char1.char_id, delta + rng.randint(-5, 5))

    rel1_after = char1.get_relationship(char2.char_id)
    rel2_after = char2.get_relationship(char1.char_id)
    avg_after = round((rel1_after + rel2_after) / 2)

    relation_tag_updates, meeting_source_id = _meeting_relation_tag_updates(char1, char2, avg_after, rng)
    description_key = _meeting_description_key(avg_after)
    catalyst_payload = _catalyst_metadata(catalyst, catalyst_delta)
    personality_payload = _personality_metadata(personality, delta)
    relationship_moment_key = _relationship_moment_key(personality, catalyst, delta)
    relationship_moment = " " + tr(relationship_moment_key)
    desc = tr(
        description_key,
        name1=char1.name,
        name2=char2.name,
        location=world.location_name(char1.location_id),
        relationship_a=rel1_after,
        relationship_b=rel2_after,
        relationship_avg=avg_after,
        relationship_moment=relationship_moment,
    )
    desc, story_hook_key = prefix_description_with_story_hook(
        "meeting",
        rng,
        desc,
        name1=char1.name,
        name2=char2.name,
        location=world.location_name(char1.location_id),
    )

    char1.add_history(tr(
        "history_met", year=world.year, name=char2.name,
        location=world.location_name(char1.location_id),
    ))
    char2.add_history(tr(
        "history_met", year=world.year, name=char1.name,
        location=world.location_name(char2.location_id),
    ))
    return EventResult(
        description=desc,
        affected_characters=[char1.char_id, char2.char_id],
        event_type="meeting",
        year=world.year,
        metadata={
            "relation_tag_updates": relation_tag_updates,
            "summary_key": f"events.{description_key}.summary",
            "render_params": {
                "name1": char1.name,
                "name2": char2.name,
                "location_id": char1.location_id,
                "relationship_a": rel1_after,
                "relationship_b": rel2_after,
                "relationship_avg": avg_after,
                "relationship_moment_key": relationship_moment_key,
                **personality_payload,
                **catalyst_payload,
                "story_hook_key": story_hook_key,
            },
            **personality_payload,
            "cause_event_ids": list(dict.fromkeys([*personality.cause_event_ids, *catalyst.cause_event_ids])),
            **catalyst_payload,
            **({"record_id": meeting_source_id} if meeting_source_id is not None else {}),
        },
    )

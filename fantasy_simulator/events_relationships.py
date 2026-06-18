"""Relationship event helpers for EventSystem."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List

from .character_personality import (
    marriage_threshold_adjustment,
    personality_affinity,
    relationship_delta_from_personality,
    render_affinity_factors,
    romance_delta_from_personality,
)
from .event_causality import latest_pair_event_ids, pair_cause_event_ids
from .event_models import EventResult, generate_record_id
from .event_story import prefix_description_with_story_hook
from .i18n import tr

if TYPE_CHECKING:
    from .character import Character
    from .world import World


CATALYST_EVENT_KINDS: tuple[str, ...] = (
    "dying_rescued",
    "adventure_returned",
    "adventure_returned_injured",
    "adventure_discovery",
    "adventure_injured",
    "battle",
    "battle_fatal",
    "romance",
)
CATALYST_RELATION_TAGS: tuple[str, ...] = ("savior", "rescued", "co_parent", "family")


@dataclass(frozen=True)
class RelationshipCatalyst:
    score: int = 0
    factor_keys: tuple[str, ...] = ()
    cause_event_ids: tuple[str, ...] = ()


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
    affinity = personality_affinity(char1.personality, char2.personality)
    personality_delta = romance_delta_from_personality(char1.personality, char2.personality)
    catalyst = _relationship_catalyst(world, char1, char2)
    catalyst_delta = _catalyst_delta(affinity.score, catalyst)
    applied_delta = relationship_delta + personality_delta + catalyst_delta
    char1.update_mutual_relationship(char2, applied_delta)
    catalyst_payload = _catalyst_metadata(catalyst, catalyst_delta)
    desc = tr(
        description_key,
        name1=char1.name,
        name2=char2.name,
        location=world.location_name(char1.location_id),
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
                "personality_affinity": affinity.score,
                "personality_factors": render_affinity_factors(affinity.factor_keys),
                "relationship_delta": applied_delta,
                **catalyst_payload,
            },
            [*cause_event_ids, *catalyst.cause_event_ids],
            personality_affinity=affinity.score,
            personality_factor_keys=list(affinity.factor_keys),
            relationship_delta=applied_delta,
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
    catalyst_payload = _catalyst_metadata(catalyst, _catalyst_delta(
        personality_affinity(char1.personality, char2.personality).score,
        catalyst,
    ))
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
                **catalyst_payload,
            },
            [*cause_event_ids, *catalyst.cause_event_ids],
            relation_tag_updates=relation_tag_updates,
            record_id=marriage_source_id,
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
    affinity = personality_affinity(char1.personality, char2.personality)
    threshold_adjustment = marriage_threshold_adjustment(char1.personality, char2.personality)
    threshold_adjustment -= _catalyst_delta(affinity.score, catalyst)
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


def _meeting_description_key(avg_after: int) -> str:
    if avg_after > 10:
        return "meeting_positive"
    if avg_after > 0:
        return "meeting_pleasant"
    if avg_after == 0:
        return "meeting_neutral"
    return "meeting_negative"


def resolve_meeting_event(
    char1: "Character",
    char2: "Character",
    world: "World",
    rng: Any = random,
) -> EventResult:
    """Resolve a meeting and its relationship-tag side effects."""
    base_delta = rng.randint(-15, 25)
    affinity = personality_affinity(char1.personality, char2.personality)
    personality_delta = relationship_delta_from_personality(char1.personality, char2.personality)
    catalyst = _relationship_catalyst(world, char1, char2)
    catalyst_delta = _catalyst_delta(affinity.score, catalyst)
    delta = base_delta + personality_delta + catalyst_delta
    char1.update_relationship(char2.char_id, delta)
    char2.update_relationship(char1.char_id, delta + rng.randint(-5, 5))

    rel1_after = char1.get_relationship(char2.char_id)
    rel2_after = char2.get_relationship(char1.char_id)
    avg_after = round((rel1_after + rel2_after) / 2)

    relation_tag_updates, meeting_source_id = _meeting_relation_tag_updates(char1, char2, avg_after, rng)
    description_key = _meeting_description_key(avg_after)
    catalyst_payload = _catalyst_metadata(catalyst, catalyst_delta)
    desc = tr(
        description_key,
        name1=char1.name,
        name2=char2.name,
        location=world.location_name(char1.location_id),
        relationship_a=rel1_after,
        relationship_b=rel2_after,
        relationship_avg=avg_after,
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
                "personality_affinity": affinity.score,
                "personality_factors": render_affinity_factors(affinity.factor_keys),
                "relationship_delta": delta,
                **catalyst_payload,
                "story_hook_key": story_hook_key,
            },
            "personality_affinity": affinity.score,
            "personality_factor_keys": list(affinity.factor_keys),
            "relationship_delta": delta,
            "cause_event_ids": list(catalyst.cause_event_ids),
            **catalyst_payload,
            **({"record_id": meeting_source_id} if meeting_source_id is not None else {}),
        },
    )

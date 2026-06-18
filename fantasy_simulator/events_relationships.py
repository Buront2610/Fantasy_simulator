"""Relationship event helpers for EventSystem."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List

from .event_causality import pair_cause_event_ids
from .event_models import EventResult, generate_record_id
from .event_story import prefix_description_with_story_hook
from .i18n import tr

if TYPE_CHECKING:
    from .character import Character
    from .world import World


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


def _relationship_metadata(
    summary_key: str,
    render_params: Dict[str, Any],
    cause_event_ids: List[str],
    **extra: Any,
) -> Dict[str, Any]:
    return {
        "cause_event_ids": list(cause_event_ids),
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
    char1.update_mutual_relationship(char2, relationship_delta)
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
            },
            cause_event_ids,
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
            },
            cause_event_ids,
            relation_tag_updates=relation_tag_updates,
            record_id=marriage_source_id,
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

    if char1.age < 18 or char2.age < 18 or rel1 < 35 or rel2 < 35 or avg_rel < 40:
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
    char1.add_relation_tag(char2.char_id, tag)
    char2.add_relation_tag(char1.char_id, tag)
    return [
        {"source": char1.char_id, "target": char2.char_id, "tag": tag},
        {"source": char2.char_id, "target": char1.char_id, "tag": tag},
    ], meeting_source_id


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
    delta = rng.randint(-15, 25)
    char1.update_relationship(char2.char_id, delta)
    char2.update_relationship(char1.char_id, delta + rng.randint(-5, 5))

    rel1_after = char1.get_relationship(char2.char_id)
    rel2_after = char2.get_relationship(char1.char_id)
    avg_after = round((rel1_after + rel2_after) / 2)

    relation_tag_updates, meeting_source_id = _meeting_relation_tag_updates(char1, char2, avg_after, rng)
    description_key = _meeting_description_key(avg_after)
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
                "story_hook_key": story_hook_key,
            },
            **({"record_id": meeting_source_id} if meeting_source_id is not None else {}),
        },
    )

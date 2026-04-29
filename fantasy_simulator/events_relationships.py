"""Relationship event helpers for EventSystem."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List

from .event_models import EventResult, generate_record_id
from .i18n import tr

if TYPE_CHECKING:
    from .character import Character
    from .world import World


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
        desc = tr("marriage_anniversary", name1=char1.name, name2=char2.name)
        char1.add_history(tr("history_anniversary", year=world.year, name=char2.name))
        char2.add_history(tr("history_anniversary", year=world.year, name=char1.name))
        return EventResult(
            description=desc,
            affected_characters=[char1.char_id, char2.char_id],
            event_type="anniversary",
            year=world.year,
        )

    if char1.spouse_id not in (None, char2.char_id) or char2.spouse_id not in (None, char1.char_id):
        char1.update_mutual_relationship(char2, 3)
        desc = tr(
            "romance_commitments_blocked",
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
        )

    if char1.age < 18 or char2.age < 18 or rel1 < 60 or rel2 < 60 or avg_rel < 70:
        char1.update_mutual_relationship(char2, 10)
        desc = tr(
            "romance_growing_closer",
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
        )

    char1.spouse_id = char2.char_id
    char2.spouse_id = char1.char_id
    char1.update_mutual_relationship(char2, 20)
    marriage_source_id = generate_record_id(rng)
    char1.add_relation_tag(char2.char_id, "spouse")
    char2.add_relation_tag(char1.char_id, "spouse")
    relation_tag_updates = [
        {"source": char1.char_id, "target": char2.char_id, "tag": "spouse"},
        {"source": char2.char_id, "target": char1.char_id, "tag": "spouse"},
    ]
    stat_changes = {
        char1.char_id: {"wisdom": 2, "charisma": 1},
        char2.char_id: {"wisdom": 2, "charisma": 1},
    }
    char1.apply_stat_delta(stat_changes[char1.char_id])
    char2.apply_stat_delta(stat_changes[char2.char_id])

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
        metadata={"relation_tag_updates": relation_tag_updates, "record_id": marriage_source_id},
    )


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

    relation_tag_updates: List[Dict[str, str]] = []
    meeting_source_id = None
    if avg_after >= 50 or avg_after <= -50:
        meeting_source_id = generate_record_id(rng)
    if avg_after >= 50:
        char1.add_relation_tag(char2.char_id, "friend")
        char2.add_relation_tag(char1.char_id, "friend")
        relation_tag_updates = [
            {"source": char1.char_id, "target": char2.char_id, "tag": "friend"},
            {"source": char2.char_id, "target": char1.char_id, "tag": "friend"},
        ]
    elif avg_after <= -50:
        char1.add_relation_tag(char2.char_id, "rival")
        char2.add_relation_tag(char1.char_id, "rival")
        relation_tag_updates = [
            {"source": char1.char_id, "target": char2.char_id, "tag": "rival"},
            {"source": char2.char_id, "target": char1.char_id, "tag": "rival"},
        ]

    if avg_after > 10:
        description_key = "meeting_positive"
    elif avg_after > 0:
        description_key = "meeting_pleasant"
    elif avg_after == 0:
        description_key = "meeting_neutral"
    else:
        description_key = "meeting_negative"
    desc = tr(
        description_key,
        name1=char1.name,
        name2=char2.name,
        location=world.location_name(char1.location_id),
        relationship_a=rel1_after,
        relationship_b=rel2_after,
        relationship_avg=avg_after,
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
            **({"record_id": meeting_source_id} if meeting_source_id is not None else {}),
        },
    )

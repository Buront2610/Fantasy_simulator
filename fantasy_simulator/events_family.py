"""Family and generational event helpers."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List

from .event_causality import pair_cause_event_ids
from .character_creator import CharacterCreator
from .event_models import EventResult, generate_record_id
from .i18n import tr

if TYPE_CHECKING:
    from .character import Character
    from .world import World


BIRTH_PARENT_RELATIONSHIP_DELTA = 6


def resolve_birth_event(
    parent1: "Character",
    parent2: "Character",
    world: "World",
    rng: Any = random,
) -> EventResult:
    """Create a child for an established couple and tag the family links."""
    child = _create_child(parent1, parent2, world, rng)
    world.add_character(child, rng=rng)

    birth_source_id = generate_record_id(rng)
    relation_tag_updates = _link_family(parent1, parent2, child, birth_source_id)
    relation_tag_updates.extend(_link_parent_couple(parent1, parent2, birth_source_id))
    parent1.update_mutual_relationship(parent2, BIRTH_PARENT_RELATIONSHIP_DELTA)
    cause_event_ids = pair_cause_event_ids(
        world,
        parent1,
        parent2,
        relation_tags=("spouse", "co_parent"),
        event_kinds=("marriage", "birth"),
        limit=3,
    )
    desc = tr(
        "birth_happened",
        child=child.name,
        parent1=parent1.name,
        parent2=parent2.name,
        location=world.location_name(child.location_id),
    )
    child.add_history(tr("history_born_to_parents", year=world.year, parent1=parent1.name, parent2=parent2.name))
    parent1.add_history(tr("history_child_born", year=world.year, child=child.name, partner=parent2.name))
    parent2.add_history(tr("history_child_born", year=world.year, child=child.name, partner=parent1.name))
    return EventResult(
        description=desc,
        affected_characters=[child.char_id, parent1.char_id, parent2.char_id],
        event_type="birth",
        year=world.year,
        metadata={
            "cause_event_ids": cause_event_ids,
            "relation_tag_updates": relation_tag_updates,
            "record_id": birth_source_id,
            "summary_key": "events.birth.summary",
            "render_params": {
                "child": child.name,
                "parent1": parent1.name,
                "parent2": parent2.name,
                "location_id": child.location_id,
                "child_id": child.char_id,
                "parent_ids": [parent1.char_id, parent2.char_id],
            },
        },
    )


def _create_child(parent1: "Character", parent2: "Character", world: "World", rng: Any) -> "Character":
    creator = CharacterCreator(setting_bundle=world.setting_bundle)
    region = parent1.location_id or parent2.location_id or None
    child = creator.create_random(rng=rng, region=region)
    child.age = 0
    child.location_id = parent1.location_id or parent2.location_id
    child.race = rng.choice([parent1.race, parent2.race])
    child.job = rng.choice([parent1.job, parent2.job])
    return child


def _link_family(
    parent1: "Character",
    parent2: "Character",
    child: "Character",
    source_event_id: str,
) -> List[Dict[str, str]]:
    updates: List[Dict[str, str]] = []
    for parent in (parent1, parent2):
        parent.add_relation_tag(child.char_id, "child", source_event_id=source_event_id)
        parent.add_relation_tag(child.char_id, "family", source_event_id=source_event_id)
        child.add_relation_tag(parent.char_id, "parent", source_event_id=source_event_id)
        child.add_relation_tag(parent.char_id, "family", source_event_id=source_event_id)
        updates.extend([
            {"source": parent.char_id, "target": child.char_id, "tag": "child"},
            {"source": parent.char_id, "target": child.char_id, "tag": "family"},
            {"source": child.char_id, "target": parent.char_id, "tag": "parent"},
            {"source": child.char_id, "target": parent.char_id, "tag": "family"},
        ])
    return updates


def _link_parent_couple(
    parent1: "Character",
    parent2: "Character",
    source_event_id: str,
) -> List[Dict[str, str]]:
    updates: List[Dict[str, str]] = []
    for source, target in ((parent1, parent2), (parent2, parent1)):
        source.add_relation_tag(target.char_id, "co_parent", source_event_id=source_event_id)
        source.add_relation_tag(target.char_id, "family", source_event_id=source_event_id)
        updates.extend([
            {"source": source.char_id, "target": target.char_id, "tag": "co_parent"},
            {"source": source.char_id, "target": target.char_id, "tag": "family"},
        ])
    return updates

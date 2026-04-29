"""Solo activity event helpers for EventSystem."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, Sequence

from .event_models import EventResult
from .i18n import tr, tr_term

if TYPE_CHECKING:
    from .character import Character
    from .world import World


def resolve_discovery_event(
    char: "Character",
    world: "World",
    *,
    discovery_items: Sequence[str],
    rng: Any = random,
) -> EventResult:
    """Resolve a discovery event for one character."""
    item = rng.choice(list(discovery_items))
    stat_gains: Dict[str, int]
    roll = rng.random()
    if roll < 0.4:
        stat_gains = {"intelligence": rng.randint(1, 4), "wisdom": rng.randint(0, 3)}
        extra = tr("discovery_extra_knowledge")
    elif roll < 0.7:
        stat_gains = {"strength": rng.randint(1, 3), "dexterity": rng.randint(0, 2)}
        extra = tr("discovery_extra_battle")
    else:
        stat_gains = {"charisma": rng.randint(1, 4)}
        extra = tr("discovery_extra_reputation")

    char.apply_stat_delta(stat_gains)
    skill_candidates = list(char.skills.keys()) or ["Dungeoneering"]
    trained_skill = rng.choice(skill_candidates)
    char.level_up_skill(trained_skill)

    localized_item = tr_term(item)
    loc_name = world.location_name(char.location_id)
    desc = tr("discovery_narrative", name=char.name, item=localized_item, location=loc_name, extra=extra)
    char.add_history(tr("history_discovery", year=world.year, item=localized_item, location=loc_name))
    return EventResult(
        description=desc,
        affected_characters=[char.char_id],
        stat_changes={char.char_id: stat_gains},
        event_type="discovery",
        year=world.year,
    )


def resolve_skill_training_event(
    char: "Character",
    world: "World",
    *,
    all_skills: Sequence[str],
    rng: Any = random,
) -> EventResult:
    """Resolve skill practice for one character."""
    if not char.skills:
        starter = rng.choice(list(all_skills))
        char.skills[starter] = 0

    skill = rng.choice(list(char.skills.keys()))
    old_level = char.skills[skill]
    char.level_up_skill(skill)
    new_level = char.skills[skill]

    stat_bonus: Dict[str, int] = {}
    if skill in ("Swordsmanship", "Unarmed Combat", "Heavy Armor"):
        stat_bonus = {"strength": 1}
    elif skill in ("Fireball", "Spellcraft", "Mana Control", "Arcane Shield"):
        stat_bonus = {"intelligence": 1}
    elif skill in ("Stealth", "Evasion", "Backstab"):
        stat_bonus = {"dexterity": 1}
    elif skill in ("Holy Light", "Regeneration", "Purify", "Commune"):
        stat_bonus = {"wisdom": 1}
    elif skill in ("Persuasion", "Charm Song", "Inspire"):
        stat_bonus = {"charisma": 1}

    char.apply_stat_delta(stat_bonus)
    effort = rng.choice(
        [
            tr("training_effort_yard"),
            tr("training_effort_meditated"),
            tr("training_effort_master"),
            tr("training_effort_tireless"),
            tr("training_effort_scrolls"),
            tr("training_effort_limits"),
        ]
    )
    localized_skill = tr_term(skill)
    desc = tr(
        "training_narrative",
        name=char.name,
        effort=effort,
        skill=localized_skill,
        old_level=old_level,
        new_level=new_level,
    )
    char.add_history(tr("history_trained_skill", year=world.year, skill=localized_skill, new_level=new_level))
    return EventResult(
        description=desc,
        affected_characters=[char.char_id],
        stat_changes={char.char_id: stat_bonus} if stat_bonus else {},
        event_type="skill_training",
        year=world.year,
    )


def resolve_journey_event(
    char: "Character",
    world: "World",
    *,
    journey_events: Sequence[str],
    rng: Any = random,
) -> EventResult:
    """Resolve one character traveling through the world graph."""
    neighbours = world.get_neighboring_locations(char.location_id)
    if not neighbours and not world.routes:
        neighbours = list(world.grid.values())
    if not neighbours:
        return EventResult(
            description=tr("journey_no_destination", name=char.name),
            affected_characters=[char.char_id],
            event_type="journey",
            year=world.year,
        )

    destination = rng.choice(neighbours)
    old_location_id = char.location_id
    char.location_id = destination.id
    world.mark_location_visited(destination.id)

    road_event = rng.choice(list(journey_events))
    desc = tr(
        "journey_narrative",
        name=char.name,
        old_location=world.location_name(old_location_id),
        destination=destination.name,
        region_type=tr_term(destination.region_type),
        road_event=road_event,
    )
    char.add_history(tr(
        "history_travelled",
        year=world.year,
        old_location=world.location_name(old_location_id),
        destination=destination.name,
    ))

    extra_changes: Dict[str, int] = {}
    if destination.region_type == "dungeon":
        bonus = rng.choice(["strength", "dexterity", "intelligence"])
        extra_changes[bonus] = rng.randint(1, 4)
        char.apply_stat_delta(extra_changes)
        desc += " " + tr("journey_dungeon_bonus", amount=extra_changes[bonus], stat=bonus)

    return EventResult(
        description=desc,
        affected_characters=[char.char_id],
        stat_changes={char.char_id: extra_changes} if extra_changes else {},
        event_type="journey",
        year=world.year,
    )

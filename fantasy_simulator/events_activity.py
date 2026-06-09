"""Solo activity event helpers for EventSystem."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, Sequence

from .event_models import EventResult
from .event_story import prefix_description_with_story_hook
from .i18n import tr, tr_for_locale, tr_term

if TYPE_CHECKING:
    from .character import Character
    from .world import World


_TRAINING_EFFORT_KEYS = [
    "training_effort_yard",
    "training_effort_meditated",
    "training_effort_master",
    "training_effort_tireless",
    "training_effort_scrolls",
    "training_effort_limits",
]


def _journey_no_destination_result(char: "Character", world: "World") -> EventResult:
    return EventResult(
        description=tr("journey_no_destination", name=char.name),
        affected_characters=[char.char_id],
        event_type="journey",
        year=world.year,
        metadata={
            "summary_key": "events.journey_no_destination.summary",
            "render_params": {"name": char.name},
        },
    )


def _road_event_params(road_event: str, journey_events: Sequence[str]) -> Dict[str, str]:
    journey_event_list = list(journey_events)
    try:
        candidate_key = f"journey_road_event_{journey_event_list.index(road_event)}"
    except ValueError:
        return {"road_event": road_event}
    if tr_for_locale("en", candidate_key) == road_event:
        return {"road_event_key": candidate_key}
    return {"road_event": road_event}


def _journey_dungeon_bonus(
    char: "Character",
    destination: Any,
    rng: Any,
) -> tuple[Dict[str, int], str, Dict[str, int | str]]:
    if destination.region_type != "dungeon":
        return {}, "", {}
    bonus = rng.choice(["strength", "dexterity", "intelligence"])
    extra_changes = {bonus: rng.randint(1, 4)}
    char.apply_stat_delta(extra_changes)
    rendered_bonus = " " + tr("journey_dungeon_bonus", amount=extra_changes[bonus], stat=bonus)
    return extra_changes, rendered_bonus, {"amount": extra_changes[bonus], "stat": bonus}


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
        extra_key = "discovery_extra_knowledge"
    elif roll < 0.7:
        stat_gains = {"strength": rng.randint(1, 3), "dexterity": rng.randint(0, 2)}
        extra_key = "discovery_extra_battle"
    else:
        stat_gains = {"charisma": rng.randint(1, 4)}
        extra_key = "discovery_extra_reputation"
    extra = tr(extra_key)

    char.apply_stat_delta(stat_gains)
    skill_candidates = list(char.skills.keys()) or ["Dungeoneering"]
    trained_skill = rng.choice(skill_candidates)
    char.level_up_skill(trained_skill)

    localized_item = tr_term(item)
    loc_name = world.location_name(char.location_id)
    desc = tr("discovery_narrative", name=char.name, item=localized_item, location=loc_name, extra=extra)
    desc, story_hook_key = prefix_description_with_story_hook(
        "discovery", rng, desc, name=char.name, item=localized_item, location=loc_name
    )
    char.add_history(tr("history_discovery", year=world.year, item=localized_item, location=loc_name))
    return EventResult(
        description=desc,
        affected_characters=[char.char_id],
        stat_changes={char.char_id: stat_gains},
        event_type="discovery",
        year=world.year,
        metadata={
            "summary_key": "events.discovery.summary",
            "render_params": {
                "name": char.name,
                "item": item,
                "location_id": char.location_id,
                "extra_key": extra_key,
                "story_hook_key": story_hook_key,
            },
        },
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
    effort_key = rng.choice(_TRAINING_EFFORT_KEYS)
    effort = tr(effort_key)
    localized_skill = tr_term(skill)
    desc = tr(
        "training_narrative",
        name=char.name,
        effort=effort,
        skill=localized_skill,
        old_level=old_level,
        new_level=new_level,
    )
    desc, story_hook_key = prefix_description_with_story_hook(
        "skill_training", rng, desc, name=char.name, skill=localized_skill
    )
    char.add_history(tr("history_trained_skill", year=world.year, skill=localized_skill, new_level=new_level))
    return EventResult(
        description=desc,
        affected_characters=[char.char_id],
        stat_changes={char.char_id: stat_bonus} if stat_bonus else {},
        event_type="skill_training",
        year=world.year,
        metadata={
            "summary_key": "events.skill_training.summary",
            "render_params": {
                "name": char.name,
                "effort_key": effort_key,
                "skill": skill,
                "old_level": old_level,
                "new_level": new_level,
                "story_hook_key": story_hook_key,
            },
        },
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
        return _journey_no_destination_result(char, world)

    destination = rng.choice(neighbours)
    old_location_id = char.location_id
    char.location_id = destination.id
    world.mark_location_visited(destination.id)

    road_event = rng.choice(list(journey_events))
    road_event_params = _road_event_params(road_event, journey_events)
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

    extra_changes, dungeon_bonus, dungeon_bonus_params = _journey_dungeon_bonus(char, destination, rng)
    desc += dungeon_bonus

    render_params: Dict[str, Any] = {
        "name": char.name,
        "from_location_id": old_location_id,
        "to_location_id": destination.id,
        "region_type": destination.region_type,
        "dungeon_bonus_params": dungeon_bonus_params,
        **road_event_params,
    }
    desc, story_hook_key = prefix_description_with_story_hook(
        "journey",
        rng,
        desc,
        name=char.name,
        old_location=world.location_name(old_location_id),
        destination=destination.name,
    )
    render_params["story_hook_key"] = story_hook_key

    return EventResult(
        description=desc,
        affected_characters=[char.char_id],
        stat_changes={char.char_id: extra_changes} if extra_changes else {},
        event_type="journey",
        year=world.year,
        metadata={
            "summary_key": "events.journey.summary",
            "render_params": render_params,
        },
    )

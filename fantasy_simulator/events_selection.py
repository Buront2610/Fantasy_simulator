"""Random event selection helpers for EventSystem."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .event_models import EventResult

if TYPE_CHECKING:
    from .character import Character
    from .events import EventSystem
    from .world import World


EVENT_WEIGHTS: Dict[str, int] = {
    "meeting": 30,
    "journey": 25,
    "skill_training": 20,
    "discovery": 10,
    "battle": 15,
    "marriage": 5,
}


def eligible_random_event_characters(characters: List["Character"]) -> List["Character"]:
    """Return characters eligible for ambient random events."""
    return [
        char
        for char in characters
        if char.alive and char.active_adventure_id is None and char.injury_status != "dying"
    ]


def find_collocated_pair(alive: List["Character"], rng: Any = random) -> Optional[Tuple["Character", "Character"]]:
    """Pick two eligible characters from the same location, if any."""
    by_loc: Dict[str, List["Character"]] = {}
    for character in alive:
        group = by_loc.setdefault(character.location_id, [])
        group.append(character)
    valid = [chars for chars in by_loc.values() if len(chars) >= 2]
    if not valid:
        return None
    group = rng.choice(valid)
    char1, char2 = rng.sample(group, 2)
    return char1, char2


def generate_random_event(
    event_system: "EventSystem",
    characters: List["Character"],
    world: "World",
    rng: Any = random,
) -> Optional[EventResult]:
    """Choose and resolve one ambient random event."""
    eligible = eligible_random_event_characters(characters)
    if not eligible:
        return None

    event_types = list(EVENT_WEIGHTS.keys())
    weights = [EVENT_WEIGHTS[event_type] for event_type in event_types]
    chosen_type = rng.choices(event_types, weights=weights, k=1)[0]

    if chosen_type in ("marriage", "battle", "meeting"):
        pair = find_collocated_pair(eligible, rng=rng)
        if pair is None:
            chosen_type = rng.choice(["skill_training", "discovery", "journey"])
        else:
            char1, char2 = pair
            if chosen_type == "marriage":
                return event_system.event_marriage(char1, char2, world, rng=rng)
            if chosen_type == "battle":
                return event_system.event_battle(char1, char2, world, rng=rng)
            return event_system.event_meeting(char1, char2, world, rng=rng)

    char = rng.choice(eligible)
    if chosen_type == "discovery":
        return event_system.event_discovery(char, world, rng=rng)
    if chosen_type == "skill_training":
        return event_system.event_skill_training(char, world, rng=rng)
    if chosen_type == "journey":
        return event_system.event_journey(char, world, rng=rng)
    return event_system.event_skill_training(char, world, rng=rng)

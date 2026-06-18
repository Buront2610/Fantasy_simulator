"""Random event selection helpers for EventSystem."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .event_models import EventResult
from .events_family import resolve_birth_event
from .simulation.population import has_population_capacity

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
BIRTH_EVENT_WEIGHT = 3


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


def find_romance_pair(alive: List["Character"], rng: Any = random) -> Optional[Tuple["Character", "Character"]]:
    """Pick a collocated unmarried pair, preferring existing affection."""
    pairs: List[Tuple["Character", "Character"]] = []
    weights: List[float] = []
    by_loc: Dict[str, List["Character"]] = {}
    for character in alive:
        by_loc.setdefault(character.location_id, []).append(character)
    for group in by_loc.values():
        for index, char1 in enumerate(group):
            if char1.spouse_id is not None:
                continue
            for char2 in group[index + 1:]:
                if char2.spouse_id is not None:
                    continue
                avg_rel = (char1.get_relationship(char2.char_id) + char2.get_relationship(char1.char_id)) / 2
                pairs.append((char1, char2))
                weights.append(max(1.0, 1.0 + avg_rel))
    if not pairs:
        return find_collocated_pair(alive, rng=rng)
    return rng.choices(pairs, weights=weights, k=1)[0]


def birth_pairs(alive: List["Character"]) -> List[Tuple["Character", "Character"]]:
    """Return collocated married pairs eligible for a generational event."""
    pairs: List[Tuple["Character", "Character"]] = []
    seen: set[frozenset[str]] = set()
    by_id = {char.char_id: char for char in alive}
    for char in alive:
        if char.age < 18 or not char.spouse_id:
            continue
        spouse = by_id.get(char.spouse_id)
        if spouse is None or spouse.age < 18 or spouse.location_id != char.location_id:
            continue
        pair_key = frozenset((char.char_id, spouse.char_id))
        if pair_key in seen:
            continue
        seen.add(pair_key)
        pairs.append((char, spouse))
    return pairs


def find_birth_pair(alive: List["Character"], rng: Any = random) -> Optional[Tuple["Character", "Character"]]:
    """Pick a collocated married pair for a generational event."""
    pairs = birth_pairs(alive)
    if not pairs:
        return None
    return rng.choice(pairs)


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
    if has_population_capacity(world) and birth_pairs(eligible):
        event_types.append("birth")
        weights.append(BIRTH_EVENT_WEIGHT)
    chosen_type = rng.choices(event_types, weights=weights, k=1)[0]

    if chosen_type == "birth":
        pair = find_birth_pair(eligible, rng=rng)
        if pair is not None:
            return resolve_birth_event(pair[0], pair[1], world, rng=rng)
        chosen_type = rng.choice(["skill_training", "discovery", "journey"])

    if chosen_type in ("marriage", "battle", "meeting"):
        pair = (
            find_romance_pair(eligible, rng=rng)
            if chosen_type == "marriage"
            else find_collocated_pair(eligible, rng=rng)
        )
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

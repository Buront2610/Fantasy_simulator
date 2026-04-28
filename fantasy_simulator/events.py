"""
events.py - Event system for the Fantasy Simulator.

Each event handler returns an EventResult describing what happened.
The EventSystem.generate_random_event method is called once per
simulation tick to drive the narrative.
"""

from __future__ import annotations

import random
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from .content.world_data import ALL_SKILLS, DISCOVERY_ITEMS, JOURNEY_EVENTS
from .death_resolution import handle_death_side_effects
from .event_models import EventResult, WorldEventRecord, generate_record_id
from .events_activity import resolve_discovery_event, resolve_journey_event, resolve_skill_training_event
from .events_combat import resolve_battle_event
from .events_lifecycle import (
    check_dying_resolution,
    check_natural_death,
    resolve_aging_event,
    resolve_death_event,
)
from .events_relationships import resolve_marriage_event, resolve_meeting_event
from .events_selection import EVENT_WEIGHTS, find_collocated_pair, generate_random_event

if TYPE_CHECKING:
    from .character import Character
    from .world import World


__all__ = ["EventResult", "WorldEventRecord", "generate_record_id", "EventSystem"]


class EventSystem:
    """Generates and resolves world events."""

    _EVENT_WEIGHTS: Dict[str, int] = EVENT_WEIGHTS

    @staticmethod
    def _new_relation_source_id(prefix: str, rng: Any = random) -> str:
        if hasattr(rng, "getrandbits"):
            return f"{prefix}_{rng.getrandbits(48):012x}"
        return f"{prefix}_{uuid.uuid4().hex[:12]}"

    def event_marriage(self, char1: Character, char2: Character, world: World, rng: Any = random) -> EventResult:
        """Two characters with strong mutual affection may get married."""
        return resolve_marriage_event(char1, char2, world, rng=rng)

    def event_battle(self, char1: Character, char2: Character, world: World, rng: Any = random) -> EventResult:
        """Two characters fight. Winner determined by combat power + luck.

        Death staging (design §8): instead of instant death, the loser's
        injury worsens one stage. Only dying characters with low constitution
        can actually die from a battle.
        """
        return resolve_battle_event(char1, char2, world, event_death=self.event_death, rng=rng)

    def event_discovery(self, char: Character, world: World, rng: Any = random) -> EventResult:
        return resolve_discovery_event(char, world, discovery_items=DISCOVERY_ITEMS, rng=rng)

    def event_meeting(self, char1: Character, char2: Character, world: World, rng: Any = random) -> EventResult:
        return resolve_meeting_event(char1, char2, world, rng=rng)

    def event_aging(self, char: Character, world: World, rng: Any = random) -> EventResult:
        return resolve_aging_event(char, world, rng=rng)

    def handle_death_side_effects(self, char: Character, world: World) -> None:
        """Apply post-death side effects such as notifying the surviving spouse.

        This is safe to call on any dead character; it is idempotent with
        respect to spouse cleanup because it checks ``char.spouse_id`` and
        ``spouse.spouse_id`` before mutating anything.
        """
        handle_death_side_effects(char, world)

    def event_death(self, char: Character, world: World, rng: Any = random) -> EventResult:
        return resolve_death_event(char, world, rng=rng)

    def event_skill_training(self, char: Character, world: World, rng: Any = random) -> EventResult:
        return resolve_skill_training_event(char, world, all_skills=ALL_SKILLS, rng=rng)

    def event_journey(self, char: Character, world: World, rng: Any = random) -> EventResult:
        return resolve_journey_event(char, world, journey_events=JOURNEY_EVENTS, rng=rng)

    def check_natural_death(
        self,
        char: Character,
        world: World,
        rng: Any = random,
        year_fraction: float = 1.0,
    ) -> Optional[EventResult]:
        return check_natural_death(
            char,
            world,
            event_death=self.event_death,
            rng=rng,
            year_fraction=year_fraction,
        )

    def check_dying_resolution(
        self,
        char: Character,
        world: World,
        rng: Any = random,
        year_fraction: float = 1.0,
    ) -> Optional[EventResult]:
        """Resolve dying characters: rescue or death (design §8.3).

        Dying characters have a chance to be rescued (based on location safety,
        nearby allies, and constitution) or die. This replaces instant death
        with a window for intervention.
        """
        return check_dying_resolution(
            char,
            world,
            event_death=self.event_death,
            rng=rng,
            year_fraction=year_fraction,
        )

    def generate_random_event(
        self, characters: List[Character], world: World, rng: Any = random
    ) -> Optional[EventResult]:
        return generate_random_event(self, characters, world, rng=rng)

    @staticmethod
    def _find_collocated_pair(alive: List[Character], rng: Any = random) -> Optional[Tuple[Character, Character]]:
        return find_collocated_pair(alive, rng=rng)

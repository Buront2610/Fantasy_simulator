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
from .events_lifecycle import (
    check_dying_resolution,
    check_natural_death,
    resolve_aging_event,
    resolve_death_event,
)
from .events_relationships import resolve_marriage_event, resolve_meeting_event
from .events_selection import EVENT_WEIGHTS, find_collocated_pair, generate_random_event
from .i18n import tr

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
        power1 = char1.combat_power + rng.randint(0, 30)
        power2 = char2.combat_power + rng.randint(0, 30)
        winner, loser = (char1, char2) if power1 >= power2 else (char2, char1)

        winner_gains = {"strength": rng.randint(1, 3), "constitution": rng.randint(0, 2)}
        loser_losses = {"constitution": -rng.randint(2, 8), "strength": -rng.randint(0, 3)}
        winner.apply_stat_delta(winner_gains)
        loser.apply_stat_delta(loser_losses)
        winner.update_mutual_relationship(loser, -20, delta_other=-30)
        # Relation tags: mark as rival with source tracking (§7.4)
        event_source_id = generate_record_id(rng)
        winner.add_relation_tag(loser.char_id, "rival")
        loser.add_relation_tag(winner.char_id, "rival")
        relation_tag_updates = [
            {"source": winner.char_id, "target": loser.char_id, "tag": "rival"},
            {"source": loser.char_id, "target": winner.char_id, "tag": "rival"},
        ]

        # Death staging: worsen injury instead of instant death
        old_status = loser.injury_status
        loser.worsen_injury()
        # Only dying characters with low constitution may die
        loser_died = loser.injury_status == "dying" and loser.constitution <= 5 and rng.random() < 0.4
        if loser_died:
            self.event_death(loser, world, rng=rng)
            desc = tr("battle_fatal", winner=winner.name, loser=loser.name)
            winner.add_history(tr(
                "history_battle_fatal", year=world.year, name=loser.name,
                location=world.location_name(winner.location_id),
            ))
            return EventResult(
                description=desc,
                affected_characters=[winner.char_id, loser.char_id],
                stat_changes={winner.char_id: winner_gains, loser.char_id: loser_losses},
                event_type="battle_fatal",
                year=world.year,
                metadata={"relation_tag_updates": relation_tag_updates, "record_id": event_source_id},
            )

        # Report injury worsening
        injury_key = f"battle_injury_{loser.injury_status}"
        desc = tr("battle_normal", winner=winner.name, loser=loser.name)
        if loser.injury_status != old_status and loser.injury_status != "none":
            desc += " " + tr(injury_key, name=loser.name)
        winner.add_history(tr(
            "history_battle_win", year=world.year, name=loser.name,
            location=world.location_name(winner.location_id),
        ))
        loser.add_history(tr(
            "history_battle_loss", year=world.year, name=winner.name,
            location=world.location_name(loser.location_id),
        ))
        return EventResult(
            description=desc,
            affected_characters=[winner.char_id, loser.char_id],
            stat_changes={winner.char_id: winner_gains, loser.char_id: loser_losses},
            event_type="battle",
            year=world.year,
            metadata={"relation_tag_updates": relation_tag_updates, "record_id": event_source_id},
        )

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

"""
events.py - Event system for the Fantasy Simulator.

Each event handler returns an EventResult describing what happened.
The EventSystem.generate_random_event method is called once per
simulation tick to drive the narrative.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from world_data import (
    BATTLE_OUTCOMES_LOSE,
    BATTLE_OUTCOMES_WIN,
    DISCOVERY_ITEMS,
    JOURNEY_EVENTS,
)
from i18n import tr, tr_term


@dataclass
class EventResult:
    """The outcome of a single in-world event."""

    description: str
    affected_characters: List[str] = field(default_factory=list)
    stat_changes: Dict[str, Dict[str, int]] = field(default_factory=dict)
    event_type: str = "generic"
    year: int = 0


class EventSystem:
    """Generates and resolves world events."""

    _EVENT_WEIGHTS: Dict[str, int] = {
        "meeting": 30,
        "journey": 25,
        "skill_training": 20,
        "discovery": 10,
        "battle": 15,
        "aging": 10,
        "marriage": 5,
    }

    def event_marriage(self, char1: Any, char2: Any, world: Any, rng: Any = random) -> EventResult:
        """Two characters with strong mutual affection may get married."""
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
            char1.update_relationship(char2.char_id, 3)
            char2.update_relationship(char1.char_id, 3)
            desc = tr(
                "romance_commitments_blocked",
                name1=char1.name,
                name2=char2.name,
                location=char1.location,
            )
            return EventResult(
                description=desc,
                affected_characters=[char1.char_id, char2.char_id],
                stat_changes={},
                event_type="romance",
                year=world.year,
            )

        if char1.age < 18 or char2.age < 18 or rel1 < 60 or rel2 < 60 or avg_rel < 70:
            char1.update_relationship(char2.char_id, 10)
            char2.update_relationship(char1.char_id, 10)
            desc = tr(
                "romance_growing_closer",
                name1=char1.name,
                name2=char2.name,
                location=char1.location,
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
        char1.update_relationship(char2.char_id, 20)
        char2.update_relationship(char1.char_id, 20)
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
            location=char1.location,
        )
        char1.add_history(tr("history_married", year=world.year, name=char2.name, location=char1.location))
        char2.add_history(tr("history_married", year=world.year, name=char1.name, location=char2.location))
        return EventResult(
            description=desc,
            affected_characters=[char1.char_id, char2.char_id],
            stat_changes=stat_changes,
            event_type="marriage",
            year=world.year,
        )

    def event_battle(self, char1: Any, char2: Any, world: Any, rng: Any = random) -> EventResult:
        """Two characters fight. Winner is determined by combat power + luck."""
        power1 = char1.combat_power + rng.randint(0, 30)
        power2 = char2.combat_power + rng.randint(0, 30)
        winner, loser = (char1, char2) if power1 >= power2 else (char2, char1)

        win_desc = rng.choice(BATTLE_OUTCOMES_WIN)
        lose_desc = rng.choice(BATTLE_OUTCOMES_LOSE)

        winner_gains = {"strength": rng.randint(1, 3), "constitution": rng.randint(0, 2)}
        loser_losses = {"constitution": -rng.randint(2, 8), "strength": -rng.randint(0, 3)}
        winner.apply_stat_delta(winner_gains)
        loser.apply_stat_delta(loser_losses)
        winner.update_relationship(loser.char_id, -20)
        loser.update_relationship(winner.char_id, -30)

        loser_died = loser.constitution <= 5 and rng.random() < 0.4
        if loser_died:
            self.event_death(loser, world, rng=rng)
            desc = tr("battle_fatal", winner=winner.name, loser=loser.name)
            winner.add_history(tr("history_battle_fatal", year=world.year, name=loser.name, location=winner.location))
            return EventResult(
                description=desc,
                affected_characters=[winner.char_id, loser.char_id],
                stat_changes={winner.char_id: winner_gains, loser.char_id: loser_losses},
                event_type="battle_fatal",
                year=world.year,
            )

        desc = tr("battle_normal", winner=winner.name, loser=loser.name)
        winner.add_history(tr("history_battle_win", year=world.year, name=loser.name, location=winner.location))
        loser.add_history(tr("history_battle_loss", year=world.year, name=winner.name, location=loser.location))
        return EventResult(
            description=desc,
            affected_characters=[winner.char_id, loser.char_id],
            stat_changes={winner.char_id: winner_gains, loser.char_id: loser_losses},
            event_type="battle",
            year=world.year,
        )

    def event_discovery(self, char: Any, world: Any, rng: Any = random) -> EventResult:
        item = rng.choice(DISCOVERY_ITEMS)
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
        desc = tr("discovery_narrative", name=char.name, item=localized_item, location=char.location, extra=extra)
        char.add_history(tr("history_discovery", year=world.year, item=localized_item, location=char.location))
        return EventResult(
            description=desc,
            affected_characters=[char.char_id],
            stat_changes={char.char_id: stat_gains},
            event_type="discovery",
            year=world.year,
        )

    def event_meeting(self, char1: Any, char2: Any, world: Any, rng: Any = random) -> EventResult:
        delta = rng.randint(-15, 25)
        char1.update_relationship(char2.char_id, delta)
        char2.update_relationship(char1.char_id, delta + rng.randint(-5, 5))

        rel1_after = char1.get_relationship(char2.char_id)
        rel2_after = char2.get_relationship(char1.char_id)
        avg_after = round((rel1_after + rel2_after) / 2)

        if avg_after > 10:
            desc = tr(
                "meeting_positive",
                name1=char1.name,
                name2=char2.name,
                location=char1.location,
                relationship_a=rel1_after,
                relationship_b=rel2_after,
                relationship_avg=avg_after,
            )
        elif avg_after > 0:
            desc = tr(
                "meeting_pleasant",
                name1=char1.name,
                name2=char2.name,
                location=char1.location,
                relationship_a=rel1_after,
                relationship_b=rel2_after,
                relationship_avg=avg_after,
            )
        elif avg_after == 0:
            desc = tr(
                "meeting_neutral",
                name1=char1.name,
                name2=char2.name,
                location=char1.location,
                relationship_a=rel1_after,
                relationship_b=rel2_after,
                relationship_avg=avg_after,
            )
        else:
            desc = tr(
                "meeting_negative",
                name1=char1.name,
                name2=char2.name,
                location=char1.location,
                relationship_a=rel1_after,
                relationship_b=rel2_after,
                relationship_avg=avg_after,
            )
        char1.add_history(tr("history_met", year=world.year, name=char2.name, location=char1.location))
        char2.add_history(tr("history_met", year=world.year, name=char1.name, location=char2.location))
        return EventResult(
            description=desc,
            affected_characters=[char1.char_id, char2.char_id],
            event_type="meeting",
            year=world.year,
        )

    def event_aging(self, char: Any, world: Any, rng: Any = random) -> EventResult:
        char.age += 1
        if char.age < 30:
            stat_changes = {
                "strength": rng.randint(0, 2),
                "intelligence": rng.randint(0, 2),
                "dexterity": rng.randint(0, 1),
                "wisdom": rng.randint(0, 1),
            }
            desc = tr("aging_young", name=char.name, age=char.age)
        elif char.age < 50:
            stat_changes = {
                "intelligence": rng.randint(0, 2),
                "wisdom": rng.randint(0, 2),
                "strength": rng.randint(-1, 1),
            }
            desc = tr("aging_prime", name=char.name, age=char.age)
        elif char.age < char.max_age * 0.75:
            stat_changes = {
                "wisdom": rng.randint(1, 3),
                "charisma": rng.randint(0, 1),
                "dexterity": -rng.randint(0, 2),
                "strength": -rng.randint(0, 1),
            }
            desc = tr("aging_middle", name=char.name, age=char.age)
        else:
            stat_changes = {
                "wisdom": rng.randint(0, 2),
                "strength": -rng.randint(1, 3),
                "dexterity": -rng.randint(1, 3),
                "constitution": -rng.randint(1, 4),
            }
            desc = tr("aging_old", name=char.name, age=char.age)

        char.apply_stat_delta(stat_changes)
        char.add_history(tr("history_turned_age", year=world.year, age=char.age))
        return EventResult(
            description=desc,
            affected_characters=[char.char_id],
            stat_changes={char.char_id: stat_changes},
            event_type="aging",
            year=world.year,
        )

    def event_death(self, char: Any, world: Any, rng: Any = random) -> EventResult:
        char.alive = False
        char.active_adventure_id = None
        if char.spouse_id:
            spouse = world.get_character_by_id(char.spouse_id)
            if spouse and spouse.alive:
                spouse.update_relationship(char.char_id, -50)
                spouse.add_history(tr("history_lost_spouse", year=world.year, name=char.name))
                spouse.spouse_id = None

        cause_options = [
            tr("death_cause_old_age"),
            tr("death_cause_monster", location=char.location),
            tr("death_cause_illness"),
            tr("death_cause_protecting"),
            tr("death_cause_dungeon"),
            tr("death_cause_road"),
        ]
        cause = cause_options[0] if char.age >= char.max_age * 0.9 else rng.choice(cause_options[1:])
        desc = tr("death_narrative", name=char.name, race=char.race, job=char.job, age=char.age, cause=cause)
        char.add_history(tr("history_passed_away", year=world.year, cause=cause))
        return EventResult(
            description=desc,
            affected_characters=[char.char_id],
            event_type="death",
            year=world.year,
        )

    def event_skill_training(self, char: Any, world: Any, rng: Any = random) -> EventResult:
        if not char.skills:
            from world_data import ALL_SKILLS

            starter = rng.choice(ALL_SKILLS)
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

    def event_journey(self, char: Any, world: Any, rng: Any = random) -> EventResult:
        neighbours = world.get_neighboring_locations(char.location)
        if not neighbours:
            neighbours = list(world.grid.values())

        destination = rng.choice(neighbours)
        old_location = char.location
        char.location = destination.name

        road_event = rng.choice(JOURNEY_EVENTS)
        desc = tr(
            "journey_narrative",
            name=char.name,
            old_location=old_location,
            destination=destination.name,
            region_type=destination.region_type,
            road_event=road_event,
        )
        char.add_history(tr("history_travelled", year=world.year, old_location=old_location, destination=destination.name))

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

    def check_natural_death(self, char: Any, world: Any, rng: Any = random) -> Optional[EventResult]:
        if not char.alive:
            return None
        age_ratio = char.age / max(char.max_age, 1)
        con_factor = (100 - char.constitution) / 100 * 0.5 + 0.5
        death_chance = max(0.0, (age_ratio - 0.6) / 0.4) ** 2 * con_factor
        if rng.random() < death_chance:
            return self.event_death(char, world, rng=rng)
        return None

    def generate_random_event(self, characters: List[Any], world: Any, rng: Any = random) -> Optional[EventResult]:
        alive = [c for c in characters if c.alive]
        if not alive:
            return None

        event_types = list(self._EVENT_WEIGHTS.keys())
        weights = [self._EVENT_WEIGHTS[e] for e in event_types]
        chosen_type = rng.choices(event_types, weights=weights, k=1)[0]

        if chosen_type in ("marriage", "battle", "meeting"):
            pair = self._find_collocated_pair(alive, rng=rng)
            if pair is None:
                chosen_type = rng.choice(["skill_training", "discovery", "journey", "aging"])
            else:
                char1, char2 = pair
                if chosen_type == "marriage":
                    return self.event_marriage(char1, char2, world, rng=rng)
                if chosen_type == "battle":
                    return self.event_battle(char1, char2, world, rng=rng)
                return self.event_meeting(char1, char2, world, rng=rng)

        char = rng.choice(alive)
        if chosen_type == "discovery":
            return self.event_discovery(char, world, rng=rng)
        if chosen_type == "skill_training":
            return self.event_skill_training(char, world, rng=rng)
        if chosen_type == "journey":
            return self.event_journey(char, world, rng=rng)
        if chosen_type == "aging":
            return self.event_aging(char, world, rng=rng)
        return self.event_skill_training(char, world, rng=rng)

    @staticmethod
    def _find_collocated_pair(alive: List[Any], rng: Any = random) -> Optional[Tuple[Any, Any]]:
        by_loc: Dict[str, List[Any]] = {}
        for c in alive:
            by_loc.setdefault(c.location, []).append(c)
        valid = [chars for chars in by_loc.values() if len(chars) >= 2]
        if not valid:
            return None
        group = rng.choice(valid)
        pair = rng.sample(group, 2)
        return pair[0], pair[1]

"""
events.py - Event system for the Fantasy Simulator.

Each event handler returns an EventResult describing what happened.
The EventSystem.generate_random_event method is called once per
simulation tick to drive the narrative.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from world_data import (
    DISCOVERY_ITEMS,
    JOURNEY_EVENTS,
)
from i18n import tr, tr_term

if TYPE_CHECKING:
    from character import Character
    from world import World


def _generate_record_id(rng: Optional[Any] = None) -> str:
    if rng is not None and hasattr(rng, "getrandbits"):
        return format(rng.getrandbits(128), "032x")
    return uuid.uuid4().hex


@dataclass
class EventResult:
    """The outcome of a single in-world event."""

    description: str
    affected_characters: List[str] = field(default_factory=list)
    stat_changes: Dict[str, Dict[str, int]] = field(default_factory=dict)
    event_type: str = "generic"
    year: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "affected_characters": list(self.affected_characters),
            "stat_changes": self.stat_changes,
            "event_type": self.event_type,
            "year": self.year,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventResult":
        return cls(
            description=data["description"],
            affected_characters=list(data.get("affected_characters", [])),
            stat_changes=data.get("stat_changes", {}),
            event_type=data.get("event_type", "generic"),
            year=data.get("year", 0),
        )


@dataclass
class WorldEventRecord:
    """A structured record of a world event for history and analysis.

    Unlike EventResult (which is consumed immediately by the simulation loop),
    WorldEventRecord is designed for long-term storage and querying.
    """

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    kind: str = "generic"
    year: int = 0
    location_id: Optional[str] = None
    primary_actor_id: Optional[str] = None
    secondary_actor_ids: List[str] = field(default_factory=list)
    description: str = ""
    severity: int = 1
    visibility: str = "public"

    def __post_init__(self) -> None:
        self.severity = max(1, min(5, self.severity))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "kind": self.kind,
            "year": self.year,
            "location_id": self.location_id,
            "primary_actor_id": self.primary_actor_id,
            "secondary_actor_ids": list(self.secondary_actor_ids),
            "description": self.description,
            "severity": self.severity,
            "visibility": self.visibility,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldEventRecord":
        return cls(
            record_id=data.get("record_id", uuid.uuid4().hex),
            kind=data.get("kind", "generic"),
            year=data.get("year", 0),
            location_id=data.get("location_id"),
            primary_actor_id=data.get("primary_actor_id"),
            secondary_actor_ids=list(data.get("secondary_actor_ids", [])),
            description=data.get("description", ""),
            severity=data.get("severity", 1),
            visibility=data.get("visibility", "public"),
        )

    @classmethod
    def from_event_result(
        cls,
        result: EventResult,
        location_id: Optional[str] = None,
        severity: int = 1,
        rng: Optional[Any] = None,
    ) -> "WorldEventRecord":
        """Create a WorldEventRecord from an EventResult."""
        primary = result.affected_characters[0] if result.affected_characters else None
        secondary = result.affected_characters[1:] if len(result.affected_characters) > 1 else []
        return cls(
            record_id=_generate_record_id(rng),
            kind=result.event_type,
            year=result.year,
            location_id=location_id,
            primary_actor_id=primary,
            secondary_actor_ids=secondary,
            description=result.description,
            severity=severity,
        )


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

    def event_marriage(self, char1: Character, char2: Character, world: World, rng: Any = random) -> EventResult:
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
        )

    def event_battle(self, char1: Character, char2: Character, world: World, rng: Any = random) -> EventResult:
        """Two characters fight. Winner is determined by combat power + luck."""
        power1 = char1.combat_power + rng.randint(0, 30)
        power2 = char2.combat_power + rng.randint(0, 30)
        winner, loser = (char1, char2) if power1 >= power2 else (char2, char1)

        winner_gains = {"strength": rng.randint(1, 3), "constitution": rng.randint(0, 2)}
        loser_losses = {"constitution": -rng.randint(2, 8), "strength": -rng.randint(0, 3)}
        winner.apply_stat_delta(winner_gains)
        loser.apply_stat_delta(loser_losses)
        winner.update_mutual_relationship(loser, -20, delta_other=-30)

        loser_died = loser.constitution <= 5 and rng.random() < 0.4
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
            )

        desc = tr("battle_normal", winner=winner.name, loser=loser.name)
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
        )

    def event_discovery(self, char: Character, world: World, rng: Any = random) -> EventResult:
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

    def event_meeting(self, char1: Character, char2: Character, world: World, rng: Any = random) -> EventResult:
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
                location=world.location_name(char1.location_id),
                relationship_a=rel1_after,
                relationship_b=rel2_after,
                relationship_avg=avg_after,
            )
        elif avg_after > 0:
            desc = tr(
                "meeting_pleasant",
                name1=char1.name,
                name2=char2.name,
                location=world.location_name(char1.location_id),
                relationship_a=rel1_after,
                relationship_b=rel2_after,
                relationship_avg=avg_after,
            )
        elif avg_after == 0:
            desc = tr(
                "meeting_neutral",
                name1=char1.name,
                name2=char2.name,
                location=world.location_name(char1.location_id),
                relationship_a=rel1_after,
                relationship_b=rel2_after,
                relationship_avg=avg_after,
            )
        else:
            desc = tr(
                "meeting_negative",
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
        )

    def event_aging(self, char: Character, world: World, rng: Any = random) -> EventResult:
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

    def handle_death_side_effects(self, char: Character, world: World) -> None:
        """Apply post-death side effects such as notifying the surviving spouse.

        This is safe to call on any dead character; it is idempotent with
        respect to spouse cleanup because it checks ``char.spouse_id`` and
        ``spouse.spouse_id`` before mutating anything.
        """
        if char.spouse_id:
            spouse = world.get_character_by_id(char.spouse_id)
            if spouse and spouse.alive and spouse.spouse_id == char.char_id:
                spouse.update_relationship(char.char_id, -50)
                spouse.add_history(tr("history_lost_spouse", year=world.year, name=char.name))
                spouse.spouse_id = None

    def event_death(self, char: Character, world: World, rng: Any = random) -> EventResult:
        char.alive = False
        char.active_adventure_id = None
        self.handle_death_side_effects(char, world)

        cause_options = [
            tr("death_cause_old_age"),
            tr("death_cause_monster", location=world.location_name(char.location_id)),
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

    def event_skill_training(self, char: Character, world: World, rng: Any = random) -> EventResult:
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

    def event_journey(self, char: Character, world: World, rng: Any = random) -> EventResult:
        neighbours = world.get_neighboring_locations(char.location_id)
        if not neighbours:
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

        road_event = rng.choice(JOURNEY_EVENTS)
        desc = tr(
            "journey_narrative",
            name=char.name,
            old_location=world.location_name(old_location_id),
            destination=destination.name,
            region_type=destination.region_type,
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

    def check_natural_death(self, char: Character, world: World, rng: Any = random) -> Optional[EventResult]:
        if not char.alive:
            return None
        age_ratio = char.age / max(char.max_age, 1)
        con_factor = (100 - char.constitution) / 100 * 0.5 + 0.5
        death_chance = max(0.0, (age_ratio - 0.6) / 0.4) ** 2 * con_factor
        if rng.random() < death_chance:
            return self.event_death(char, world, rng=rng)
        return None

    def generate_random_event(
        self, characters: List[Character], world: World, rng: Any = random
    ) -> Optional[EventResult]:
        eligible = [c for c in characters if c.alive and c.active_adventure_id is None]
        if not eligible:
            return None

        event_types = list(self._EVENT_WEIGHTS.keys())
        weights = [self._EVENT_WEIGHTS[e] for e in event_types]
        chosen_type = rng.choices(event_types, weights=weights, k=1)[0]

        if chosen_type in ("marriage", "battle", "meeting"):
            pair = self._find_collocated_pair(eligible, rng=rng)
            if pair is None:
                chosen_type = rng.choice(["skill_training", "discovery", "journey", "aging"])
            else:
                char1, char2 = pair
                if chosen_type == "marriage":
                    return self.event_marriage(char1, char2, world, rng=rng)
                if chosen_type == "battle":
                    return self.event_battle(char1, char2, world, rng=rng)
                return self.event_meeting(char1, char2, world, rng=rng)

        char = rng.choice(eligible)
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
    def _find_collocated_pair(alive: List[Character], rng: Any = random) -> Optional[Tuple[Character, Character]]:
        by_loc: Dict[str, List[Character]] = {}
        for c in alive:
            group = by_loc.setdefault(c.location_id, [])
            group.append(c)
        valid = [chars for chars in by_loc.values() if len(chars) >= 2]
        if not valid:
            return None
        group = rng.choice(valid)
        c1, c2 = rng.sample(group, 2)
        return c1, c2

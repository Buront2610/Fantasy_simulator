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


# ---------------------------------------------------------------------------
# EventResult
# ---------------------------------------------------------------------------

@dataclass
class EventResult:
    """The outcome of a single in-world event.

    Attributes
    ----------
    description : str
        Narrative text describing what happened.
    affected_characters : list[str]
        IDs of every character touched by this event.
    stat_changes : dict[str, dict[str, int]]
        ``{char_id: {stat_name: delta}}`` — stats changed during the event.
    event_type : str
        Machine-readable event category (e.g. "battle", "marriage").
    year : int
        World year in which the event occurred.
    """

    description: str
    affected_characters: List[str] = field(default_factory=list)
    stat_changes: Dict[str, Dict[str, int]] = field(default_factory=dict)
    event_type: str = "generic"
    year: int = 0


# ---------------------------------------------------------------------------
# EventSystem
# ---------------------------------------------------------------------------

class EventSystem:
    """Generates and resolves world events.

    All handler methods accept Character / World objects (typed as Any to
    avoid circular imports) and return an EventResult.
    """

    # Weight table: event_type → relative frequency
    _EVENT_WEIGHTS: Dict[str, int] = {
        "meeting":        30,
        "journey":        25,
        "skill_training": 20,
        "discovery":      10,
        "battle":         15,
        "aging":          10,
        "marriage":        5,
        "death":           5,
    }

    # ------------------------------------------------------------------
    # Individual event handlers
    # ------------------------------------------------------------------

    def event_marriage(self, char1: Any, char2: Any, world: Any) -> EventResult:
        """Two characters with high mutual affection get married."""
        rel1 = char1.get_relationship(char2.char_id)
        rel2 = char2.get_relationship(char1.char_id)
        avg_rel = (rel1 + rel2) / 2

        if avg_rel < 50:
            # Not enough affection — improve relationship instead
            char1.update_relationship(char2.char_id, 10)
            char2.update_relationship(char1.char_id, 10)
            desc = (
                f"{char1.name} and {char2.name} spent time together at "
                f"{char1.location}, growing closer (relationship improved)."
            )
            return EventResult(
                description=desc,
                affected_characters=[char1.char_id, char2.char_id],
                stat_changes={},
                event_type="romance",
                year=world.year,
            )

        # Already married?
        if char1.spouse_id == char2.char_id:
            desc = f"{char1.name} and {char2.name} celebrated another year of their marriage."
            char1.add_history(f"Year {world.year}: Celebrated marriage anniversary with {char2.name}.")
            char2.add_history(f"Year {world.year}: Celebrated marriage anniversary with {char1.name}.")
            return EventResult(
                description=desc,
                affected_characters=[char1.char_id, char2.char_id],
                event_type="anniversary",
                year=world.year,
            )

        # Marry them
        char1.spouse_id = char2.char_id
        char2.spouse_id = char1.char_id
        char1.update_relationship(char2.char_id, 20)
        char2.update_relationship(char1.char_id, 20)
        # Small happiness / wisdom boost
        stat_changes = {
            char1.char_id: {"wisdom": 2, "charisma": 1},
            char2.char_id: {"wisdom": 2, "charisma": 1},
        }
        char1.apply_stat_delta(stat_changes[char1.char_id])
        char2.apply_stat_delta(stat_changes[char2.char_id])

        desc = (
            f"💍 {char1.name} ({char1.race} {char1.job}) and "
            f"{char2.name} ({char2.race} {char2.job}) were married in "
            f"{char1.location} amid great celebration!"
        )
        char1.add_history(f"Year {world.year}: Married {char2.name} in {char1.location}.")
        char2.add_history(f"Year {world.year}: Married {char1.name} in {char2.location}.")
        return EventResult(
            description=desc,
            affected_characters=[char1.char_id, char2.char_id],
            stat_changes=stat_changes,
            event_type="marriage",
            year=world.year,
        )

    def event_battle(self, char1: Any, char2: Any, world: Any) -> EventResult:
        """Two characters fight. Winner is determined by combat power + luck."""
        power1 = char1.combat_power + random.randint(0, 30)
        power2 = char2.combat_power + random.randint(0, 30)

        if power1 >= power2:
            winner, loser = char1, char2
        else:
            winner, loser = char2, char1

        win_desc  = random.choice(BATTLE_OUTCOMES_WIN)
        lose_desc = random.choice(BATTLE_OUTCOMES_LOSE)

        # Stat consequences
        winner_gains = {"strength": random.randint(1, 3), "constitution": random.randint(0, 2)}
        loser_losses = {"constitution": -random.randint(2, 8), "strength": -random.randint(0, 3)}

        winner.apply_stat_delta(winner_gains)
        loser.apply_stat_delta(loser_losses)

        # Relationship damage
        winner.update_relationship(loser.char_id, -20)
        loser.update_relationship(winner.char_id, -30)

        # Small chance loser dies if already weak
        loser_died = loser.constitution <= 5 and random.random() < 0.4

        if loser_died:
            result = self.event_death(loser, world)
            desc = (
                f"⚔️  {winner.name} {win_desc} against {loser.name}, "
                f"who {lose_desc} — and did not survive the encounter. "
                f"{loser.name} has perished."
            )
            winner.add_history(f"Year {world.year}: Defeated {loser.name} in battle at {winner.location} (fatal).")
            return EventResult(
                description=desc,
                affected_characters=[winner.char_id, loser.char_id],
                stat_changes={winner.char_id: winner_gains, loser.char_id: loser_losses},
                event_type="battle_fatal",
                year=world.year,
            )

        desc = (
            f"⚔️  {winner.name} {win_desc} against {loser.name}, "
            f"who {lose_desc}."
        )
        winner.add_history(f"Year {world.year}: Won a battle against {loser.name} at {winner.location}.")
        loser.add_history(f"Year {world.year}: Lost a battle against {winner.name} at {loser.location}.")
        return EventResult(
            description=desc,
            affected_characters=[winner.char_id, loser.char_id],
            stat_changes={winner.char_id: winner_gains, loser.char_id: loser_losses},
            event_type="battle",
            year=world.year,
        )

    def event_discovery(self, char: Any, world: Any) -> EventResult:
        """Character discovers something valuable or interesting."""
        item = random.choice(DISCOVERY_ITEMS)
        stat_gains: Dict[str, int] = {}

        # What type of discovery?
        roll = random.random()
        if roll < 0.4:
            # Intelligence / wisdom reward
            stat_gains = {"intelligence": random.randint(1, 4), "wisdom": random.randint(0, 3)}
            extra = "The knowledge contained within changed their outlook forever."
        elif roll < 0.7:
            # Combat reward
            stat_gains = {"strength": random.randint(1, 3), "dexterity": random.randint(0, 2)}
            extra = "The discovery will prove useful in future battles."
        else:
            # Charisma / fortune reward
            stat_gains = {"charisma": random.randint(1, 4)}
            extra = "Word of the discovery spread quickly, raising their reputation."

        char.apply_stat_delta(stat_gains)

        # Also train a random skill
        skill_candidates = list(char.skills.keys()) or ["Dungeoneering"]
        trained_skill = random.choice(skill_candidates)
        char.level_up_skill(trained_skill)

        desc = (
            f"🔍 {char.name} discovered {item} near {char.location}. "
            f"{extra}"
        )
        char.add_history(f"Year {world.year}: Discovered {item} near {char.location}.")
        return EventResult(
            description=desc,
            affected_characters=[char.char_id],
            stat_changes={char.char_id: stat_gains},
            event_type="discovery",
            year=world.year,
        )

    def event_meeting(self, char1: Any, char2: Any, world: Any) -> EventResult:
        """Two characters meet; relationship may improve or worsen."""
        # Base outcome weighted toward positive
        delta = random.randint(-15, 25)
        char1.update_relationship(char2.char_id, delta)
        char2.update_relationship(char1.char_id, delta + random.randint(-5, 5))

        rel_after = char1.get_relationship(char2.char_id)
        if delta > 10:
            tone = "hit it off splendidly"
            emoji = "🤝"
        elif delta > 0:
            tone = "had a pleasant exchange"
            emoji = "🙂"
        elif delta == 0:
            tone = "exchanged a polite nod"
            emoji = "😐"
        else:
            tone = "had a tense, uncomfortable encounter"
            emoji = "😠"

        desc = (
            f"{emoji} {char1.name} and {char2.name} met in {char1.location} "
            f"and {tone}. (Relationship: {rel_after:+d})"
        )
        char1.add_history(f"Year {world.year}: Met {char2.name} in {char1.location}.")
        char2.add_history(f"Year {world.year}: Met {char1.name} in {char2.location}.")
        return EventResult(
            description=desc,
            affected_characters=[char1.char_id, char2.char_id],
            event_type="meeting",
            year=world.year,
        )

    def event_aging(self, char: Any, world: Any) -> EventResult:
        """Character ages; stats shift with time."""
        char.age += 1
        stat_changes: Dict[str, int] = {}

        if char.age < 30:
            # Growing — mostly gains
            stat_changes = {
                "strength":     random.randint(0, 2),
                "intelligence": random.randint(0, 2),
                "dexterity":    random.randint(0, 1),
                "wisdom":       random.randint(0, 1),
            }
            desc = f"⏳ {char.name} turned {char.age}. Youth still drives them forward."
        elif char.age < 50:
            # Prime — balanced
            stat_changes = {
                "intelligence": random.randint(0, 2),
                "wisdom":       random.randint(0, 2),
                "strength":     random.randint(-1, 1),
            }
            desc = f"⏳ {char.name} turned {char.age}, entering the prime of life."
        elif char.age < char.max_age * 0.75:
            # Middle age — wisdom up, agility down
            stat_changes = {
                "wisdom":       random.randint(1, 3),
                "charisma":     random.randint(0, 1),
                "dexterity":    -random.randint(0, 2),
                "strength":     -random.randint(0, 1),
            }
            desc = f"⏳ {char.name} turned {char.age}. Silver threads appear in their hair."
        else:
            # Old age — decline
            stat_changes = {
                "wisdom":       random.randint(0, 2),
                "strength":     -random.randint(1, 3),
                "dexterity":    -random.randint(1, 3),
                "constitution": -random.randint(1, 4),
            }
            desc = f"⏳ {char.name} turned {char.age}. The weight of years shows clearly now."

        char.apply_stat_delta(stat_changes)
        char.add_history(f"Year {world.year}: Turned {char.age}.")
        return EventResult(
            description=desc,
            affected_characters=[char.char_id],
            stat_changes={char.char_id: stat_changes},
            event_type="aging",
            year=world.year,
        )

    def event_death(self, char: Any, world: Any) -> EventResult:
        """Character dies — marked as deceased in the world."""
        char.alive = False
        if char.spouse_id:
            spouse = world.get_character_by_id(char.spouse_id)
            if spouse and spouse.alive:
                spouse.update_relationship(char.char_id, -50)
                spouse.add_history(f"Year {world.year}: Lost beloved spouse {char.name}.")
                spouse.spouse_id = None

        cause_options = [
            "of old age, surrounded by those who loved them",
            "in a monster attack near " + char.location,
            "from a mysterious illness",
            "protecting others from a great danger",
            "while exploring the depths of a dungeon",
            "in a tragic accident on the road",
        ]
        # Weight toward natural causes if old
        if char.age >= char.max_age * 0.9:
            cause = cause_options[0]
        else:
            cause = random.choice(cause_options[1:])

        desc = f"💀 {char.name} ({char.race} {char.job}, age {char.age}) died {cause}."
        char.add_history(f"Year {world.year}: Passed away {cause}.")
        return EventResult(
            description=desc,
            affected_characters=[char.char_id],
            event_type="death",
            year=world.year,
        )

    def event_skill_training(self, char: Any, world: Any) -> EventResult:
        """Character dedicates time to improving a skill."""
        if not char.skills:
            # Give them a starter skill
            from world_data import ALL_SKILLS
            starter = random.choice(ALL_SKILLS)
            char.skills[starter] = 0

        skill = random.choice(list(char.skills.keys()))
        old_level = char.skills[skill]
        msg = char.level_up_skill(skill)
        new_level = char.skills[skill]

        # Small stat bonus for certain skill categories
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

        effort = random.choice([
            "spent long hours in the training yard",
            "meditated through the night",
            "sought out an old master for guidance",
            "practised tirelessly until their hands bled",
            "studied ancient scrolls",
            "pushed themselves beyond their limits",
        ])
        desc = (
            f"📚 {char.name} {effort} and improved {skill} "
            f"(Lv {old_level} → Lv {new_level})."
        )
        char.add_history(f"Year {world.year}: Trained {skill} to level {new_level}.")
        return EventResult(
            description=desc,
            affected_characters=[char.char_id],
            stat_changes={char.char_id: stat_bonus} if stat_bonus else {},
            event_type="skill_training",
            year=world.year,
        )

    def event_journey(self, char: Any, world: Any) -> EventResult:
        """Character travels to a neighbouring (or random) location."""
        neighbours = world.get_neighboring_locations(char.location)
        if not neighbours:
            # Teleport to random location
            neighbours = list(world.grid.values())

        destination = random.choice(neighbours)
        old_location = char.location
        char.location = destination.name

        # Random road event
        road_event = random.choice(JOURNEY_EVENTS)
        desc = (
            f"🚶 {char.name} journeyed from {old_location} to "
            f"{destination.name} ({destination.region_type}) "
            f"and {road_event}."
        )
        char.add_history(f"Year {world.year}: Travelled from {old_location} to {destination.name}.")

        # Dungeon bonus
        extra_changes: Dict[str, int] = {}
        if destination.region_type == "dungeon":
            bonus = random.choice(["strength", "dexterity", "intelligence"])
            extra_changes[bonus] = random.randint(1, 4)
            char.apply_stat_delta(extra_changes)
            desc += f" The dungeon hardened them (+{extra_changes[bonus]} {bonus})."

        return EventResult(
            description=desc,
            affected_characters=[char.char_id],
            stat_changes={char.char_id: extra_changes} if extra_changes else {},
            event_type="journey",
            year=world.year,
        )

    # ------------------------------------------------------------------
    # Natural death check (called each year per character)
    # ------------------------------------------------------------------

    def check_natural_death(self, char: Any, world: Any) -> Optional[EventResult]:
        """Return a death EventResult if the character should die this year.

        Probability increases sharply as age approaches max_age.
        """
        if not char.alive:
            return None
        age_ratio = char.age / max(char.max_age, 1)
        # Constitution lowers mortality
        con_factor = (100 - char.constitution) / 100 * 0.5 + 0.5
        death_chance = max(0.0, (age_ratio - 0.6) / 0.4) ** 2 * con_factor

        if random.random() < death_chance:
            return self.event_death(char, world)
        return None

    # ------------------------------------------------------------------
    # Random event dispatcher
    # ------------------------------------------------------------------

    def generate_random_event(
        self,
        characters: List[Any],
        world: Any,
    ) -> Optional[EventResult]:
        """Pick and execute a random event from the living character pool.

        Returns None if there are no valid characters.
        """
        alive = [c for c in characters if c.alive]
        if not alive:
            return None

        # Weighted random event type selection
        event_types = list(self._EVENT_WEIGHTS.keys())
        weights = [self._EVENT_WEIGHTS[e] for e in event_types]
        chosen_type = random.choices(event_types, weights=weights, k=1)[0]

        # Two-character events need a pair at the same location
        if chosen_type in ("marriage", "battle", "meeting"):
            pair = self._find_collocated_pair(alive)
            if pair is None:
                # Fall back to solo event
                chosen_type = random.choice(["skill_training", "discovery", "journey", "aging"])
            else:
                char1, char2 = pair
                if chosen_type == "marriage":
                    return self.event_marriage(char1, char2, world)
                elif chosen_type == "battle":
                    return self.event_battle(char1, char2, world)
                else:
                    return self.event_meeting(char1, char2, world)

        char = random.choice(alive)
        if chosen_type == "discovery":
            return self.event_discovery(char, world)
        elif chosen_type == "skill_training":
            return self.event_skill_training(char, world)
        elif chosen_type == "journey":
            return self.event_journey(char, world)
        elif chosen_type == "aging":
            return self.event_aging(char, world)
        elif chosen_type == "death":
            return self.event_death(char, world)
        else:
            return self.event_skill_training(char, world)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _find_collocated_pair(
        alive: List[Any],
    ) -> Optional[Tuple[Any, Any]]:
        """Return a random pair of characters sharing the same location, or None."""
        # Group by location
        by_loc: Dict[str, List[Any]] = {}
        for c in alive:
            by_loc.setdefault(c.location, []).append(c)
        valid = [chars for chars in by_loc.values() if len(chars) >= 2]
        if not valid:
            return None
        group = random.choice(valid)
        pair = random.sample(group, 2)
        return pair[0], pair[1]

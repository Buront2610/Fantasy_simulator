"""Policy scoring, retreat rules, and party adventure risk math."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any, Dict, List

from .adventure_constants import (
    BASE_INJURY_CHANCE,
    CHOICE_PRESS_ON,
    CHOICE_PROCEED_CAUTIOUSLY,
    CHOICE_WITHDRAW,
    POLICY_ASSAULT,
    POLICY_CAUTIOUS,
    POLICY_INJURY_MOD,
    POLICY_LOOT_MOD,
    POLICY_RELIC,
    POLICY_RESCUE,
    POLICY_SUPPLY_MOD,
    POLICY_SWIFT,
    POLICY_TREASURE,
    RETREAT_NEVER,
    RETREAT_ON_SERIOUS,
    RETREAT_ON_SUPPLY,
    RETREAT_ON_TROPHY,
    STAT_BASELINE,
    SUPPLY_CRITICAL,
    SUPPLY_DEGRADE_FULL_TO_LOW,
    SUPPLY_DEGRADE_LOW_TO_CRITICAL,
    SUPPLY_FULL,
    SUPPLY_LOW,
)
from .adventure_protocols import AdventureRunLike

if TYPE_CHECKING:
    from .character import Character
    from .world import World


def select_party_policy(members: List["Character"], rng: Any = random) -> str:
    if not members:
        return POLICY_CAUTIOUS

    avg_wis = sum(c.wisdom for c in members) / len(members)
    avg_str = sum(c.strength for c in members) / len(members)
    avg_int = sum(c.intelligence for c in members) / len(members)
    avg_con = sum(c.constitution for c in members) / len(members)
    scores: Dict[str, float] = {
        POLICY_CAUTIOUS: avg_wis,
        POLICY_SWIFT: avg_str * 0.5 + avg_con * 0.5,
        POLICY_TREASURE: avg_int * 0.5 + avg_con * 0.5,
        POLICY_RESCUE: avg_wis * 0.7 + avg_str * 0.3,
        POLICY_RELIC: avg_int,
        POLICY_ASSAULT: avg_str,
    }

    sorted_policies = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    top3 = sorted_policies[:3]
    tier_weights = [1.0, 0.5, 0.2]
    total_weight = sum(tier_weights)
    roll = rng.random() * total_weight
    cumulative = 0.0
    for (policy, _score), weight in zip(top3, tier_weights):
        cumulative += weight
        if roll <= cumulative:
            return policy
    return top3[0][0]


def default_retreat_rule_for_policy(policy: str) -> str:
    mapping = {
        POLICY_CAUTIOUS: RETREAT_ON_SERIOUS,
        POLICY_RESCUE: RETREAT_ON_SERIOUS,
        POLICY_TREASURE: RETREAT_ON_TROPHY,
        POLICY_RELIC: RETREAT_ON_TROPHY,
        POLICY_SWIFT: RETREAT_ON_SUPPLY,
        POLICY_ASSAULT: RETREAT_NEVER,
    }
    return mapping.get(policy, RETREAT_ON_SERIOUS)


class AdventurePolicyEngine:
    def __init__(self, run: AdventureRunLike) -> None:
        self.run = run

    def party_members(self, world: "World") -> List["Character"]:
        members: List["Character"] = []
        for member_id in self.run.member_ids:
            character = world.get_character_by_id(member_id)
            if character is not None and character.alive:
                members.append(character)
        return members

    @staticmethod
    def combat_score(members: List["Character"]) -> float:
        if not members:
            return STAT_BASELINE
        return sum(c.strength + c.constitution for c in members) / (2 * len(members))

    @staticmethod
    def evasion_score(members: List["Character"]) -> float:
        if not members:
            return STAT_BASELINE
        return sum(c.dexterity + c.wisdom for c in members) / (2 * len(members))

    @staticmethod
    def lore_score(members: List["Character"]) -> float:
        if not members:
            return STAT_BASELINE
        return sum(c.intelligence for c in members) / len(members)

    def compute_injury_chance(self, members: List["Character"]) -> float:
        combat = self.combat_score(members)
        ability_mod = STAT_BASELINE / max(combat, 1.0)
        danger_mod = 0.5 + self.run.danger_level / 100.0
        policy_mod = POLICY_INJURY_MOD.get(self.run.policy, 1.0)
        chance = BASE_INJURY_CHANCE * ability_mod * danger_mod * policy_mod
        return max(0.04, min(0.22, chance))

    def compute_loot_chance(self, members: List["Character"]) -> float:
        lore = self.lore_score(members)
        ability_mod = lore / STAT_BASELINE
        policy_mod = POLICY_LOOT_MOD.get(self.run.policy, 1.0)
        chance = 0.76 * ability_mod * policy_mod
        return max(0.20, min(0.95, chance))

    def should_auto_retreat(self, members: List["Character"]) -> bool:
        if self.run.retreat_rule == RETREAT_ON_SERIOUS:
            return any(member.injury_status in ("serious", "dying") for member in members)
        if self.run.retreat_rule == RETREAT_ON_SUPPLY:
            return self.run.supply_state == SUPPLY_CRITICAL
        if self.run.retreat_rule == RETREAT_ON_TROPHY:
            return bool(self.run.loot_summary)
        return False

    def tick_supply(self, rng: Any) -> None:
        policy_mod = POLICY_SUPPLY_MOD.get(self.run.policy, 1.0)
        if self.run.supply_state == SUPPLY_FULL:
            if rng.random() < SUPPLY_DEGRADE_FULL_TO_LOW * policy_mod:
                self.run.supply_state = SUPPLY_LOW
        elif self.run.supply_state == SUPPLY_LOW:
            if rng.random() < SUPPLY_DEGRADE_LOW_TO_CRITICAL * policy_mod:
                self.run.supply_state = SUPPLY_CRITICAL

    def default_option_for_context(self, context: str) -> str:
        if context == "approach":
            defaults = {
                POLICY_CAUTIOUS: CHOICE_PROCEED_CAUTIOUSLY,
                POLICY_RESCUE: CHOICE_PROCEED_CAUTIOUSLY,
                POLICY_TREASURE: CHOICE_PRESS_ON,
                POLICY_RELIC: CHOICE_PRESS_ON,
                POLICY_SWIFT: CHOICE_PRESS_ON,
                POLICY_ASSAULT: CHOICE_PRESS_ON,
            }
            return defaults.get(self.run.policy, CHOICE_PROCEED_CAUTIOUSLY)
        if context == "depth":
            defaults = {
                POLICY_CAUTIOUS: CHOICE_WITHDRAW,
                POLICY_RESCUE: CHOICE_WITHDRAW,
                POLICY_SWIFT: CHOICE_PRESS_ON,
                POLICY_TREASURE: CHOICE_PRESS_ON,
                POLICY_RELIC: CHOICE_PRESS_ON,
                POLICY_ASSAULT: CHOICE_PRESS_ON,
            }
            return defaults.get(self.run.policy, CHOICE_WITHDRAW)
        return CHOICE_WITHDRAW

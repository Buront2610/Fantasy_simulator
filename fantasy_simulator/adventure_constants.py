"""Shared constants and identifiers for adventure runs."""

from __future__ import annotations

import random
import uuid
from typing import Any, Dict


ADVENTURE_DISCOVERIES = [
    "an ancient relic",
    "a pouch of moon-silver",
    "a fragment of lost lore",
    "a cache of monster trophies",
]


def generate_adventure_id(rng: Any = random) -> str:
    if hasattr(rng, "getrandbits"):
        return format(rng.getrandbits(40), "010x")
    return uuid.uuid4().hex[:10]


CHOICE_PRESS_ON = "press_on"
CHOICE_PROCEED_CAUTIOUSLY = "proceed_cautiously"
CHOICE_RETREAT = "retreat"
CHOICE_WITHDRAW = "withdraw"

POLICY_CAUTIOUS = "cautious"
POLICY_SWIFT = "swift"
POLICY_TREASURE = "treasure"
POLICY_RESCUE = "rescue"
POLICY_RELIC = "relic"
POLICY_ASSAULT = "assault"

ALL_POLICIES: tuple[str, ...] = (
    POLICY_CAUTIOUS,
    POLICY_SWIFT,
    POLICY_TREASURE,
    POLICY_RESCUE,
    POLICY_RELIC,
    POLICY_ASSAULT,
)

RETREAT_ON_SERIOUS = "on_serious"
RETREAT_ON_SUPPLY = "on_supply"
RETREAT_ON_TROPHY = "on_trophy"
RETREAT_NEVER = "never"

ALL_RETREAT_RULES: tuple[str, ...] = (
    RETREAT_ON_SERIOUS,
    RETREAT_ON_SUPPLY,
    RETREAT_ON_TROPHY,
    RETREAT_NEVER,
)

SUPPLY_FULL = "full"
SUPPLY_LOW = "low"
SUPPLY_CRITICAL = "critical"

STAT_BASELINE = 50.0

POLICY_INJURY_MOD: Dict[str, float] = {
    POLICY_CAUTIOUS: 0.70,
    POLICY_SWIFT: 1.20,
    POLICY_TREASURE: 1.10,
    POLICY_RESCUE: 0.90,
    POLICY_RELIC: 1.00,
    POLICY_ASSAULT: 1.30,
}

POLICY_LOOT_MOD: Dict[str, float] = {
    POLICY_CAUTIOUS: 0.80,
    POLICY_SWIFT: 0.90,
    POLICY_TREASURE: 1.40,
    POLICY_RESCUE: 0.70,
    POLICY_RELIC: 1.30,
    POLICY_ASSAULT: 1.10,
}

POLICY_SUPPLY_MOD: Dict[str, float] = {
    POLICY_CAUTIOUS: 0.85,
    POLICY_SWIFT: 0.70,
    POLICY_TREASURE: 1.05,
    POLICY_RESCUE: 0.90,
    POLICY_RELIC: 1.00,
    POLICY_ASSAULT: 1.25,
}

BASE_INJURY_CHANCE = 0.18
BASE_CRITICAL_RATIO = 0.24 / 0.18
SUPPLY_DEGRADE_FULL_TO_LOW = 0.15
SUPPLY_DEGRADE_LOW_TO_CRITICAL = 0.20

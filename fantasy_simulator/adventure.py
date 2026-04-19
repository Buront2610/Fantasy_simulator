"""
adventure.py - Adventure progression for the Fantasy Simulator.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .adventure_domain import (
    ADVENTURE_DISCOVERIES,
    ALL_POLICIES,
    ALL_RETREAT_RULES,
    CHOICE_PRESS_ON,
    CHOICE_PROCEED_CAUTIOUSLY,
    CHOICE_RETREAT,
    CHOICE_WITHDRAW,
    POLICY_ASSAULT,
    POLICY_CAUTIOUS,
    POLICY_RELIC,
    POLICY_RESCUE,
    POLICY_SWIFT,
    POLICY_TREASURE,
    RETREAT_NEVER,
    RETREAT_ON_SERIOUS,
    RETREAT_ON_SUPPLY,
    RETREAT_ON_TROPHY,
    SUPPLY_CRITICAL,
    SUPPLY_FULL,
    SUPPLY_LOW,
    AdventureChoiceResolver,
    AdventurePolicyEngine,
    AdventureSerialization,
    AdventureStateMachine,
    default_retreat_rule_for_policy,
    generate_adventure_id,
    select_party_policy,
)
from .i18n import tr

if TYPE_CHECKING:
    from .character import Character
    from .world import World


__all__ = [
    "ADVENTURE_DISCOVERIES",
    "AdventureChoice",
    "AdventureRun",
    "ALL_POLICIES",
    "ALL_RETREAT_RULES",
    "CHOICE_PRESS_ON",
    "CHOICE_PROCEED_CAUTIOUSLY",
    "CHOICE_RETREAT",
    "CHOICE_WITHDRAW",
    "POLICY_ASSAULT",
    "POLICY_CAUTIOUS",
    "POLICY_RELIC",
    "POLICY_RESCUE",
    "POLICY_SWIFT",
    "POLICY_TREASURE",
    "RETREAT_NEVER",
    "RETREAT_ON_SERIOUS",
    "RETREAT_ON_SUPPLY",
    "RETREAT_ON_TROPHY",
    "SUPPLY_CRITICAL",
    "SUPPLY_FULL",
    "SUPPLY_LOW",
    "create_adventure_run",
    "default_retreat_rule_for_policy",
    "generate_adventure_id",
    "select_party_policy",
]


@dataclass
class AdventureChoice:
    """A single pending player-facing choice for an adventure."""

    prompt: str
    options: List[str]
    default_option: str
    context: str
    selected_option: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "options": list(self.options),
            "default_option": self.default_option,
            "context": self.context,
            "selected_option": self.selected_option,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdventureChoice":
        return cls(
            prompt=data["prompt"],
            options=list(data["options"]),
            default_option=data["default_option"],
            context=data["context"],
            selected_option=data.get("selected_option"),
        )


@dataclass
class AdventureRun:
    """Represents one ongoing adventure inside the main world simulation."""

    character_id: str
    character_name: str
    origin: str
    destination: str
    year_started: int
    adventure_id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    state: str = "traveling"
    injury_status: str = "none"
    steps_taken: int = 0
    pending_choice: Optional[AdventureChoice] = None
    outcome: Optional[str] = None
    loot_summary: List[str] = field(default_factory=list)
    summary_log: List[str] = field(default_factory=list)
    detail_log: List[str] = field(default_factory=list)
    resolution_year: Optional[int] = None
    injury_member_id: Optional[str] = None
    death_member_id: Optional[str] = None
    member_ids: List[str] = field(default_factory=list)
    party_id: Optional[str] = None
    policy: str = POLICY_CAUTIOUS
    retreat_rule: str = RETREAT_ON_SERIOUS
    supply_state: str = SUPPLY_FULL
    danger_level: int = 50

    @property
    def is_resolved(self) -> bool:
        return self.state == "resolved"

    @property
    def is_party(self) -> bool:
        return len(self.member_ids) > 1

    def _policy_engine(self) -> AdventurePolicyEngine:
        return AdventurePolicyEngine(self)

    def _party_members(self, world: "World") -> List["Character"]:
        return self._policy_engine().party_members(world)

    @staticmethod
    def _combat_score(members: List["Character"]) -> float:
        return AdventurePolicyEngine.combat_score(members)

    @staticmethod
    def _evasion_score(members: List["Character"]) -> float:
        return AdventurePolicyEngine.evasion_score(members)

    @staticmethod
    def _lore_score(members: List["Character"]) -> float:
        return AdventurePolicyEngine.lore_score(members)

    def _compute_injury_chance(self, members: List["Character"]) -> float:
        return self._policy_engine().compute_injury_chance(members)

    def _compute_loot_chance(self, members: List["Character"]) -> float:
        return self._policy_engine().compute_loot_chance(members)

    def _should_auto_retreat(self, members: List["Character"]) -> bool:
        return self._policy_engine().should_auto_retreat(members)

    def _tick_supply(self, rng: Any) -> None:
        self._policy_engine().tick_supply(rng)

    def _default_option_for_context(self, context: str) -> str:
        return self._policy_engine().default_option_for_context(context)

    def _clear_member_adventures(self, world: "World") -> None:
        for member_id in self.member_ids:
            if member_id != self.character_id:
                member = world.get_character_by_id(member_id)
                if member is not None:
                    member.active_adventure_id = None

    def to_dict(self) -> Dict[str, Any]:
        return AdventureSerialization.to_dict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdventureRun":
        return AdventureSerialization.from_dict(cls, AdventureChoice, data)

    def step(self, character: "Character", world: "World", rng: Any = random) -> List[str]:
        return AdventureStateMachine(self, AdventureChoice).step(character, world, rng=rng)

    def resolve_choice(
        self,
        world: "World",
        character: "Character",
        option: Optional[str] = None,
    ) -> List[str]:
        return AdventureChoiceResolver(self).resolve(world, character, option=option)

    def _record(self, summary: str, detail: str) -> None:
        self.summary_log.append(summary)
        self.detail_log.append(detail)


def create_adventure_run(
    character: "Character",
    world: "World",
    rng: Any = random,
    id_rng: Any = random,
) -> AdventureRun:
    """Create a new base adventure run for the leader character."""
    neighbors = world.get_neighboring_locations(character.location_id)
    risky = [loc for loc in neighbors if loc.region_type in ("forest", "mountain", "dungeon")]
    reachable = list(neighbors)
    if not risky:
        reachable_candidates = [
            world.get_location_by_id(location_id)
            for location_id in world.reachable_location_ids(character.location_id)
        ]
        reachable = [loc for loc in reachable_candidates if loc is not None]
        risky = [
            loc for loc in reachable
            if loc.region_type in ("forest", "mountain", "dungeon")
        ]
    candidates = risky or reachable
    if not candidates and not world.grid:
        raise ValueError("Cannot create adventure: world has no locations")
    if not candidates:
        if world.routes:
            raise ValueError("Cannot create adventure: no reachable destinations")
        destination = world.random_location(rng=rng)
    else:
        destination = rng.choice(candidates)

    origin_name = world.location_name(character.location_id)
    destination_name = world.location_name(destination.id)
    danger_level = getattr(destination, "danger", 50)

    run = AdventureRun(
        character_id=character.char_id,
        character_name=character.name,
        origin=character.location_id,
        destination=destination.id,
        year_started=world.year,
        adventure_id=generate_adventure_id(id_rng),
        member_ids=[character.char_id],
        danger_level=danger_level,
    )
    run._record(
        tr("summary_adventure_set_out", name=character.name, origin=origin_name, destination=destination_name),
        tr("detail_adventure_set_out", name=character.name, origin=origin_name, destination=destination_name),
    )
    return run

"""Adventure domain helpers split by policy, choices, and serialization."""

from __future__ import annotations

import random
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol, Type, TypeVar, cast

from .i18n import tr, tr_term

if TYPE_CHECKING:
    from .character import Character
    from .world import World


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

_STAT_BASELINE = 50.0

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

_BASE_INJURY_CHANCE = 0.18
_BASE_CRITICAL_RATIO = 0.24 / 0.18
_SUPPLY_DEGRADE_FULL_TO_LOW = 0.15
_SUPPLY_DEGRADE_LOW_TO_CRITICAL = 0.20


class AdventureRunLike(Protocol):
    character_id: str
    character_name: str
    origin: str
    destination: str
    year_started: int
    adventure_id: str
    state: str
    injury_status: str
    steps_taken: int
    pending_choice: Any
    outcome: Optional[str]
    loot_summary: List[str]
    summary_log: List[str]
    detail_log: List[str]
    resolution_year: Optional[int]
    injury_member_id: Optional[str]
    death_member_id: Optional[str]
    member_ids: List[str]
    party_id: Optional[str]
    policy: str
    retreat_rule: str
    supply_state: str
    danger_level: int

    @property
    def is_resolved(self) -> bool:
        ...

    @property
    def is_party(self) -> bool:
        ...

    def _record(self, summary: str, detail: str) -> None:
        ...

    def _clear_member_adventures(self, world: "World") -> None:
        ...


def validate_adventure_run_payload(run: AdventureRunLike) -> None:
    if run.policy not in ALL_POLICIES:
        raise ValueError(f"policy must be one of {ALL_POLICIES}")
    if run.retreat_rule not in ALL_RETREAT_RULES:
        raise ValueError(f"retreat_rule must be one of {ALL_RETREAT_RULES}")
    if run.supply_state not in (SUPPLY_FULL, SUPPLY_LOW, SUPPLY_CRITICAL):
        raise ValueError("supply_state must be one of ('full', 'low', 'critical')")
    if not isinstance(run.danger_level, int) or isinstance(run.danger_level, bool):
        raise ValueError("danger_level must be an integer")
    if run.danger_level < 0 or run.danger_level > 100:
        raise ValueError("danger_level must be between 0 and 100")
    if not isinstance(run.member_ids, list) or any(not isinstance(member_id, str) for member_id in run.member_ids):
        raise ValueError("member_ids must be a list of strings")
    if run.member_ids and run.character_id not in run.member_ids:
        raise ValueError("member_ids must include character_id")


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
            return _STAT_BASELINE
        return sum(c.strength + c.constitution for c in members) / (2 * len(members))

    @staticmethod
    def evasion_score(members: List["Character"]) -> float:
        if not members:
            return _STAT_BASELINE
        return sum(c.dexterity + c.wisdom for c in members) / (2 * len(members))

    @staticmethod
    def lore_score(members: List["Character"]) -> float:
        if not members:
            return _STAT_BASELINE
        return sum(c.intelligence for c in members) / len(members)

    def compute_injury_chance(self, members: List["Character"]) -> float:
        combat = self.combat_score(members)
        ability_mod = _STAT_BASELINE / max(combat, 1.0)
        danger_mod = 0.5 + self.run.danger_level / 100.0
        policy_mod = POLICY_INJURY_MOD.get(self.run.policy, 1.0)
        chance = _BASE_INJURY_CHANCE * ability_mod * danger_mod * policy_mod
        return max(0.04, min(0.22, chance))

    def compute_loot_chance(self, members: List["Character"]) -> float:
        lore = self.lore_score(members)
        ability_mod = lore / _STAT_BASELINE
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
            if rng.random() < _SUPPLY_DEGRADE_FULL_TO_LOW * policy_mod:
                self.run.supply_state = SUPPLY_LOW
        elif self.run.supply_state == SUPPLY_LOW:
            if rng.random() < _SUPPLY_DEGRADE_LOW_TO_CRITICAL * policy_mod:
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


TAdventureRun = TypeVar("TAdventureRun")


class AdventureSerialization:
    @staticmethod
    def to_dict(run: AdventureRunLike) -> Dict[str, Any]:
        return {
            "character_id": run.character_id,
            "character_name": run.character_name,
            "origin": run.origin,
            "destination": run.destination,
            "year_started": run.year_started,
            "adventure_id": run.adventure_id,
            "state": run.state,
            "injury_status": run.injury_status,
            "steps_taken": run.steps_taken,
            "pending_choice": run.pending_choice.to_dict() if run.pending_choice is not None else None,
            "outcome": run.outcome,
            "loot_summary": list(run.loot_summary),
            "summary_log": list(run.summary_log),
            "detail_log": list(run.detail_log),
            "resolution_year": run.resolution_year,
            "injury_member_id": run.injury_member_id,
            "death_member_id": run.death_member_id,
            "member_ids": list(run.member_ids),
            "party_id": run.party_id,
            "policy": run.policy,
            "retreat_rule": run.retreat_rule,
            "supply_state": run.supply_state,
            "danger_level": run.danger_level,
        }

    @staticmethod
    def from_dict(run_cls: Type[TAdventureRun], choice_cls: Type[Any], data: Dict[str, Any]) -> TAdventureRun:
        pending = data.get("pending_choice")
        character_id = data["character_id"]
        member_ids = data.get("member_ids") or [character_id]
        if not isinstance(member_ids, list) or any(not isinstance(member_id, str) for member_id in member_ids):
            raise ValueError("member_ids must be a list of strings")
        run_factory = cast(Any, run_cls)
        run = run_factory(
            character_id=character_id,
            character_name=data["character_name"],
            origin=data["origin"],
            destination=data["destination"],
            year_started=data["year_started"],
            adventure_id=data.get("adventure_id", uuid.uuid4().hex[:10]),
            state=data.get("state", "traveling"),
            injury_status=data.get("injury_status", "none"),
            steps_taken=data.get("steps_taken", 0),
            pending_choice=choice_cls.from_dict(pending) if pending else None,
            outcome=data.get("outcome"),
            loot_summary=list(data.get("loot_summary", [])),
            summary_log=list(data.get("summary_log", [])),
            detail_log=list(data.get("detail_log", [])),
            resolution_year=data.get("resolution_year"),
            injury_member_id=data.get("injury_member_id"),
            death_member_id=data.get("death_member_id"),
            member_ids=list(member_ids),
            party_id=data.get("party_id"),
            policy=data.get("policy", POLICY_CAUTIOUS),
            retreat_rule=data.get("retreat_rule", RETREAT_ON_SERIOUS),
            supply_state=data.get("supply_state", SUPPLY_FULL),
            danger_level=data.get("danger_level", 50),
        )
        validate_adventure_run_payload(run)
        return run


class AdventureChoiceResolver:
    def __init__(self, run: AdventureRunLike) -> None:
        self.run = run

    def resolve(
        self,
        world: "World",
        character: "Character",
        option: Optional[str] = None,
    ) -> List[str]:
        if self.run.pending_choice is None:
            return []

        chosen = option or self.run.pending_choice.default_option
        if chosen not in self.run.pending_choice.options:
            chosen = self.run.pending_choice.default_option
        self.run.pending_choice.selected_option = chosen

        detail = tr("detail_choice_made", name=self.run.character_name, choice=tr(f"choice_{chosen}"))
        self.run.detail_log.append(detail)

        context = self.run.pending_choice.context
        self.run.pending_choice = None

        if chosen in (CHOICE_RETREAT, CHOICE_WITHDRAW):
            self.run.state = "returning"
            summary = tr("summary_choice_withdraw", name=self.run.character_name)
            self.run.summary_log.append(summary)
            self.run.detail_log.append(tr("detail_choice_withdraw", name=self.run.character_name))
            return [summary]

        if context == "approach" and chosen == CHOICE_PROCEED_CAUTIOUSLY:
            self.run.state = "exploring"
            destination_name = world.location_name(self.run.destination)
            self.run.detail_log.append(
                tr("detail_choice_cautious", name=self.run.character_name, destination=destination_name)
            )
            return []

        if context in ("approach", "depth") and chosen == CHOICE_PRESS_ON:
            self.run.state = "exploring"
            destination_name = world.location_name(self.run.destination)
            self.run.detail_log.append(
                tr("detail_choice_press_on", name=self.run.character_name, destination=destination_name)
            )
            return []

        self.run.state = "exploring"
        return []


class AdventureStateMachine:
    def __init__(self, run: AdventureRunLike, choice_cls: Type[Any]) -> None:
        self.run = run
        self.choice_cls = choice_cls
        self.policy = AdventurePolicyEngine(run)

    def step(self, character: "Character", world: "World", rng: Any = random) -> List[str]:
        if self.run.is_resolved:
            return []

        if self.run.state == "waiting_for_choice":
            return AdventureChoiceResolver(self.run).resolve(world, character, option=None)

        destination_name = world.location_name(self.run.destination)
        origin_name = world.location_name(self.run.origin)

        if self.run.state == "traveling":
            return self._step_traveling(world, rng, destination_name, origin_name)
        if self.run.state == "exploring":
            return self._step_exploring(character, world, rng, destination_name, origin_name)
        if self.run.state == "returning":
            return self._step_returning(character, world, destination_name, origin_name)
        return []

    def _step_traveling(
        self,
        world: "World",
        rng: Any,
        destination_name: str,
        origin_name: str,
    ) -> List[str]:
        self.run.steps_taken += 1
        summary = tr("summary_adventure_arrived", name=self.run.character_name, destination=destination_name)
        detail = tr(
            "detail_adventure_arrived",
            name=self.run.character_name,
            origin=origin_name,
            destination=destination_name,
        )
        self.run._record(summary, detail)
        if rng.random() < 0.35:
            self.run.pending_choice = self.choice_cls(
                prompt=tr(
                    "choice_dangerous_approach",
                    name=self.run.character_name,
                    destination=destination_name,
                ),
                options=[CHOICE_PRESS_ON, CHOICE_PROCEED_CAUTIOUSLY, CHOICE_RETREAT],
                default_option=self.policy.default_option_for_context("approach"),
                context="approach",
            )
            self.run.state = "waiting_for_choice"
            self.run.detail_log.append(tr("detail_paused_at_entrance", name=self.run.character_name))
        else:
            self.run.state = "exploring"
        return [summary]

    def _step_exploring(
        self,
        character: "Character",
        world: "World",
        rng: Any,
        destination_name: str,
        origin_name: str,
    ) -> List[str]:
        self.run.steps_taken += 1
        members = self.policy.party_members(world) or [character]

        if self.run.is_party and self.policy.should_auto_retreat(members):
            self.run.state = "returning"
            summary = tr("summary_party_retreated_auto", name=self.run.character_name, destination=destination_name)
            detail = tr("detail_party_retreated_auto", name=self.run.character_name, destination=destination_name)
            self.run._record(summary, detail)
            return [summary]

        if self.run.is_party:
            self.policy.tick_supply(rng)

        injury_chance = self.policy.compute_injury_chance(members)
        critical_chance = min(injury_chance * _BASE_CRITICAL_RATIO, 0.60)
        roll = rng.random()
        injured_member = character
        if self.run.is_party and members:
            injured_member = rng.choice(members)

        if roll < injury_chance:
            return self._resolve_hazard_band(injured_member, character, world, destination_name)
        if roll < critical_chance:
            return self._resolve_nonfatal_injury(injured_member, destination_name)

        loot_chance = self.policy.compute_loot_chance(members)
        if rng.random() < loot_chance:
            discovery = rng.choice(ADVENTURE_DISCOVERIES)
            self.run.loot_summary.append(discovery)
            summary = tr("summary_adventure_discovery", name=self.run.character_name, destination=destination_name)
            detail = tr(
                "detail_adventure_discovery",
                name=self.run.character_name,
                discovery=tr_term(discovery),
                destination=destination_name,
            )
            self.run._record(summary, detail)
        else:
            summary = tr("summary_adventure_scouting", name=self.run.character_name, destination=destination_name)
            detail = tr("detail_adventure_scouting", name=self.run.character_name, destination=destination_name)
            self.run._record(summary, detail)

        if self.run.pending_choice is None and rng.random() < 0.40:
            self.run.pending_choice = self.choice_cls(
                prompt=tr("choice_press_deeper", name=self.run.character_name, destination=destination_name),
                options=[CHOICE_PRESS_ON, CHOICE_WITHDRAW],
                default_option=self.policy.default_option_for_context("depth"),
                context="depth",
            )
            self.run.state = "waiting_for_choice"
            self.run.detail_log.append(tr("detail_paused_to_delve", name=self.run.character_name))
        else:
            self.run.state = "returning"
        return [self.run.summary_log[-1]]

    def _resolve_hazard_band(
        self,
        injured_member: "Character",
        leader: "Character",
        world: "World",
        destination_name: str,
    ) -> List[str]:
        if injured_member.injury_status == "dying":
            self.run.outcome = "death"
            self.run.state = "resolved"
            self.run.resolution_year = world.year
            injured_member.alive = False
            injured_member.active_adventure_id = None
            self.run.death_member_id = injured_member.char_id
            leader.active_adventure_id = None
            self.run._clear_member_adventures(world)
            summary = tr("summary_adventure_died", name=injured_member.name, destination=destination_name)
            detail = tr("detail_adventure_died", name=injured_member.name, destination=destination_name)
            self.run._record(summary, detail)
            injured_member.add_history(tr("history_adventure_detail", year=world.year, detail=detail))
            return [summary]
        return self._resolve_nonfatal_injury(injured_member, destination_name)

    def _resolve_nonfatal_injury(
        self,
        injured_member: "Character",
        destination_name: str,
    ) -> List[str]:
        injured_member.worsen_injury()
        self.run.injury_status = injured_member.injury_status
        self.run.injury_member_id = injured_member.char_id
        summary = tr("summary_adventure_injured", name=injured_member.name)
        detail = tr("detail_adventure_injured", name=injured_member.name, destination=destination_name)
        self.run._record(summary, detail)
        self.run.state = "returning"
        return [summary]

    def _step_returning(
        self,
        character: "Character",
        world: "World",
        destination_name: str,
        origin_name: str,
    ) -> List[str]:
        self.run.steps_taken += 1
        self.run.state = "resolved"
        self.run.resolution_year = world.year
        history_target = character
        if self.run.outcome != "death":
            if self.run.injury_status != "none":
                self.run.outcome = "injury"
                injured_member = world.get_character_by_id(self.run.injury_member_id or self.run.character_id)
                if injured_member is None:
                    injured_member = character
                injured_member.injury_status = self.run.injury_status
                summary = tr("summary_returned_injured", name=injured_member.name, destination=destination_name)
                detail = tr("detail_returned_injured", name=injured_member.name, origin=origin_name)
                history_target = injured_member
            elif self.run.loot_summary:
                self.run.outcome = "safe_return"
                summary = tr(
                    "summary_returned_safely",
                    name=self.run.character_name,
                    destination=destination_name,
                    loot=tr_term(self.run.loot_summary[-1]),
                )
                detail = tr(
                    "detail_returned_safely",
                    name=self.run.character_name,
                    origin=origin_name,
                    items=", ".join(tr_term(item) for item in self.run.loot_summary),
                )
            else:
                self.run.outcome = "retreat"
                summary = tr("summary_retreated_safely", name=self.run.character_name, destination=destination_name)
                detail = tr("detail_retreated_safely", name=self.run.character_name, origin=origin_name)
            self.run._record(summary, detail)
        character.active_adventure_id = None
        self.run._clear_member_adventures(world)
        history_target.add_history(tr("history_adventure_detail", year=world.year, detail=self.run.detail_log[-1]))
        return [self.run.summary_log[-1]]

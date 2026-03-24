"""
adventure.py - Adventure progression for the Fantasy Simulator.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

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

# ---------------------------------------------------------------------------
# Party adventure constants  (design §9.2 / §9.5)
# ---------------------------------------------------------------------------

# Adventure policy (方針) constants
POLICY_CAUTIOUS = "cautious"    # 慎重探索
POLICY_SWIFT = "swift"          # 最短踏破
POLICY_TREASURE = "treasure"    # 金策重視
POLICY_RESCUE = "rescue"        # 救助優先
POLICY_RELIC = "relic"          # 遺物回収重視
POLICY_ASSAULT = "assault"      # 殲滅志向

ALL_POLICIES: tuple = (
    POLICY_CAUTIOUS, POLICY_SWIFT, POLICY_TREASURE,
    POLICY_RESCUE, POLICY_RELIC, POLICY_ASSAULT,
)

# Retreat rule constants
RETREAT_ON_SERIOUS = "on_serious"   # 誰かが serious 以上で撤退
RETREAT_ON_SUPPLY = "on_supply"     # 食料不足で撤退
RETREAT_ON_TROPHY = "on_trophy"     # 希少品確保で帰還
RETREAT_NEVER = "never"             # 撤退基準なし

ALL_RETREAT_RULES: tuple = (RETREAT_ON_SERIOUS, RETREAT_ON_SUPPLY, RETREAT_ON_TROPHY, RETREAT_NEVER)

# Supply state constants
SUPPLY_FULL = "full"
SUPPLY_LOW = "low"
SUPPLY_CRITICAL = "critical"

# Stat baseline for neutral modifier calculations (stats range 1-100, avg ~50)
_STAT_BASELINE: float = 50.0

# Per-policy modifiers on injury probability and loot probability  (design §9.6)
# injury_mod < 1.0 means safer; > 1.0 means riskier
POLICY_INJURY_MOD: Dict[str, float] = {
    POLICY_CAUTIOUS: 0.70,
    POLICY_SWIFT: 1.20,
    POLICY_TREASURE: 1.10,
    POLICY_RESCUE: 0.90,
    POLICY_RELIC: 1.00,
    POLICY_ASSAULT: 1.30,
}

# loot_mod > 1.0 means more/better discoveries
POLICY_LOOT_MOD: Dict[str, float] = {
    POLICY_CAUTIOUS: 0.80,
    POLICY_SWIFT: 0.90,
    POLICY_TREASURE: 1.40,
    POLICY_RESCUE: 0.70,
    POLICY_RELIC: 1.30,
    POLICY_ASSAULT: 1.10,
}

# supply_mod > 1.0 means faster depletion; < 1.0 slower depletion
POLICY_SUPPLY_MOD: Dict[str, float] = {
    POLICY_CAUTIOUS: 0.85,
    POLICY_SWIFT: 0.70,
    POLICY_TREASURE: 1.05,
    POLICY_RESCUE: 0.90,
    POLICY_RELIC: 1.00,
    POLICY_ASSAULT: 1.25,
}

# Base injury probability thresholds (design §9.7)
_BASE_INJURY_CHANCE: float = 0.18
# _BASE_CRITICAL_RATIO: ratio between critical threshold and injury threshold
_BASE_CRITICAL_RATIO: float = 0.24 / 0.18  # ≈ 1.333

# Supply depletion probabilities per exploring step
_SUPPLY_DEGRADE_FULL_TO_LOW: float = 0.15
_SUPPLY_DEGRADE_LOW_TO_CRITICAL: float = 0.20


def select_party_policy(members: List["Character"], rng: Any = random) -> str:
    """AI-driven policy selection based on party ability scores  (design §9.3 / §9.4).

    Spotlighted / playable parties should override this with player input; this
    function covers the NPC / favorite-assist path.
    """
    if not members:
        return POLICY_CAUTIOUS

    avg_wis = sum(c.wisdom for c in members) / len(members)
    avg_str = sum(c.strength for c in members) / len(members)
    avg_int = sum(c.intelligence for c in members) / len(members)
    avg_con = sum(c.constitution for c in members) / len(members)

    # Score each policy using relevant stats
    scores: Dict[str, float] = {
        POLICY_CAUTIOUS: avg_wis,
        POLICY_SWIFT: avg_str * 0.5 + avg_con * 0.5,
        POLICY_TREASURE: avg_int * 0.5 + avg_con * 0.5,
        POLICY_RESCUE: avg_wis * 0.7 + avg_str * 0.3,
        POLICY_RELIC: avg_int,
        POLICY_ASSAULT: avg_str,
    }

    # Weighted selection from top-3 policies (highest score wins most often)
    sorted_policies = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top3 = sorted_policies[:3]
    tier_weights = [1.0, 0.5, 0.2]
    total_weight = sum(tier_weights)
    r = rng.random() * total_weight
    cumulative = 0.0
    for (policy, _), w in zip(top3, tier_weights):
        cumulative += w
        if r <= cumulative:
            return policy
    return top3[0][0]


def default_retreat_rule_for_policy(policy: str) -> str:
    """Return the baseline retreat rule for a selected party policy.

    This is the current extension point for future decision inputs
    (favorite / spotlighted / playable / vow / relationship context).
    """
    mapping = {
        POLICY_CAUTIOUS: RETREAT_ON_SERIOUS,
        POLICY_RESCUE: RETREAT_ON_SERIOUS,
        POLICY_TREASURE: RETREAT_ON_TROPHY,
        POLICY_RELIC: RETREAT_ON_TROPHY,
        POLICY_SWIFT: RETREAT_ON_SUPPLY,
        POLICY_ASSAULT: RETREAT_NEVER,
    }
    return mapping.get(policy, RETREAT_ON_SERIOUS)


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
    """Represents one ongoing adventure inside the main world simulation.

    Party adventure fields (design §9.1):
    - member_ids: all party member char_ids (includes leader / character_id).
      Empty list means legacy solo adventure treated as [character_id].
    - party_id: shared identifier for party; None for solo.
    - policy: adventure policy constant (POLICY_*).
    - retreat_rule: auto-retreat trigger (RETREAT_*).
    - supply_state: current supply level (SUPPLY_*).
    - danger_level: 0-100 danger of target location (scales injury chance).
    """

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
    # Party fields (PR-E)
    member_ids: List[str] = field(default_factory=list)
    party_id: Optional[str] = None
    policy: str = POLICY_CAUTIOUS
    retreat_rule: str = RETREAT_ON_SERIOUS
    supply_state: str = SUPPLY_FULL
    danger_level: int = 50  # 0-100

    @property
    def is_resolved(self) -> bool:
        return self.state == "resolved"

    @property
    def is_party(self) -> bool:
        """True when this run has 2 or more party members."""
        return len(self.member_ids) > 1

    # ------------------------------------------------------------------
    # Ability-score helpers  (design §9.6, Robert C. Martin: pure functions)
    # ------------------------------------------------------------------

    def _party_members(self, world: "World") -> List["Character"]:
        """Return living party members fetched from world via member_ids."""
        members = []
        for mid in self.member_ids:
            c = world.get_character_by_id(mid)
            if c is not None and c.alive:
                members.append(c)
        return members

    @staticmethod
    def _combat_score(members: List["Character"]) -> float:
        """(STR + CON) / 2 average  → combat / endurance score.

        Baseline _STAT_BASELINE (50) = neutral modifier.
        Higher → lower injury chance.  Design §9.6: STR/CON → 正面戦闘・耐久.
        """
        if not members:
            return _STAT_BASELINE
        return sum(c.strength + c.constitution for c in members) / (2 * len(members))

    @staticmethod
    def _evasion_score(members: List["Character"]) -> float:
        """(DEX + WIS) / 2 average → evasion / retreat quality score.

        Design §9.6: DEX/WIS → 罠回避・撤退判断.
        """
        if not members:
            return _STAT_BASELINE
        return sum(c.dexterity + c.wisdom for c in members) / (2 * len(members))

    @staticmethod
    def _lore_score(members: List["Character"]) -> float:
        """INT average → discovery / lore quality score.

        Design §9.6: INT → 禁忌・遺跡・儀式対応.
        """
        if not members:
            return _STAT_BASELINE
        return sum(c.intelligence for c in members) / len(members)

    def _compute_injury_chance(self, members: List["Character"]) -> float:
        """Return adjusted injury probability for this exploring step.

        Factors applied (all multiplicative, then clamped to [0.04, 0.22]):
        - combat_score: higher score → lower chance  (baseline 50 = 1.0 modifier)
        - danger_level: 0.5 at danger=0, 1.0 at danger=50, 1.5 at danger=100

        - policy: POLICY_INJURY_MOD lookup
        """
        combat = self._combat_score(members)
        ability_mod = _STAT_BASELINE / max(combat, 1.0)
        danger_mod = 0.5 + self.danger_level / 100.0
        policy_mod = POLICY_INJURY_MOD.get(self.policy, 1.0)
        chance = _BASE_INJURY_CHANCE * ability_mod * danger_mod * policy_mod
        # Cap at 0.22 so critical_chance (≈ chance * 1.333) stays below 0.30
        return max(0.04, min(0.22, chance))

    def _compute_loot_chance(self, members: List["Character"]) -> float:
        """Return probability that exploration yields a discovery.

        Factors applied (all multiplicative, then clamped to [0.20, 0.95]):
        - lore_score: higher score → higher chance  (baseline 50 = 1.0 modifier)
        - policy: POLICY_LOOT_MOD lookup
        """
        lore = self._lore_score(members)
        ability_mod = lore / _STAT_BASELINE
        policy_mod = POLICY_LOOT_MOD.get(self.policy, 1.0)
        chance = 0.76 * ability_mod * policy_mod
        return max(0.20, min(0.95, chance))

    def _should_auto_retreat(self, members: List["Character"]) -> bool:
        """Return True if retreat_rule triggers for the current party state.

        Design §9.5: retreat conditions.
        """
        if self.retreat_rule == RETREAT_ON_SERIOUS:
            return any(c.injury_status in ("serious", "dying") for c in members)
        if self.retreat_rule == RETREAT_ON_SUPPLY:
            return self.supply_state == SUPPLY_CRITICAL
        if self.retreat_rule == RETREAT_ON_TROPHY:
            return bool(self.loot_summary)
        # RETREAT_NEVER: no automatic retreat
        return False

    def _tick_supply(self, rng: Any) -> None:
        """Probabilistically degrade supply_state during exploration."""
        policy_mod = POLICY_SUPPLY_MOD.get(self.policy, 1.0)
        if self.supply_state == SUPPLY_FULL:
            if rng.random() < _SUPPLY_DEGRADE_FULL_TO_LOW * policy_mod:
                self.supply_state = SUPPLY_LOW
        elif self.supply_state == SUPPLY_LOW:
            if rng.random() < _SUPPLY_DEGRADE_LOW_TO_CRITICAL * policy_mod:
                self.supply_state = SUPPLY_CRITICAL

    def _default_option_for_context(self, context: str) -> str:
        """Return policy-aware default option for pending choice contexts.

        Extension point: future decision_context can include vow/personality/
        relationship and player-control flags.
        """
        if context == "approach":
            approach_defaults = {
                POLICY_CAUTIOUS: CHOICE_PROCEED_CAUTIOUSLY,
                POLICY_RESCUE: CHOICE_PROCEED_CAUTIOUSLY,
                POLICY_TREASURE: CHOICE_PRESS_ON,
                POLICY_RELIC: CHOICE_PRESS_ON,
                POLICY_SWIFT: CHOICE_PRESS_ON,
                POLICY_ASSAULT: CHOICE_PRESS_ON,
            }
            return approach_defaults.get(self.policy, CHOICE_PROCEED_CAUTIOUSLY)

        if context == "depth":
            depth_defaults = {
                POLICY_CAUTIOUS: CHOICE_WITHDRAW,
                POLICY_RESCUE: CHOICE_WITHDRAW,
                POLICY_SWIFT: CHOICE_PRESS_ON,
                POLICY_TREASURE: CHOICE_PRESS_ON,
                POLICY_RELIC: CHOICE_PRESS_ON,
                POLICY_ASSAULT: CHOICE_PRESS_ON,
            }
            return depth_defaults.get(self.policy, CHOICE_WITHDRAW)
        return CHOICE_WITHDRAW

    def _clear_member_adventures(self, world: "World") -> None:
        """Clear active_adventure_id for all non-leader party members."""
        for mid in self.member_ids:
            if mid != self.character_id:
                member = world.get_character_by_id(mid)
                if member is not None:
                    member.active_adventure_id = None

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "character_id": self.character_id,
            "character_name": self.character_name,
            "origin": self.origin,
            "destination": self.destination,
            "year_started": self.year_started,
            "adventure_id": self.adventure_id,
            "state": self.state,
            "injury_status": self.injury_status,
            "steps_taken": self.steps_taken,
            "pending_choice": (
                self.pending_choice.to_dict() if self.pending_choice is not None else None
            ),
            "outcome": self.outcome,
            "loot_summary": list(self.loot_summary),
            "summary_log": list(self.summary_log),
            "detail_log": list(self.detail_log),
            "resolution_year": self.resolution_year,
            "injury_member_id": self.injury_member_id,
            "death_member_id": self.death_member_id,
            # Party fields
            "member_ids": list(self.member_ids),
            "party_id": self.party_id,
            "policy": self.policy,
            "retreat_rule": self.retreat_rule,
            "supply_state": self.supply_state,
            "danger_level": self.danger_level,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdventureRun":
        pending = data.get("pending_choice")
        char_id = data["character_id"]
        # Backward compat: pre-PR-E saves have no member_ids → treat as solo
        member_ids = data.get("member_ids") or [char_id]
        return cls(
            character_id=char_id,
            character_name=data["character_name"],
            origin=data["origin"],
            destination=data["destination"],
            year_started=data["year_started"],
            adventure_id=data.get("adventure_id", uuid.uuid4().hex[:10]),
            state=data.get("state", "traveling"),
            injury_status=data.get("injury_status", "none"),
            steps_taken=data.get("steps_taken", 0),
            pending_choice=AdventureChoice.from_dict(pending) if pending else None,
            outcome=data.get("outcome"),
            loot_summary=list(data.get("loot_summary", [])),
            summary_log=list(data.get("summary_log", [])),
            detail_log=list(data.get("detail_log", [])),
            resolution_year=data.get("resolution_year"),
            injury_member_id=data.get("injury_member_id"),
            death_member_id=data.get("death_member_id"),
            # Party fields
            member_ids=list(member_ids),
            party_id=data.get("party_id"),
            policy=data.get("policy", POLICY_CAUTIOUS),
            retreat_rule=data.get("retreat_rule", RETREAT_ON_SERIOUS),
            supply_state=data.get("supply_state", SUPPLY_FULL),
            danger_level=data.get("danger_level", 50),
        )

    # ------------------------------------------------------------------
    # Core simulation
    # ------------------------------------------------------------------

    def step(self, character: "Character", world: "World", rng: Any = random) -> List[str]:
        """Advance the adventure by one internal step."""
        if self.is_resolved:
            return []

        if self.state == "waiting_for_choice":
            return self.resolve_choice(world, character, option=None)

        dest_name = world.location_name(self.destination)
        origin_name = world.location_name(self.origin)

        if self.state == "traveling":
            self.steps_taken += 1
            summary = tr("summary_adventure_arrived", name=self.character_name, destination=dest_name)
            detail = tr(
                "detail_adventure_arrived",
                name=self.character_name, origin=origin_name, destination=dest_name,
            )
            self._record(summary, detail)
            if rng.random() < 0.35:
                self.pending_choice = AdventureChoice(
                    prompt=tr("choice_dangerous_approach", name=self.character_name, destination=dest_name),
                    options=[CHOICE_PRESS_ON, CHOICE_PROCEED_CAUTIOUSLY, CHOICE_RETREAT],
                    default_option=self._default_option_for_context("approach"),
                    context="approach",
                )
                self.state = "waiting_for_choice"
                self.detail_log.append(tr("detail_paused_at_entrance", name=self.character_name))
            else:
                self.state = "exploring"
            return [summary]

        if self.state == "exploring":
            return self._step_exploring(character, world, rng, dest_name, origin_name)

        if self.state == "returning":
            return self._step_returning(character, world, dest_name, origin_name)

        return []

    def _step_exploring(
        self,
        character: "Character",
        world: "World",
        rng: Any,
        dest_name: str,
        origin_name: str,
    ) -> List[str]:
        """Handle one exploring step with party ability modifiers.

        Design §9.6: ability-dependent outcomes.
        Design §9.5: retreat rule evaluation.
        """
        self.steps_taken += 1

        # Resolve party members for ability calculations
        members = self._party_members(world)
        if not members:
            members = [character]  # fallback: leader only

        # --- Auto-retreat check (retreat_rule, party only) ---
        # Solo characters handle retreat via player choices and the injury roll system.
        # Auto-retreat is a party policy: the group pulls back when a member falls.
        if self.is_party and self._should_auto_retreat(members):
            self.state = "returning"
            summary = tr("summary_party_retreated_auto", name=self.character_name, destination=dest_name)
            detail = tr("detail_party_retreated_auto", name=self.character_name, destination=dest_name)
            self._record(summary, detail)
            return [summary]

        # --- Supply depletion (party runs only; solo runs are too short to exhaust) ---
        if self.is_party:
            self._tick_supply(rng)

        # --- Injury roll with ability + policy + danger modifiers ---
        injury_chance = self._compute_injury_chance(members)
        critical_chance = min(injury_chance * _BASE_CRITICAL_RATIO, 0.60)

        roll = rng.random()
        injured_member = character
        if self.is_party and members:
            injured_member = rng.choice(members)

        if roll < injury_chance:
            # Death staging: worsen character injury
            injured_member.worsen_injury()
            self.injury_status = injured_member.injury_status
            self.injury_member_id = injured_member.char_id
            summary = tr("summary_adventure_injured", name=injured_member.name)
            detail = tr("detail_adventure_injured", name=injured_member.name, destination=dest_name)
            self._record(summary, detail)
            self.state = "returning"
            return [summary]

        if roll < critical_chance:
            # Death staging: if already dying → die; otherwise worsen
            if injured_member.injury_status == "dying":
                self.outcome = "death"
                self.state = "resolved"
                self.resolution_year = world.year
                injured_member.alive = False
                injured_member.active_adventure_id = None
                self.death_member_id = injured_member.char_id
                character.active_adventure_id = None
                self._clear_member_adventures(world)
                summary = tr("summary_adventure_died", name=injured_member.name, destination=dest_name)
                detail = tr(
                    "detail_adventure_died", name=injured_member.name, destination=dest_name
                )
                self._record(summary, detail)
                injured_member.add_history(
                    tr("history_adventure_detail", year=world.year, detail=detail)
                )
                return [summary]
            # Not yet dying: worsen injury and return
            injured_member.worsen_injury()
            self.injury_status = injured_member.injury_status
            self.injury_member_id = injured_member.char_id
            summary = tr("summary_adventure_injured", name=injured_member.name)
            detail = tr("detail_adventure_injured", name=injured_member.name, destination=dest_name)
            self._record(summary, detail)
            self.state = "returning"
            return [summary]

        # --- Discovery (policy and lore dependent) ---
        loot_chance = self._compute_loot_chance(members)
        if rng.random() < loot_chance:
            discovery = rng.choice(ADVENTURE_DISCOVERIES)
            self.loot_summary.append(discovery)
            summary = tr("summary_adventure_discovery", name=self.character_name, destination=dest_name)
            detail = tr(
                "detail_adventure_discovery",
                name=self.character_name, discovery=tr_term(discovery), destination=dest_name,
            )
            self._record(summary, detail)
        else:
            summary = tr("summary_adventure_scouting", name=self.character_name, destination=dest_name)
            detail = tr("detail_adventure_scouting", name=self.character_name, destination=dest_name)
            self._record(summary, detail)

        if self.pending_choice is None and rng.random() < 0.40:
            self.pending_choice = AdventureChoice(
                prompt=tr("choice_press_deeper", name=self.character_name, destination=dest_name),
                options=[CHOICE_PRESS_ON, CHOICE_WITHDRAW],
                default_option=self._default_option_for_context("depth"),
                context="depth",
            )
            self.state = "waiting_for_choice"
            self.detail_log.append(tr("detail_paused_to_delve", name=self.character_name))
        else:
            self.state = "returning"
        return [self.summary_log[-1]]

    def _step_returning(
        self,
        character: "Character",
        world: "World",
        dest_name: str,
        origin_name: str,
    ) -> List[str]:
        """Handle the return leg of the adventure."""
        self.steps_taken += 1
        self.state = "resolved"
        self.resolution_year = world.year
        history_target = character
        if self.outcome != "death":
            if self.injury_status != "none":
                self.outcome = "injury"
                injured_member = world.get_character_by_id(self.injury_member_id or self.character_id)
                if injured_member is None:
                    injured_member = character
                injured_member.injury_status = self.injury_status
                summary = tr("summary_returned_injured", name=injured_member.name, destination=dest_name)
                detail = tr("detail_returned_injured", name=injured_member.name, origin=origin_name)
                history_target = injured_member
            elif self.loot_summary:
                self.outcome = "safe_return"
                summary = tr(
                    "summary_returned_safely",
                    name=self.character_name, destination=dest_name,
                    loot=tr_term(self.loot_summary[-1]),
                )
                detail = tr(
                    "detail_returned_safely",
                    name=self.character_name, origin=origin_name,
                    items=", ".join(tr_term(item) for item in self.loot_summary),
                )
            else:
                self.outcome = "retreat"
                summary = tr("summary_retreated_safely", name=self.character_name, destination=dest_name)
                detail = tr("detail_retreated_safely", name=self.character_name, origin=origin_name)
            self._record(summary, detail)
        character.active_adventure_id = None
        self._clear_member_adventures(world)
        history_target.add_history(tr("history_adventure_detail", year=world.year, detail=self.detail_log[-1]))
        return [self.summary_log[-1]]

    def resolve_choice(
        self,
        world: "World",
        character: "Character",
        option: Optional[str] = None,
    ) -> List[str]:
        """Resolve the current pending choice or apply its default option."""
        if self.pending_choice is None:
            return []

        chosen = option or self.pending_choice.default_option
        if chosen not in self.pending_choice.options:
            chosen = self.pending_choice.default_option
        self.pending_choice.selected_option = chosen

        detail = tr("detail_choice_made", name=self.character_name, choice=tr(f"choice_{chosen}"))
        self.detail_log.append(detail)

        context = self.pending_choice.context
        self.pending_choice = None

        if chosen in (CHOICE_RETREAT, CHOICE_WITHDRAW):
            self.state = "returning"
            summary = tr("summary_choice_withdraw", name=self.character_name)
            self.summary_log.append(summary)
            self.detail_log.append(tr("detail_choice_withdraw", name=self.character_name))
            return [summary]

        if context == "approach" and chosen == CHOICE_PROCEED_CAUTIOUSLY:
            self.state = "exploring"
            dest_name = world.location_name(self.destination)
            self.detail_log.append(tr("detail_choice_cautious", name=self.character_name, destination=dest_name))
            return []

        if context in ("approach", "depth") and chosen == CHOICE_PRESS_ON:
            self.state = "exploring"
            dest_name = world.location_name(self.destination)
            self.detail_log.append(tr("detail_choice_press_on", name=self.character_name, destination=dest_name))
            return []

        self.state = "exploring"
        return []

    def _record(self, summary: str, detail: str) -> None:
        self.summary_log.append(summary)
        self.detail_log.append(detail)


def create_adventure_run(
    character: "Character",
    world: "World",
    rng: Any = random,
    id_rng: Any = random,
) -> "AdventureRun":
    """Create a new solo adventure for a character using nearby risky terrain when possible."""
    neighbors = world.get_neighboring_locations(character.location_id)
    risky = [loc for loc in neighbors if loc.region_type in ("forest", "mountain", "dungeon")]
    if not risky:
        risky = [
            loc for loc in world.grid.values()
            if loc.region_type in ("forest", "mountain", "dungeon")
        ]
    if not risky and not world.grid:
        raise ValueError("Cannot create adventure: world has no locations")
    destination = rng.choice(risky) if risky else world.random_location(rng=rng)

    origin_name = world.location_name(character.location_id)
    dest_name = world.location_name(destination.id)

    # Capture danger level from destination location
    danger_level = getattr(destination, "danger", 50)

    run = AdventureRun(
        character_id=character.char_id,
        character_name=character.name,
        origin=character.location_id,
        destination=destination.id,
        year_started=world.year,
        adventure_id=generate_adventure_id(id_rng),
        member_ids=[character.char_id],  # solo run: only leader
        danger_level=danger_level,
    )
    run._record(
        tr("summary_adventure_set_out", name=character.name, origin=origin_name, destination=dest_name),
        tr("detail_adventure_set_out", name=character.name, origin=origin_name, destination=dest_name),
    )
    return run

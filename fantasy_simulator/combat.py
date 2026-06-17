"""Reusable combat resolution primitives."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Protocol


class Combatant(Protocol):
    char_id: str
    name: str
    location_id: str
    injury_status: str
    skills: dict[str, int]

    @property
    def combat_power(self) -> int: ...

    @property
    def constitution(self) -> int: ...

    @property
    def dexterity(self) -> int: ...

    @property
    def intelligence(self) -> int: ...

    @property
    def wisdom(self) -> int: ...

    def apply_stat_delta(self, deltas: dict[str, int]) -> None: ...

    def update_mutual_relationship(self, other: Any, delta: int, delta_other: int | None = None) -> None: ...

    def worsen_injury(self) -> str: ...

    def add_history(self, event: str) -> None: ...

    def add_relation_tag(self, other_id: str, tag: str, source_event_id: str | None = None) -> None: ...


@dataclass(frozen=True, slots=True)
class CombatLogEntry:
    round_number: int
    actor_id: str
    actor_name: str
    target_id: str
    target_name: str
    tactic: str
    action_kind: str
    skill_key: str
    dice: int
    modifier: int
    target_number: int
    attack_total: int
    defense_total: int
    margin: int
    damage: int
    actor_vitality: int
    target_vitality: int
    outcome: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_number": self.round_number,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "tactic": self.tactic,
            "action_kind": self.action_kind,
            "skill_key": self.skill_key,
            "dice": self.dice,
            "modifier": self.modifier,
            "target_number": self.target_number,
            "attack_total": self.attack_total,
            "defense_total": self.defense_total,
            "margin": self.margin,
            "damage": self.damage,
            "actor_vitality": self.actor_vitality,
            "target_vitality": self.target_vitality,
            "outcome": self.outcome,
        }


@dataclass(frozen=True, slots=True)
class CombatResolution:
    winner: Combatant
    loser: Combatant
    winner_power: int
    loser_power: int
    winner_gains: dict[str, int]
    loser_losses: dict[str, int]
    log_entries: tuple[CombatLogEntry, ...] = field(default_factory=tuple)

    def combat_log_payload(self) -> list[dict[str, Any]]:
        return [entry.to_dict() for entry in self.log_entries]


_TACTICS = ("opening pressure", "guard break", "counterattack")
MARTIAL_SKILLS = frozenset({
    "Swordsmanship",
    "Shield Block",
    "Battle Cry",
    "Endurance",
    "Archery",
    "Unarmed Combat",
    "Heavy Armor",
    "Holy Strike",
})
SPELL_EFFECTS: dict[str, dict[str, int | str]] = {
    "Fireball": {"kind": "spell_attack", "attack_bonus": 5, "damage_bonus": 2},
    "Nature's Wrath": {"kind": "spell_attack", "attack_bonus": 4, "damage_bonus": 2},
    "Holy Strike": {"kind": "weapon_art", "attack_bonus": 3, "damage_bonus": 1},
    "Arcane Shield": {"kind": "spell_guard", "defense_bonus": 5, "guard_bonus": 2},
    "Divine Shield": {"kind": "spell_guard", "defense_bonus": 4, "guard_bonus": 2},
    "Evasion": {"kind": "maneuver", "defense_bonus": 3, "guard_bonus": 1},
}
MAX_COMBAT_ROUNDS = 5


def resolve_combat(char1: Combatant, char2: Combatant, rng: Any = random) -> CombatResolution:
    """Resolve a reusable combat exchange without applying side effects."""
    vitality = {
        char1.char_id: _starting_vitality(char1),
        char2.char_id: _starting_vitality(char2),
    }
    log_entries: list[CombatLogEntry] = []
    initiative = _initiative_total(char1, rng) >= _initiative_total(char2, rng)
    attacker, defender = (char1, char2) if initiative else (char2, char1)

    for round_number in range(1, MAX_COMBAT_ROUNDS + 1):
        entry = _resolve_combat_round(
            round_number,
            attacker,
            defender,
            vitality,
            rng,
        )
        log_entries.append(entry)
        if vitality[defender.char_id] <= 0:
            break
        attacker, defender = defender, attacker

    char1_score = _final_combat_score(char1, vitality[char1.char_id], log_entries)
    char2_score = _final_combat_score(char2, vitality[char2.char_id], log_entries)
    winner, loser = (char1, char2) if char1_score >= char2_score else (char2, char1)
    winner_power, loser_power = (char1_score, char2_score) if winner is char1 else (char2_score, char1_score)
    winner_gains = {"strength": _randint(rng, 1, 3), "constitution": _randint(rng, 0, 2)}
    loser_losses = {"constitution": -_randint(rng, 2, 8), "strength": -_randint(rng, 0, 3)}
    return CombatResolution(
        winner=winner,
        loser=loser,
        winner_power=winner_power,
        loser_power=loser_power,
        winner_gains=winner_gains,
        loser_losses=loser_losses,
        log_entries=tuple(_mark_decisive_entry(log_entries, winner, loser)),
    )


def _starting_vitality(combatant: Combatant) -> int:
    return max(3, 10 + combatant.constitution // 10)


def _initiative_total(combatant: Combatant, rng: Any) -> int:
    return combatant.dexterity // 5 + _skill_level(combatant, "Evasion") + _randint(rng, 1, 20)


def _final_combat_score(
    combatant: Combatant,
    remaining_vitality: int,
    log_entries: list[CombatLogEntry],
) -> int:
    dealt = sum(entry.damage for entry in log_entries if entry.actor_id == combatant.char_id)
    return combatant.combat_power + remaining_vitality + dealt


def _resolve_combat_round(
    round_number: int,
    attacker: Combatant,
    defender: Combatant,
    vitality: dict[str, int],
    rng: Any,
) -> CombatLogEntry:
    skill_key, action_kind = _select_action(attacker)
    dice = _randint(rng, 1, 20)
    attack_modifier = _attack_modifier(attacker, skill_key, action_kind)
    defense_total = _defense_total(defender, rng)
    attack_total = dice + attack_modifier
    target_number = defense_total
    margin = attack_total - defense_total
    damage = _damage_for_margin(margin, skill_key)
    vitality[defender.char_id] = max(0, vitality[defender.char_id] - damage)
    return _log_entry(
        round_number,
        attacker,
        defender,
        _TACTICS[(round_number - 1) % len(_TACTICS)],
        action_kind,
        skill_key,
        dice,
        attack_modifier,
        target_number,
        attack_total,
        defense_total,
        damage,
        vitality[attacker.char_id],
        vitality[defender.char_id],
        _round_outcome(margin, damage),
    )


def _select_action(combatant: Combatant) -> tuple[str, str]:
    spell_skill = _best_skill(combatant, SPELL_EFFECTS)
    martial_skill = _best_skill(combatant, MARTIAL_SKILLS)
    if spell_skill and _skill_level(combatant, spell_skill) >= max(2, _skill_level(combatant, martial_skill)):
        effect_kind = str(SPELL_EFFECTS[spell_skill].get("kind", "spell_attack"))
        return spell_skill, effect_kind
    if martial_skill:
        return martial_skill, "weapon_attack"
    return "", "weapon_attack"


def _best_skill(combatant: Combatant, candidates: Any) -> str:
    skills = getattr(combatant, "skills", {})
    best_skill = ""
    best_level = 0
    for skill_key in candidates:
        level = int(skills.get(skill_key, 0))
        if level > best_level:
            best_skill = skill_key
            best_level = level
    return best_skill


def _skill_level(combatant: Combatant, skill_key: str) -> int:
    if not skill_key:
        return 0
    return int(getattr(combatant, "skills", {}).get(skill_key, 0))


def _attack_modifier(combatant: Combatant, skill_key: str, action_kind: str) -> int:
    if action_kind.startswith("spell"):
        base = max(combatant.intelligence, combatant.wisdom) // 5
    else:
        base = combatant.combat_power // 5
    effect = SPELL_EFFECTS.get(skill_key, {})
    return base + _skill_level(combatant, skill_key) * 2 + int(effect.get("attack_bonus", 0))


def _defense_total(combatant: Combatant, rng: Any) -> int:
    guard_skill = _best_skill(combatant, ("Shield Block", "Arcane Shield", "Divine Shield", "Evasion"))
    effect = SPELL_EFFECTS.get(guard_skill, {})
    guard_bonus = int(effect.get("defense_bonus", 0))
    return 10 + combatant.dexterity // 6 + combatant.constitution // 8 + _skill_level(combatant, guard_skill) + (
        guard_bonus + _randint(rng, 1, 12)
    )


def _damage_for_margin(margin: int, skill_key: str) -> int:
    if margin < 0:
        return 0
    effect = SPELL_EFFECTS.get(skill_key, {})
    return max(1, 1 + margin // 6 + int(effect.get("damage_bonus", 0)))


def _round_outcome(margin: int, damage: int) -> str:
    if damage <= 0:
        return "miss"
    if margin >= 12:
        return "decisive"
    if margin >= 4:
        return "advantage"
    return "checked"


def _mark_decisive_entry(
    log_entries: list[CombatLogEntry],
    winner: Combatant,
    loser: Combatant,
) -> tuple[CombatLogEntry, ...]:
    if not log_entries:
        return ()
    for index in range(len(log_entries) - 1, -1, -1):
        entry = log_entries[index]
        if entry.actor_id == winner.char_id and entry.target_id == loser.char_id and entry.damage > 0:
            log_entries[index] = CombatLogEntry(**{**entry.to_dict(), "outcome": "decisive"})
            break
    return tuple(log_entries)


def _randint(rng: Any, low: int, high: int) -> int:
    randint = getattr(rng, "randint", None)
    if callable(randint):
        return int(randint(low, high))
    choice = getattr(rng, "choice", None)
    if callable(choice):
        return int(choice(list(range(low, high + 1))))
    random_value = getattr(rng, "random", None)
    if callable(random_value):
        return low + int(float(random_value()) * (high - low + 1))
    return random.randint(low, high)


def _log_entry(
    round_number: int,
    actor: Combatant,
    target: Combatant,
    tactic: str,
    action_kind: str,
    skill_key: str,
    dice: int,
    modifier: int,
    target_number: int,
    attack_total: int,
    defense_total: int,
    damage: int,
    actor_vitality: int,
    target_vitality: int,
    outcome: str,
) -> CombatLogEntry:
    return CombatLogEntry(
        round_number=round_number,
        actor_id=actor.char_id,
        actor_name=actor.name,
        target_id=target.char_id,
        target_name=target.name,
        tactic=tactic,
        action_kind=action_kind,
        skill_key=skill_key,
        dice=dice,
        modifier=modifier,
        target_number=target_number,
        attack_total=attack_total,
        defense_total=defense_total,
        margin=attack_total - defense_total,
        damage=damage,
        actor_vitality=actor_vitality,
        target_vitality=target_vitality,
        outcome=outcome,
    )

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

    @property
    def combat_power(self) -> int: ...

    @property
    def constitution(self) -> int: ...

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
    attack_total: int
    defense_total: int
    margin: int
    outcome: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_number": self.round_number,
            "actor_id": self.actor_id,
            "actor_name": self.actor_name,
            "target_id": self.target_id,
            "target_name": self.target_name,
            "tactic": self.tactic,
            "attack_total": self.attack_total,
            "defense_total": self.defense_total,
            "margin": self.margin,
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


def resolve_combat(char1: Combatant, char2: Combatant, rng: Any = random) -> CombatResolution:
    """Resolve a reusable combat exchange without applying side effects."""
    power1 = char1.combat_power + rng.randint(0, 30)
    power2 = char2.combat_power + rng.randint(0, 30)
    winner, loser = (char1, char2) if power1 >= power2 else (char2, char1)
    winner_power, loser_power = (power1, power2) if winner is char1 else (power2, power1)
    winner_gains = {"strength": rng.randint(1, 3), "constitution": rng.randint(0, 2)}
    loser_losses = {"constitution": -rng.randint(2, 8), "strength": -rng.randint(0, 3)}
    return CombatResolution(
        winner=winner,
        loser=loser,
        winner_power=winner_power,
        loser_power=loser_power,
        winner_gains=winner_gains,
        loser_losses=loser_losses,
        log_entries=_build_combat_log(winner, loser, winner_power, loser_power),
    )


def _build_combat_log(
    winner: Combatant,
    loser: Combatant,
    winner_power: int,
    loser_power: int,
) -> tuple[CombatLogEntry, ...]:
    gap = max(1, winner_power - loser_power)
    opening_margin = max(1, gap // 3)
    pressure_margin = max(1, gap // 2)
    return (
        _log_entry(1, winner, loser, _TACTICS[0], loser_power + opening_margin, loser_power, "advantage"),
        _log_entry(2, loser, winner, _TACTICS[2], loser_power, winner_power - pressure_margin, "checked"),
        _log_entry(3, winner, loser, _TACTICS[1], winner_power, loser_power, "decisive"),
    )


def _log_entry(
    round_number: int,
    actor: Combatant,
    target: Combatant,
    tactic: str,
    attack_total: int,
    defense_total: int,
    outcome: str,
) -> CombatLogEntry:
    return CombatLogEntry(
        round_number=round_number,
        actor_id=actor.char_id,
        actor_name=actor.name,
        target_id=target.char_id,
        target_name=target.name,
        tactic=tactic,
        attack_total=attack_total,
        defense_total=defense_total,
        margin=attack_total - defense_total,
        outcome=outcome,
    )

"""Combat encounters used by adventure hazards."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .combat import resolve_combat


@dataclass(frozen=True)
class AdventureHazardResult:
    severity_steps: int
    hazard_name: str
    rounds: int


class AdventureHazardCombatant:
    """Ephemeral combatant for an adventure-site hazard."""

    def __init__(
        self,
        *,
        char_id: str,
        name: str,
        location_id: str,
        combat_power: int,
        constitution: int,
        dexterity: int,
        intelligence: int,
        wisdom: int,
        skills: dict[str, int],
    ) -> None:
        self.char_id = char_id
        self.name = name
        self.location_id = location_id
        self.injury_status = "none"
        self._combat_power = combat_power
        self.constitution = constitution
        self.dexterity = dexterity
        self.intelligence = intelligence
        self.wisdom = wisdom
        self.skills = dict(skills)

    @property
    def combat_power(self) -> int:
        return self._combat_power

    def apply_stat_delta(self, deltas: dict[str, int]) -> None:
        del deltas

    def update_mutual_relationship(self, other: Any, delta: int, delta_other: int | None = None) -> None:
        del other, delta, delta_other

    def worsen_injury(self) -> str:
        return self.injury_status

    def add_history(self, event: str) -> None:
        del event

    def add_relation_tag(self, other_id: str, tag: str, source_event_id: str | None = None) -> None:
        del other_id, tag, source_event_id


def resolve_adventure_hazard_combat(run: Any, member: Any, world: Any, rng: Any) -> AdventureHazardResult:
    """Resolve a local hazard as combat and append a JSON-ready log to the run."""
    hazard = _hazard_for_run(run, world)
    resolution = resolve_combat(member, hazard, rng)
    combat_log = resolution.combat_log_payload()
    run.combat_logs.append({
        "step": int(getattr(run, "steps_taken", 0)),
        "location_id": run.destination,
        "member_id": member.char_id,
        "member_name": member.name,
        "hazard_id": hazard.char_id,
        "hazard_name": hazard.name,
        "winner_id": resolution.winner.char_id,
        "loser_id": resolution.loser.char_id,
        "winner_power": resolution.winner_power,
        "loser_power": resolution.loser_power,
        "combat_log": combat_log,
    })
    return AdventureHazardResult(
        severity_steps=_hazard_injury_severity(resolution.loser.char_id == member.char_id, run.danger_level),
        hazard_name=hazard.name,
        rounds=len(combat_log),
    )


def _hazard_for_run(run: Any, world: Any) -> AdventureHazardCombatant:
    location = world.get_location_by_id(run.destination)
    region_type = str(getattr(location, "region_type", "wilds")) if location is not None else "wilds"
    danger = int(getattr(location, "danger", run.danger_level)) if location is not None else int(run.danger_level)
    danger = max(0, min(100, max(danger, int(run.danger_level))))
    skills = _hazard_skills(region_type, danger)
    return AdventureHazardCombatant(
        char_id=f"hazard:{run.adventure_id}:{run.steps_taken}",
        name=_hazard_name(region_type),
        location_id=run.destination,
        combat_power=28 + danger // 3,
        constitution=35 + danger // 4,
        dexterity=30 + danger // 5,
        intelligence=25 + danger // 6,
        wisdom=25 + danger // 6,
        skills=skills,
    )


def _hazard_name(region_type: str) -> str:
    names = {
        "dungeon": "dungeon guardian",
        "forest": "forest warden",
        "mountain": "ridge ambusher",
        "swamp": "marsh stalker",
    }
    return names.get(region_type, "wildland threat")


def _hazard_skills(region_type: str, danger: int) -> dict[str, int]:
    base_level = 1 + danger // 40
    if region_type == "forest":
        return {"Nature's Wrath": base_level + 1, "Evasion": base_level}
    if region_type == "dungeon":
        return {"Swordsmanship": base_level + 1, "Shield Block": base_level, "Fireball": max(1, base_level - 1)}
    if region_type == "mountain":
        return {"Archery": base_level + 1, "Evasion": base_level}
    return {"Swordsmanship": base_level, "Battle Cry": max(1, base_level - 1)}


def _hazard_injury_severity(member_lost: bool, danger_level: int) -> int:
    if member_lost and danger_level >= 75:
        return 2
    return 1

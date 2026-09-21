"""Current party capabilities: a specialist leads, at most two helpers contribute."""

from dataclasses import dataclass
from typing import Any


ROLE_SKILLS = {
    "frontline": ("Swordsmanship", "Shield Block", "Unarmed Combat", "Holy Strike"),
    "scout": ("Track", "Navigation", "Trap Disarm", "Dungeoneering", "Stealth"),
    "lore": ("Lore Mastery", "Spellcraft", "Arcane Sensing", "Appraisal"),
    "medic": ("First Aid", "Regeneration", "Lay on Hands", "Holy Light"),
}
ROLE_STATS = {
    "frontline": ("strength", "constitution"), "scout": ("dexterity", "wisdom"),
    "lore": ("intelligence", "wisdom"), "medic": ("wisdom", "intelligence"),
}
FITNESS = {"none": 1.0, "injured": 0.65, "serious": 0.25, "dying": 0.0}


@dataclass(frozen=True)
class RoleCapability:
    holder_id: str | None
    score: float


def aptitude(actor: Any, role: str) -> float:
    if not actor.alive:
        return 0.0
    skill = max((actor.skills.get(key, 0) for key in ROLE_SKILLS[role]), default=0)
    if role == "medic" and skill <= 0:
        return 0.0
    stats = ROLE_STATS[role]
    ability = sum(getattr(actor, key) for key in stats) / len(stats)
    return (ability + 3 * min(10, max(0, skill))) * FITNESS[actor.injury_status]


def capability(members: list[Any], role: str) -> RoleCapability:
    ranked = sorted(((aptitude(actor, role), actor.char_id) for actor in members),
                    key=lambda item: (-item[0], item[1]))
    ranked = [item for item in ranked if item[0] > 0]
    if not ranked:
        return RoleCapability(None, 0.0)
    # A specialist is never diluted by a novice. Extra bodies still consume supplies.
    score = sum(item[0] * weight for item, weight in zip(ranked, (1.0, 0.25, 0.125)))
    return RoleCapability(ranked[0][1], score)


def role_holders(members: list[Any]) -> dict[str, str]:
    result = {}
    for role in ROLE_SKILLS:
        holder = capability(members, role).holder_id
        if holder is not None:
            result[role] = holder
    return result


def choose_companions(leader: Any, candidates: list[Any], count: int, *, target: Any = None) -> list[Any]:
    """Invite healthy, willing colocated actors who fill the party's current needs."""
    available = [actor for actor in candidates
                 if actor.char_id != leader.char_id and actor.alive and actor.active_adventure_id is None
                 and actor.injury_status == "none" and actor.location_id == leader.location_id
                 and min(actor.get_relationship(leader.char_id), leader.get_relationship(actor.char_id)) >= 0
                 and (target is None or actor.get_relationship(target.char_id) >= 0)]
    members = [leader]
    weights = {"frontline": 1.0, "scout": 1.0, "lore": 0.5 if target else 1.5,
               "medic": 2.0 if target else 1.0}
    for _ in range(min(count, len(available))):
        baseline = {role: capability(members, role).score for role in weights}

        def gain(actor: Any) -> tuple[float, str]:
            improvement = sum(weight * (capability([*members, actor], role).score - baseline[role])
                              for role, weight in weights.items())
            return -improvement, actor.char_id

        chosen = min(available, key=gain)
        members.append(chosen)
        available.remove(chosen)
    return members[1:]


def party_care_factor(world: Any, patient: Any, tick: int) -> float:
    """Funded accompanying care reduces deterioration, never unrelated aging."""
    if patient.injury_status not in ("injured", "serious") or not patient.active_adventure_id:
        return 1.0
    run = world.get_adventure_by_id(patient.active_adventure_id)
    if run is None or run.is_resolved or run.objective is None or run.schedule is None:
        return 1.0
    if patient.char_id not in run.member_ids or run.schedule.remaining_provisions(tick, len(run.member_ids)) <= 0:
        return 1.0
    companions = [world.get_character_by_id(mid) for mid in run.member_ids if mid != patient.char_id]
    companions = [actor for actor in companions if actor is not None
                  and actor.active_adventure_id == run.adventure_id and actor.location_id == patient.location_id]
    score = capability(companions, "medic").score
    return 1.0 - min(0.4, score / 250.0)

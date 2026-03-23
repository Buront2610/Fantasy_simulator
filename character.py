"""
character.py - Core Character class for the Fantasy Simulator.
"""

from __future__ import annotations

import random
import uuid
from typing import Any, Dict, List, Optional

from i18n import tr, tr_term
from world_data import NAME_TO_LOCATION_ID, fallback_location_id


class Character:
    """Represents a living (or deceased) inhabitant of the world."""

    # Valid injury status values (design §8: healthy → injured → serious → dying → dead)
    VALID_INJURY_STATUSES = ("none", "injured", "serious", "dying")

    def __init__(
        self,
        name: str,
        age: int,
        gender: str,
        race: str,
        job: str,
        *,
        strength: int = 10,
        intelligence: int = 10,
        dexterity: int = 10,
        wisdom: int = 10,
        charisma: int = 10,
        constitution: int = 10,
        skills: Optional[Dict[str, int]] = None,
        relationships: Optional[Dict[str, int]] = None,
        alive: bool = True,
        location_id: str = "loc_aethoria_capital",
        favorite: bool = False,
        spotlighted: bool = False,
        playable: bool = False,
        history: Optional[List[str]] = None,
        char_id: Optional[str] = None,
        spouse_id: Optional[str] = None,
        injury_status: str = "none",
        active_adventure_id: Optional[str] = None,
        relation_tags: Optional[Dict[str, List[str]]] = None,
        rng: Any = None,
    ) -> None:
        if char_id:
            self.char_id: str = char_id
        elif rng is not None:
            self.char_id = format(rng.getrandbits(32), "08x")
        else:
            self.char_id = uuid.uuid4().hex[:8]
        self.name: str = name
        self.age: int = age
        self.gender: str = gender
        self.race: str = race
        self.job: str = job

        self.strength: int = self._clamp(strength)
        self.intelligence: int = self._clamp(intelligence)
        self.dexterity: int = self._clamp(dexterity)
        self.wisdom: int = self._clamp(wisdom)
        self.charisma: int = self._clamp(charisma)
        self.constitution: int = self._clamp(constitution)

        self.skills: Dict[str, int] = skills if skills is not None else {}
        self.relationships: Dict[str, int] = relationships if relationships is not None else {}
        self.alive: bool = alive
        self.location_id: str = location_id
        self.favorite: bool = favorite
        self.spotlighted: bool = spotlighted
        self.playable: bool = playable
        self.history: List[str] = history if history is not None else []
        self.spouse_id: Optional[str] = spouse_id
        self.injury_status: str = injury_status if injury_status in self.VALID_INJURY_STATUSES else "none"
        self.active_adventure_id: Optional[str] = active_adventure_id
        # Structured relationship tags (design §7.4): maps char_id -> list of tags
        # e.g. {"abc123": ["friend", "savior"], "def456": ["rival"]}
        self.relation_tags: Dict[str, List[str]] = (
            relation_tags if relation_tags is not None else {}
        )

    @staticmethod
    def _clamp(value: int, lo: int = 1, hi: int = 100) -> int:
        return max(lo, min(hi, value))

    @property
    def combat_power(self) -> int:
        return (self.strength * 2 + self.dexterity + self.constitution) // 4

    @property
    def max_age(self) -> int:
        lifespans = {
            "Human": 80,
            "Elf": 600,
            "Dwarf": 250,
            "Halfling": 130,
            "Orc": 60,
            "Tiefling": 100,
            "Dragonborn": 80,
        }
        return lifespans.get(self.race, 80)

    def apply_stat_delta(self, deltas: Dict[str, int]) -> None:
        stat_names = {"strength", "intelligence", "dexterity", "wisdom", "charisma", "constitution"}
        for stat, delta in deltas.items():
            if stat in stat_names:
                current = getattr(self, stat)
                setattr(self, stat, self._clamp(current + delta))

    def level_up_skill(self, skill_name: str, amount: int = 1) -> str:
        current = self.skills.get(skill_name, 0)
        new_level = min(10, current + amount)
        self.skills[skill_name] = new_level
        if new_level > current:
            return tr("skill_improved", name=self.name, skill=skill_name, level=new_level)
        return tr("skill_already_max", name=self.name, skill=skill_name)

    @property
    def is_dying(self) -> bool:
        """True if this character is in the dying stage (SI-11: alive=True while dying)."""
        return self.alive and self.injury_status == "dying"

    def worsen_injury(self) -> str:
        """Advance injury one stage: none→injured→serious→dying. Returns new status."""
        progression = {"none": "injured", "injured": "serious", "serious": "dying"}
        self.injury_status = progression.get(self.injury_status, self.injury_status)
        return self.injury_status

    def add_relation_tag(self, other_id: str, tag: str) -> None:
        """Add a relation tag for another character (idempotent)."""
        tags = self.relation_tags.setdefault(other_id, [])
        if tag not in tags:
            tags.append(tag)

    def has_relation_tag(self, other_id: str, tag: str) -> bool:
        """Check if a relation tag exists for another character."""
        return tag in self.relation_tags.get(other_id, [])

    def get_relation_tags(self, other_id: str) -> List[str]:
        """Return all relation tags for another character."""
        return list(self.relation_tags.get(other_id, []))

    def update_relationship(self, other_id: str, delta: int) -> None:
        current = self.relationships.get(other_id, 0)
        self.relationships[other_id] = max(-100, min(100, current + delta))

    def update_mutual_relationship(self, other: "Character", delta: int, delta_other: Optional[int] = None) -> None:
        """Update relationships symmetrically between two characters.

        If *delta_other* is None, both sides receive *delta*.
        """
        self.update_relationship(other.char_id, delta)
        other.update_relationship(self.char_id, delta_other if delta_other is not None else delta)

    def add_history(self, event: str) -> None:
        self.history.append(event)

    def get_relationship(self, other_id: str) -> int:
        return self.relationships.get(other_id, 0)

    @property
    def location_display_name(self) -> str:
        """Derive a human-readable name from location_id.

        This is a fallback for contexts where World is not available.
        Prefer ``world.location_name(char.location_id)`` when possible.
        """
        lid = self.location_id
        if lid.startswith("loc_"):
            lid = lid[4:]
        return lid.replace("_", " ").title()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "char_id": self.char_id,
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "race": self.race,
            "job": self.job,
            "strength": self.strength,
            "intelligence": self.intelligence,
            "dexterity": self.dexterity,
            "wisdom": self.wisdom,
            "charisma": self.charisma,
            "constitution": self.constitution,
            "skills": self.skills,
            "relationships": self.relationships,
            "alive": self.alive,
            "location_id": self.location_id,
            "favorite": self.favorite,
            "spotlighted": self.spotlighted,
            "playable": self.playable,
            "history": self.history,
            "spouse_id": self.spouse_id,
            "injury_status": self.injury_status,
            "active_adventure_id": self.active_adventure_id,
            "relation_tags": {k: list(v) for k, v in self.relation_tags.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Character":
        # Clamp skill levels to [0, 10] and relationships to [-100, 100]
        raw_skills = data.get("skills", {})
        skills = {k: max(0, min(10, v)) for k, v in raw_skills.items()}
        raw_rels = data.get("relationships", {})
        relationships = {k: max(-100, min(100, v)) for k, v in raw_rels.items()}
        # Support both old "location" and new "location_id" keys
        location_id = data.get("location_id")
        if location_id is None:
            old_name = data.get("location", "Aethoria Capital")
            location_id = NAME_TO_LOCATION_ID.get(old_name, fallback_location_id(old_name))
        return cls(
            name=data["name"],
            age=data["age"],
            gender=data["gender"],
            race=data["race"],
            job=data["job"],
            strength=data.get("strength", 10),
            intelligence=data.get("intelligence", 10),
            dexterity=data.get("dexterity", 10),
            wisdom=data.get("wisdom", 10),
            charisma=data.get("charisma", 10),
            constitution=data.get("constitution", 10),
            skills=skills,
            relationships=relationships,
            alive=data.get("alive", True),
            location_id=location_id,
            favorite=data.get("favorite", False),
            spotlighted=data.get("spotlighted", False),
            playable=data.get("playable", False),
            history=data.get("history", []),
            char_id=data.get("char_id"),
            spouse_id=data.get("spouse_id"),
            injury_status=data.get("injury_status", "none"),
            active_adventure_id=data.get("active_adventure_id"),
            relation_tags={
                k: list(v) for k, v in data.get("relation_tags", {}).items()
            },
        )

    def __repr__(self) -> str:  # pragma: no cover
        status = "alive" if self.alive else "deceased"
        return (
            f"Character(name={self.name!r}, race={self.race!r}, "
            f"job={self.job!r}, age={self.age}, status={status})"
        )

    def stat_block(self) -> str:
        lines = [
            f"  {tr('name_label'):<10}: {self.name}",
            f"  {tr('race_job_label'):<10}: {tr_term(self.race)} {tr_term(self.job)}",
            f"  {tr('age_gender_label'):<10}: {self.age}  |  {tr('gender_label')}: {tr_term(self.gender)}",
            f"  {tr('location_label'):<10}: {self.location_display_name}",
            f"  {tr('status_label'):<10}: {tr('status_alive') if self.alive else tr('status_dead')}",
            f"  {tr('stats_label')}",
            (
                f"  {tr('stat_str')} {self.strength:>3}  |  "
                f"{tr('stat_int')} {self.intelligence:>3}  |  "
                f"{tr('stat_dex')} {self.dexterity:>3}"
            ),
            (
                f"  {tr('stat_wis')} {self.wisdom:>3}  |  "
                f"{tr('stat_cha')} {self.charisma:>3}  |  "
                f"{tr('stat_con')} {self.constitution:>3}"
            ),
        ]
        if self.skills:
            top_skills = sorted(self.skills.items(), key=lambda x: -x[1])[:5]
            skill_str = "  |  ".join(f"{tr_term(k)}(Lv{v})" for k, v in top_skills)
            lines.append(f"  {tr('top_skills_label')}")
            lines.append(f"  {skill_str}")
        if self.injury_status != "none":
            lines.append(f"  {tr('injury_label'):<10}: {tr(f'injury_status_{self.injury_status}')}")
        if self.relation_tags:
            lines.append(f"  {tr('relations_label')}")
            for other_id, tags in list(self.relation_tags.items())[:5]:
                tag_str = ", ".join(tr(f"relation_tag_{t}") for t in tags)
                lines.append(f"    {other_id[:8]}: {tag_str}")
        return "\n".join(lines)


def random_stats(
    base: int = 30,
    spread: int = 40,
    race_bonuses: Optional[Dict[str, int]] = None,
    rng: Any = random,
) -> Dict[str, int]:
    bonuses = race_bonuses or {}
    result: Dict[str, int] = {}
    for stat in ("strength", "intelligence", "dexterity", "wisdom", "charisma", "constitution"):
        raw = rng.randint(base, base + spread) + bonuses.get(stat, 0)
        result[stat] = max(1, min(100, raw))
    return result

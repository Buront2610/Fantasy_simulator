"""
character.py - Core Character class for the Fantasy Simulator.
"""

from __future__ import annotations

import random
import uuid
from typing import Any, Dict, List, Optional


class Character:
    """Represents a living (or deceased) inhabitant of the world.

    Attributes
    ----------
    char_id : str
        Unique identifier (UUID4 hex).
    name : str
        Display name.
    age : int
        Current age in years.
    gender : str
        Gender identity string (e.g. "Male", "Female", "Non-binary").
    race : str
        Race name (e.g. "Human", "Elf").
    job : str
        Current job / class (e.g. "Warrior", "Mage").
    strength : int
        Physical power (1–100).
    intelligence : int
        Mental acuity (1–100).
    dexterity : int
        Speed and precision (1–100).
    wisdom : int
        Insight and magical attunement (1–100).
    charisma : int
        Charm and force of personality (1–100).
    constitution : int
        Endurance and toughness (1–100).
    skills : dict[str, int]
        Mapping of skill name → level (0–10).
    relationships : dict[str, int]
        Mapping of other character's ``char_id`` → relationship value (−100 to 100).
    alive : bool
        Whether the character is still living.
    location : str
        Name of the location where this character currently resides.
    history : list[str]
        Chronological list of notable events in this character's life.
    spouse_id : Optional[str]
        ``char_id`` of spouse, or ``None`` if unmarried.
    """

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

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
        location: str = "Aethoria Capital",
        history: Optional[List[str]] = None,
        char_id: Optional[str] = None,
        spouse_id: Optional[str] = None,
        injury_status: str = "none",
        active_adventure_id: Optional[str] = None,
    ) -> None:
        self.char_id: str = char_id or uuid.uuid4().hex[:8]
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
        self.location: str = location
        self.history: List[str] = history if history is not None else []
        self.spouse_id: Optional[str] = spouse_id
        self.injury_status: str = injury_status
        self.active_adventure_id: Optional[str] = active_adventure_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _clamp(value: int, lo: int = 1, hi: int = 100) -> int:
        """Clamp *value* to [lo, hi]."""
        return max(lo, min(hi, value))

    # ------------------------------------------------------------------
    # Stat helpers
    # ------------------------------------------------------------------

    @property
    def combat_power(self) -> int:
        """Rough combat effectiveness (used by EventSystem)."""
        return (self.strength * 2 + self.dexterity + self.constitution) // 4

    @property
    def max_age(self) -> int:
        """Expected maximum lifespan based on race."""
        lifespans = {
            "Human": 80, "Elf": 600, "Dwarf": 250, "Halfling": 130,
            "Orc": 60, "Tiefling": 100, "Dragonborn": 80,
        }
        return lifespans.get(self.race, 80)

    def apply_stat_delta(self, deltas: Dict[str, int]) -> None:
        """Apply a dictionary of stat changes, clamping to valid range."""
        stat_names = {"strength", "intelligence", "dexterity", "wisdom", "charisma", "constitution"}
        for stat, delta in deltas.items():
            if stat in stat_names:
                current = getattr(self, stat)
                setattr(self, stat, self._clamp(current + delta))

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def level_up_skill(self, skill_name: str, amount: int = 1) -> str:
        """Increase *skill_name* by *amount* levels (capped at 10).

        Returns a human-readable description of the change.
        """
        current = self.skills.get(skill_name, 0)
        new_level = min(10, current + amount)
        self.skills[skill_name] = new_level
        if new_level > current:
            return f"{self.name} improved {skill_name} to level {new_level}."
        return f"{self.name}'s {skill_name} is already at max level."

    def update_relationship(self, other_id: str, delta: int) -> None:
        """Adjust the relationship value toward *other_id* by *delta*.

        Clamped to [−100, 100].
        """
        current = self.relationships.get(other_id, 0)
        self.relationships[other_id] = max(-100, min(100, current + delta))

    def add_history(self, event: str) -> None:
        """Append an event string to this character's life history."""
        self.history.append(event)

    def get_relationship(self, other_id: str) -> int:
        """Return relationship value toward *other_id* (default 0)."""
        return self.relationships.get(other_id, 0)

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise character to a plain dict (JSON-compatible)."""
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
            "location": self.location,
            "history": self.history,
            "spouse_id": self.spouse_id,
            "injury_status": self.injury_status,
            "active_adventure_id": self.active_adventure_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Character":
        """Deserialise a character from a plain dict."""
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
            skills=data.get("skills", {}),
            relationships=data.get("relationships", {}),
            alive=data.get("alive", True),
            location=data.get("location", "Aethoria Capital"),
            history=data.get("history", []),
            char_id=data.get("char_id"),
            spouse_id=data.get("spouse_id"),
            injury_status=data.get("injury_status", "none"),
            active_adventure_id=data.get("active_adventure_id"),
        )

    # ------------------------------------------------------------------
    # Representation
    # ------------------------------------------------------------------

    def __repr__(self) -> str:  # pragma: no cover
        status = "alive" if self.alive else "deceased"
        return (
            f"Character(name={self.name!r}, race={self.race!r}, "
            f"job={self.job!r}, age={self.age}, status={status})"
        )

    def stat_block(self) -> str:
        """Return a compact, human-readable stat summary."""
        lines = [
            f"  Name       : {self.name}",
            f"  Race/Job   : {self.race} {self.job}",
            f"  Age        : {self.age}  |  Gender: {self.gender}",
            f"  Location   : {self.location}",
            f"  Status     : {'Alive' if self.alive else 'Deceased'}",
            "  ─── Stats ─────────────────────────────",
            f"  STR {self.strength:>3}  |  INT {self.intelligence:>3}  |  DEX {self.dexterity:>3}",
            f"  WIS {self.wisdom:>3}  |  CHA {self.charisma:>3}  |  CON {self.constitution:>3}",
        ]
        if self.skills:
            top_skills = sorted(self.skills.items(), key=lambda x: -x[1])[:5]
            skill_str = "  |  ".join(f"{k}(Lv{v})" for k, v in top_skills)
            lines.append(f"  ─── Top Skills ─────────────────────────")
            lines.append(f"  {skill_str}")
        if self.injury_status != "none":
            lines.append(f"  Injury     : {self.injury_status}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Factory helper (used by CharacterCreator)
# ---------------------------------------------------------------------------

def random_stats(
    base: int = 30,
    spread: int = 40,
    race_bonuses: Optional[Dict[str, int]] = None,
) -> Dict[str, int]:
    """Generate a random stat block.

    Each stat is uniformly sampled from [base, base+spread] then the
    race bonus is applied and the result is clamped to [1, 100].
    """
    bonuses = race_bonuses or {}
    result: Dict[str, int] = {}
    for stat in ("strength", "intelligence", "dexterity", "wisdom", "charisma", "constitution"):
        raw = random.randint(base, base + spread) + bonuses.get(stat, 0)
        result[stat] = max(1, min(100, raw))
    return result

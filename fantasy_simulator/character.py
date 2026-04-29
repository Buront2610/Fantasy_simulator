"""
character.py - Core Character class for the Fantasy Simulator.
"""

from __future__ import annotations

import random
import uuid
from typing import Any, Callable, Dict, List, Optional

from .character_domain import (
    CharacterAbilities,
    CharacterNarrativeState,
    Relationship,
    VALID_INJURY_STATUSES,
    build_relationship_details,
    clamp_relationship_score,
    clamp_skill_level,
)
from .character_presentation import character_stat_block, random_stats as roll_random_stats
from .character_serialization import deserialize_character, serialize_character
from .content.world_data import NAME_TO_LOCATION_ID, fallback_location_id
from .i18n import tr


class Character:
    """Represents a living (or deceased) inhabitant of the world."""

    VALID_INJURY_STATUSES = VALID_INJURY_STATUSES

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
        location_id: str = "",
        favorite: bool = False,
        spotlighted: bool = False,
        playable: bool = False,
        history: Optional[List[str]] = None,
        char_id: Optional[str] = None,
        spouse_id: Optional[str] = None,
        injury_status: str = "none",
        active_adventure_id: Optional[str] = None,
        relation_tags: Optional[Dict[str, List[str]]] = None,
        relation_tag_sources: Optional[Dict[str, List[str]]] = None,
        rng: Any = None,
    ) -> None:
        if char_id:
            self.char_id: str = char_id
        elif rng is not None:
            self.char_id = format(rng.getrandbits(32), "08x")
        else:
            self.char_id = uuid.uuid4().hex[:8]

        self.name = name
        self.age = age
        self.gender = gender
        self.race = race
        self.job = job

        self._abilities = CharacterAbilities(
            strength=strength,
            intelligence=intelligence,
            dexterity=dexterity,
            wisdom=wisdom,
            charisma=charisma,
            constitution=constitution,
        )

        self.skills: Dict[str, int] = {
            skill: clamp_skill_level(level)
            for skill, level in (skills or {}).items()
        }
        self.relationships: Dict[str, int] = {
            target_id: clamp_relationship_score(score)
            for target_id, score in (relationships or {}).items()
        }
        self.alive = alive
        self.location_id = location_id
        self.favorite = favorite
        self.spotlighted = spotlighted
        self.playable = playable
        self.history: List[str] = list(history or [])
        self.spouse_id = spouse_id
        self.injury_status = injury_status if injury_status in self.VALID_INJURY_STATUSES else "none"
        self.active_adventure_id = active_adventure_id
        self.relation_tags: Dict[str, List[str]] = {
            target_id: list(tags)
            for target_id, tags in (relation_tags or {}).items()
        }
        self.relation_tag_sources: Dict[str, List[str]] = {
            key: list(values)
            for key, values in (relation_tag_sources or {}).items()
        }

    @staticmethod
    def _clamp(value: int, lo: int = 1, hi: int = 100) -> int:
        return max(lo, min(hi, int(value)))

    @property
    def abilities(self) -> CharacterAbilities:
        return CharacterAbilities(
            strength=self.strength,
            intelligence=self.intelligence,
            dexterity=self.dexterity,
            wisdom=self.wisdom,
            charisma=self.charisma,
            constitution=self.constitution,
        )

    @property
    def narrative_state(self) -> CharacterNarrativeState:
        return CharacterNarrativeState(
            favorite=self.favorite,
            spotlighted=self.spotlighted,
            playable=self.playable,
            history=list(self.history),
            spouse_id=self.spouse_id,
            injury_status=self.injury_status,
            active_adventure_id=self.active_adventure_id,
        )

    @property
    def relationship_details(self) -> Dict[str, Relationship]:
        return build_relationship_details(
            self.relationships,
            self.relation_tags,
            self.relation_tag_sources,
        )

    def get_relationship_state(self, other_id: str) -> Relationship:
        return self.relationship_details.get(other_id, Relationship(target_id=other_id))

    @property
    def strength(self) -> int:
        return self._abilities.strength

    @strength.setter
    def strength(self, value: int) -> None:
        self._abilities = CharacterAbilities(**{**self._abilities.to_dict(), "strength": value})

    @property
    def intelligence(self) -> int:
        return self._abilities.intelligence

    @intelligence.setter
    def intelligence(self, value: int) -> None:
        self._abilities = CharacterAbilities(**{**self._abilities.to_dict(), "intelligence": value})

    @property
    def dexterity(self) -> int:
        return self._abilities.dexterity

    @dexterity.setter
    def dexterity(self, value: int) -> None:
        self._abilities = CharacterAbilities(**{**self._abilities.to_dict(), "dexterity": value})

    @property
    def wisdom(self) -> int:
        return self._abilities.wisdom

    @wisdom.setter
    def wisdom(self, value: int) -> None:
        self._abilities = CharacterAbilities(**{**self._abilities.to_dict(), "wisdom": value})

    @property
    def charisma(self) -> int:
        return self._abilities.charisma

    @charisma.setter
    def charisma(self, value: int) -> None:
        self._abilities = CharacterAbilities(**{**self._abilities.to_dict(), "charisma": value})

    @property
    def constitution(self) -> int:
        return self._abilities.constitution

    @constitution.setter
    def constitution(self, value: int) -> None:
        self._abilities = CharacterAbilities(**{**self._abilities.to_dict(), "constitution": value})

    @property
    def combat_power(self) -> int:
        return self.abilities.combat_power

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
        self._abilities = self._abilities.apply_delta(deltas)

    def level_up_skill(self, skill_name: str, amount: int = 1) -> str:
        current = self.skills.get(skill_name, 0)
        new_level = clamp_skill_level(current + amount)
        self.skills[skill_name] = new_level
        if new_level > current:
            return tr("skill_improved", name=self.name, skill=skill_name, level=new_level)
        return tr("skill_already_max", name=self.name, skill=skill_name)

    @property
    def is_dying(self) -> bool:
        return self.alive and self.injury_status == "dying"

    def worsen_injury(self) -> str:
        progression = {"none": "injured", "injured": "serious", "serious": "dying"}
        self.injury_status = progression.get(self.injury_status, self.injury_status)
        return self.injury_status

    def add_relation_tag(self, other_id: str, tag: str, source_event_id: Optional[str] = None) -> None:
        tags = self.relation_tags.setdefault(other_id, [])
        if tag not in tags:
            tags.append(tag)
        if source_event_id:
            key = f"{other_id}:{tag}"
            sources = self.relation_tag_sources.setdefault(key, [])
            if source_event_id not in sources:
                sources.append(source_event_id)

    def has_relation_tag(self, other_id: str, tag: str) -> bool:
        return tag in self.relation_tags.get(other_id, [])

    def get_relation_tags(self, other_id: str) -> List[str]:
        return list(self.relation_tags.get(other_id, []))

    def update_relationship(self, other_id: str, delta: int) -> None:
        current = self.relationships.get(other_id, 0)
        self.relationships[other_id] = clamp_relationship_score(current + delta)

    def update_mutual_relationship(self, other: "Character", delta: int, delta_other: Optional[int] = None) -> None:
        self.update_relationship(other.char_id, delta)
        other.update_relationship(self.char_id, delta_other if delta_other is not None else delta)

    def add_history(self, event: str) -> None:
        self.history.append(event)

    def get_relationship(self, other_id: str) -> int:
        return self.relationships.get(other_id, 0)

    @property
    def location_display_name(self) -> str:
        lid = self.location_id
        if not lid:
            return ""
        if lid.startswith("loc_"):
            lid = lid[4:]
        return lid.replace("_", " ").title()

    def to_dict(self) -> Dict[str, Any]:
        return serialize_character(self)

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        *,
        location_resolver: Callable[[str], str] | None = None,
    ) -> "Character":
        def legacy_location_resolver(old_name: str) -> str:
            return NAME_TO_LOCATION_ID.get(old_name, fallback_location_id(old_name))

        return deserialize_character(
            cls,
            data,
            location_resolver=location_resolver,
            legacy_location_resolver=legacy_location_resolver,
        )

    def __repr__(self) -> str:  # pragma: no cover
        status = "alive" if self.alive else "deceased"
        return (
            f"Character(name={self.name!r}, race={self.race!r}, "
            f"job={self.job!r}, age={self.age}, status={status})"
        )

    def stat_block(
        self,
        char_name_lookup: Optional[Dict[str, str]] = None,
        location_resolver: Callable[[str], str] | None = None,
    ) -> str:
        return character_stat_block(
            self,
            char_name_lookup=char_name_lookup,
            location_resolver=location_resolver,
        )


def random_stats(
    base: int = 30,
    spread: int = 40,
    race_bonuses: Optional[Dict[str, int]] = None,
    rng: Any = random,
) -> Dict[str, int]:
    return roll_random_stats(base=base, spread=spread, race_bonuses=race_bonuses, rng=rng)

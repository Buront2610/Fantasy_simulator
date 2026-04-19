"""Value objects and serializers for the Character domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional


STAT_NAMES: tuple[str, ...] = (
    "strength",
    "intelligence",
    "dexterity",
    "wisdom",
    "charisma",
    "constitution",
)
VALID_INJURY_STATUSES: tuple[str, ...] = ("none", "injured", "serious", "dying")


def clamp_stat(value: int, lo: int = 1, hi: int = 100) -> int:
    return max(lo, min(hi, int(value)))


def clamp_skill_level(value: int) -> int:
    return max(0, min(10, int(value)))


def clamp_relationship_score(value: int) -> int:
    return max(-100, min(100, int(value)))


@dataclass(frozen=True)
class CharacterAbilities:
    strength: int = 10
    intelligence: int = 10
    dexterity: int = 10
    wisdom: int = 10
    charisma: int = 10
    constitution: int = 10

    def __post_init__(self) -> None:
        for stat_name in STAT_NAMES:
            object.__setattr__(self, stat_name, clamp_stat(getattr(self, stat_name)))

    @property
    def combat_power(self) -> int:
        return (self.strength * 2 + self.dexterity + self.constitution) // 4

    def apply_delta(self, deltas: Mapping[str, int]) -> "CharacterAbilities":
        updated = self.to_dict()
        for stat_name, delta in deltas.items():
            if stat_name in updated:
                updated[stat_name] = clamp_stat(updated[stat_name] + delta)
        return CharacterAbilities(**updated)

    def to_dict(self) -> Dict[str, int]:
        return {stat_name: getattr(self, stat_name) for stat_name in STAT_NAMES}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CharacterAbilities":
        return cls(
            strength=data.get("strength", 10),
            intelligence=data.get("intelligence", 10),
            dexterity=data.get("dexterity", 10),
            wisdom=data.get("wisdom", 10),
            charisma=data.get("charisma", 10),
            constitution=data.get("constitution", 10),
        )


@dataclass(frozen=True)
class CharacterNarrativeState:
    favorite: bool = False
    spotlighted: bool = False
    playable: bool = False
    history: List[str] = field(default_factory=list)
    spouse_id: Optional[str] = None
    injury_status: str = "none"
    active_adventure_id: Optional[str] = None

    def __post_init__(self) -> None:
        history = [str(entry) for entry in self.history]
        object.__setattr__(self, "history", history)
        injury_status = self.injury_status if self.injury_status in VALID_INJURY_STATUSES else "none"
        object.__setattr__(self, "injury_status", injury_status)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "favorite": self.favorite,
            "spotlighted": self.spotlighted,
            "playable": self.playable,
            "history": list(self.history),
            "spouse_id": self.spouse_id,
            "injury_status": self.injury_status,
            "active_adventure_id": self.active_adventure_id,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CharacterNarrativeState":
        return cls(
            favorite=bool(data.get("favorite", False)),
            spotlighted=bool(data.get("spotlighted", False)),
            playable=bool(data.get("playable", False)),
            history=list(data.get("history", [])),
            spouse_id=data.get("spouse_id"),
            injury_status=data.get("injury_status", "none"),
            active_adventure_id=data.get("active_adventure_id"),
        )


@dataclass(frozen=True)
class Relationship:
    target_id: str
    score: int = 0
    tags: List[str] = field(default_factory=list)
    tag_sources: Dict[str, List[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        score = clamp_relationship_score(self.score)
        object.__setattr__(self, "score", score)
        unique_tags: List[str] = []
        normalized_sources: Dict[str, List[str]] = {}
        for tag in self.tags:
            tag_text = str(tag)
            if tag_text not in unique_tags:
                unique_tags.append(tag_text)
        for tag_name, source_ids in self.tag_sources.items():
            normalized_sources[str(tag_name)] = _unique_strings(source_ids)
        object.__setattr__(self, "tags", unique_tags)
        object.__setattr__(self, "tag_sources", normalized_sources)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "score": self.score,
            "tags": list(self.tags),
            "tag_sources": {tag: list(source_ids) for tag, source_ids in self.tag_sources.items()},
        }

    @classmethod
    def from_dict(cls, target_id: str, data: Mapping[str, Any]) -> "Relationship":
        return cls(
            target_id=target_id,
            score=data.get("score", 0),
            tags=list(data.get("tags", [])),
            tag_sources={
                str(tag): _unique_strings(source_ids)
                for tag, source_ids in data.get("tag_sources", {}).items()
            },
        )

    @classmethod
    def from_legacy(
        cls,
        target_id: str,
        *,
        score: int = 0,
        tags: Optional[Iterable[str]] = None,
        relation_tag_sources: Optional[Mapping[str, List[str]]] = None,
    ) -> "Relationship":
        source_map: Dict[str, List[str]] = {}
        raw_sources = relation_tag_sources or {}
        tag_list = _unique_strings(tags or [])
        for tag in tag_list:
            legacy_key = f"{target_id}:{tag}"
            source_map[tag] = _unique_strings(raw_sources.get(legacy_key, []))
        return cls(target_id=target_id, score=score, tags=tag_list, tag_sources=source_map)

    def with_score_delta(self, delta: int) -> "Relationship":
        return Relationship(
            target_id=self.target_id,
            score=clamp_relationship_score(self.score + delta),
            tags=list(self.tags),
            tag_sources={tag: list(source_ids) for tag, source_ids in self.tag_sources.items()},
        )

    def with_added_tag(self, tag: str, source_event_id: Optional[str] = None) -> "Relationship":
        tags = list(self.tags)
        if tag not in tags:
            tags.append(tag)
        tag_sources = {tag_name: list(source_ids) for tag_name, source_ids in self.tag_sources.items()}
        if source_event_id is not None:
            existing = tag_sources.setdefault(tag, [])
            if source_event_id not in existing:
                existing.append(source_event_id)
        return Relationship(
            target_id=self.target_id,
            score=self.score,
            tags=tags,
            tag_sources=tag_sources,
        )


def build_relationship_details(
    relationships: Mapping[str, int],
    relation_tags: Mapping[str, List[str]],
    relation_tag_sources: Mapping[str, List[str]],
) -> Dict[str, Relationship]:
    target_ids = set(relationships) | set(relation_tags)
    details: Dict[str, Relationship] = {}
    for target_id in target_ids:
        details[target_id] = Relationship.from_legacy(
            target_id,
            score=relationships.get(target_id, 0),
            tags=relation_tags.get(target_id, []),
            relation_tag_sources=relation_tag_sources,
        )
    return details


def flatten_relationship_details(
    details: Mapping[str, Relationship],
) -> Dict[str, Dict[str, Any]]:
    return {target_id: relationship.to_dict() for target_id, relationship in details.items()}


def expand_relationship_details(
    payload: Mapping[str, Any],
) -> tuple[Dict[str, int], Dict[str, List[str]], Dict[str, List[str]]]:
    relationships: Dict[str, int] = {}
    relation_tags: Dict[str, List[str]] = {}
    relation_tag_sources: Dict[str, List[str]] = {}
    for target_id, raw_data in payload.items():
        relationship = Relationship.from_dict(target_id, raw_data)
        if relationship.score != 0:
            relationships[target_id] = relationship.score
        if relationship.tags:
            relation_tags[target_id] = list(relationship.tags)
        for tag_name, source_ids in relationship.tag_sources.items():
            if source_ids:
                relation_tag_sources[f"{target_id}:{tag_name}"] = list(source_ids)
    return relationships, relation_tags, relation_tag_sources


def _unique_strings(values: Iterable[Any]) -> List[str]:
    result: List[str] = []
    for value in values:
        text = str(value)
        if text not in result:
            result.append(text)
    return result

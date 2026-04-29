"""Serialization helpers for ``Character``."""

from __future__ import annotations

from typing import Any, Callable, Dict

from .character_domain import (
    clamp_relationship_score,
    clamp_skill_level,
    expand_relationship_details,
)


def serialize_character(character: Any) -> Dict[str, Any]:
    abilities_payload = character.abilities.to_dict()
    narrative_payload = character.narrative_state.to_dict()
    relationship_payload = {
        target_id: detail.to_dict()
        for target_id, detail in character.relationship_details.items()
    }
    return {
        "char_id": character.char_id,
        "name": character.name,
        "age": character.age,
        "gender": character.gender,
        "race": character.race,
        "job": character.job,
        **abilities_payload,
        "abilities": abilities_payload,
        "skills": dict(character.skills),
        "relationships": dict(character.relationships),
        "relationship_details": relationship_payload,
        "alive": character.alive,
        "location_id": character.location_id,
        **narrative_payload,
        "narrative_state": narrative_payload,
        "relation_tags": {k: list(v) for k, v in character.relation_tags.items()},
        "relation_tag_sources": {k: list(v) for k, v in character.relation_tag_sources.items()},
    }


def deserialize_character(
    character_cls: Any,
    data: Dict[str, Any],
    *,
    location_resolver: Callable[[str], str] | None = None,
    legacy_location_resolver: Callable[[str], str] | None = None,
) -> Any:
    ability_payload = data.get("abilities", {})
    narrative_payload = data.get("narrative_state", {})
    skills = {
        k: clamp_skill_level(v)
        for k, v in data.get("skills", {}).items()
    }
    relationships = {
        k: clamp_relationship_score(v)
        for k, v in data.get("relationships", {}).items()
    }
    relation_tags = {
        k: list(v) for k, v in data.get("relation_tags", {}).items()
    }
    relation_tag_sources = {
        k: list(v) for k, v in data.get("relation_tag_sources", {}).items()
    }
    if data.get("relationship_details"):
        relationships, relation_tags, relation_tag_sources = expand_relationship_details(
            data["relationship_details"]
        )

    location_id = data.get("location_id")
    if location_id is None:
        old_name = data.get("location", "Aethoria Capital")
        if location_resolver is not None:
            location_id = location_resolver(old_name)
        elif legacy_location_resolver is not None:
            location_id = legacy_location_resolver(old_name)
        else:
            location_id = old_name

    return character_cls(
        name=data["name"],
        age=data["age"],
        gender=data["gender"],
        race=data["race"],
        job=data["job"],
        strength=ability_payload.get("strength", data.get("strength", 10)),
        intelligence=ability_payload.get("intelligence", data.get("intelligence", 10)),
        dexterity=ability_payload.get("dexterity", data.get("dexterity", 10)),
        wisdom=ability_payload.get("wisdom", data.get("wisdom", 10)),
        charisma=ability_payload.get("charisma", data.get("charisma", 10)),
        constitution=ability_payload.get("constitution", data.get("constitution", 10)),
        skills=skills,
        relationships=relationships,
        alive=data.get("alive", True),
        location_id=location_id,
        favorite=narrative_payload.get("favorite", data.get("favorite", False)),
        spotlighted=narrative_payload.get("spotlighted", data.get("spotlighted", False)),
        playable=narrative_payload.get("playable", data.get("playable", False)),
        history=narrative_payload.get("history", data.get("history", [])),
        char_id=data.get("char_id"),
        spouse_id=narrative_payload.get("spouse_id", data.get("spouse_id")),
        injury_status=narrative_payload.get("injury_status", data.get("injury_status", "none")),
        active_adventure_id=narrative_payload.get(
            "active_adventure_id",
            data.get("active_adventure_id"),
        ),
        relation_tags=relation_tags,
        relation_tag_sources=relation_tag_sources,
    )

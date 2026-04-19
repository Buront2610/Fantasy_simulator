"""Static schema types for the language subsystem."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List


VALID_SOUND_CHANGE_POSITIONS = {"any", "initial", "medial", "final"}
VALID_SOUND_CHANGE_CONTEXTS = {
    "",
    "any",
    "boundary",
    "vowel",
    "front_vowel",
    "back_vowel",
    "consonant",
    "liquid",
    "nasal",
    "stop",
    "fricative",
}


def _string_list_payload(payload: Any, *, field_name: str) -> List[str]:
    if payload is None:
        return []
    if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
        raise ValueError(f"{field_name} must be a list of strings")
    return list(payload)


@dataclass(frozen=True)
class SoundChangeRuleDefinition:
    """A structured sound change with simple environment constraints."""

    rule_key: str
    source: str
    target: str
    before: str = ""
    after: str = ""
    position: str = "any"
    description: str = ""
    weight: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rule_key": self.rule_key,
            "source": self.source,
            "target": self.target,
            "before": self.before,
            "after": self.after,
            "position": self.position,
            "description": self.description,
            "weight": int(self.weight),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SoundChangeRuleDefinition":
        return cls(
            rule_key=str(data.get("rule_key", "")),
            source=str(data.get("source", "")),
            target=str(data.get("target", "")),
            before=str(data.get("before", "")),
            after=str(data.get("after", "")),
            position=str(data.get("position", "any")),
            description=str(data.get("description", "")),
            weight=max(1, int(data.get("weight", 1))),
        )


def sound_change_rules_from_payload(payload: Any, *, field_name: str) -> List[SoundChangeRuleDefinition]:
    if payload is None:
        return []
    if not isinstance(payload, list):
        raise ValueError(f"{field_name} must be a list")
    return [
        SoundChangeRuleDefinition.from_dict(dict(item))
        for item in payload
    ]

"""Runtime language state and evolution records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from .schema import SoundChangeRuleDefinition, sound_change_rules_from_payload


def _string_list_payload(payload: Any, *, field_name: str) -> List[str]:
    if payload is None:
        return []
    if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
        raise ValueError(f"{field_name} must be a list of strings")
    return list(payload)


@dataclass
class LanguageEvolutionRecord:
    """A deterministic language innovation applied at a specific year."""

    year: int
    language_key: str
    source_token: str = ""
    target_token: str = ""
    added_name_stem: str = ""
    added_toponym_suffix: str = ""
    rule_key: str = ""
    rule_before: str = ""
    rule_after: str = ""
    rule_position: str = "any"
    rule_description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "year": self.year,
            "language_key": self.language_key,
            "source_token": self.source_token,
            "target_token": self.target_token,
            "added_name_stem": self.added_name_stem,
            "added_toponym_suffix": self.added_toponym_suffix,
            "rule_key": self.rule_key,
            "rule_before": self.rule_before,
            "rule_after": self.rule_after,
            "rule_position": self.rule_position,
            "rule_description": self.rule_description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LanguageEvolutionRecord":
        return cls(
            year=int(data.get("year", 0)),
            language_key=str(data.get("language_key", "")),
            source_token=str(data.get("source_token", "")),
            target_token=str(data.get("target_token", "")),
            added_name_stem=str(data.get("added_name_stem", "")),
            added_toponym_suffix=str(data.get("added_toponym_suffix", "")),
            rule_key=str(data.get("rule_key", "")),
            rule_before=str(data.get("rule_before", "")),
            rule_after=str(data.get("rule_after", "")),
            rule_position=str(data.get("rule_position", "any")),
            rule_description=str(data.get("rule_description", "")),
        )

    def to_rule_definition(self) -> SoundChangeRuleDefinition | None:
        if not self.source_token:
            return None
        key = self.rule_key or f"runtime:{self.language_key}:{self.year}:{self.source_token}>{self.target_token}"
        return SoundChangeRuleDefinition(
            rule_key=key,
            source=self.source_token,
            target=self.target_token,
            before=self.rule_before,
            after=self.rule_after,
            position=self.rule_position,
            description=self.rule_description,
        )


@dataclass
class LanguageRuntimeState:
    """Mutable simulation state layered on top of static language specs."""

    language_key: str
    applied_rules: List[SoundChangeRuleDefinition] = field(default_factory=list)
    derived_name_stems: List[str] = field(default_factory=list)
    derived_toponym_suffixes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "language_key": self.language_key,
            "applied_rules": [rule.to_dict() for rule in self.applied_rules],
            "derived_name_stems": list(self.derived_name_stems),
            "derived_toponym_suffixes": list(self.derived_toponym_suffixes),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LanguageRuntimeState":
        return cls(
            language_key=str(data.get("language_key", "")),
            applied_rules=sound_change_rules_from_payload(
                data.get("applied_rules", []),
                field_name="language_runtime_state.applied_rules",
            ),
            derived_name_stems=_string_list_payload(
                data.get("derived_name_stems", []),
                field_name="language_runtime_state.derived_name_stems",
            ),
            derived_toponym_suffixes=_string_list_payload(
                data.get("derived_toponym_suffixes", []),
                field_name="language_runtime_state.derived_toponym_suffixes",
            ),
        )

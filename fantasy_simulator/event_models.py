"""Canonical event data models and ID generation helpers.

This module isolates pure data contracts (DbC-friendly) from event-generation
side effects implemented in ``events.py``.

Contract policy:
- structural requirements may fail fast (e.g. missing required keys)
- value ranges are normalized for persistence compatibility
  (month/day are lower-bound normalized only in this model layer)
- ``to_dict`` / ``from_dict`` defensively copy mutable nested payloads
"""

from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from math import isfinite
from typing import Any, Dict, List, Optional, Protocol


class SupportsGetRandBits(Protocol):
    def getrandbits(self, k: int) -> int: ...


def generate_record_id(rng: Optional[SupportsGetRandBits] = None) -> str:
    """Generate a stable-width hex record ID.

    Contract:
    - Returns lowercase 32-char hex string.
    - Uses injected RNG when available for deterministic tests.
    """
    if rng is not None and hasattr(rng, "getrandbits"):
        return format(rng.getrandbits(128), "032x")
    return uuid.uuid4().hex


@dataclass(slots=True)
class EventResult:
    """The outcome of a single in-world event."""

    description: str
    affected_characters: List[str] = field(default_factory=list)
    stat_changes: Dict[str, Dict[str, int]] = field(default_factory=dict)
    event_type: str = "generic"
    summary_key: str = ""
    year: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "description": self.description,
            "affected_characters": list(self.affected_characters),
            "stat_changes": deepcopy(self.stat_changes),
            "event_type": self.event_type,
            "year": self.year,
            "metadata": deepcopy(self.metadata),
        }
        if self.summary_key:
            payload["summary_key"] = self.summary_key
        return payload

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventResult":
        return cls(
            description=data["description"],
            affected_characters=list(data.get("affected_characters", [])),
            stat_changes=deepcopy(data.get("stat_changes", {})),
            event_type=data.get("event_type", "generic"),
            summary_key=data.get("summary_key", ""),
            year=data.get("year", 0),
            metadata=deepcopy(data.get("metadata", {})),
        )


@dataclass(slots=True)
class WorldEventRecord:
    """A structured record of a world event for history and analysis."""

    record_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    kind: str = "generic"
    year: int = 0
    month: int = 1
    day: int = 1
    absolute_day: int = 0
    location_id: Optional[str] = None
    primary_actor_id: Optional[str] = None
    secondary_actor_ids: List[str] = field(default_factory=list)
    description: str = ""
    severity: int = 1
    visibility: str = "public"
    calendar_key: str = ""
    summary_key: str = ""
    render_params: Dict[str, Any] = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)
    impacts: List[Dict[str, Any]] = field(default_factory=list)
    legacy_event_result: Optional[Dict[str, Any]] = None
    legacy_event_log_entry: Optional[str] = None

    def __post_init__(self) -> None:
        # Contract checks / normalization for persistence compatibility.
        self.record_id = self._validate_string_payload(self.record_id, "record_id")
        self.kind = self._validate_string_payload(self.kind, "kind")
        self.year = self._validate_int_payload(self.year, "year")
        self.month = max(1, self._validate_int_payload(self.month, "month"))
        self.day = max(1, self._validate_int_payload(self.day, "day"))
        self.absolute_day = max(0, self._validate_int_payload(self.absolute_day, "absolute_day"))
        self.location_id = self._validate_optional_string_payload(self.location_id, "location_id")
        self.primary_actor_id = self._validate_optional_string_payload(self.primary_actor_id, "primary_actor_id")
        self.secondary_actor_ids = self._validate_string_list_payload(
            self.secondary_actor_ids,
            "secondary_actor_ids",
        )
        self.description = self._validate_string_payload(self.description, "description")
        self.severity = max(1, min(5, self._validate_int_payload(self.severity, "severity")))
        self.visibility = self._validate_string_payload(self.visibility, "visibility")
        self.calendar_key = self._validate_string_payload(self.calendar_key, "calendar_key")
        self.summary_key = self._validate_summary_key(self.summary_key)
        self.render_params = self._validate_render_params_payload(self.render_params)
        self.tags = self._validate_string_list_payload(self.tags, "tags")
        self.impacts = self._validate_impacts_payload(self.impacts)
        self.legacy_event_result = self._validate_legacy_event_result_payload(self.legacy_event_result)
        self.legacy_event_log_entry = self._validate_legacy_event_log_entry_payload(self.legacy_event_log_entry)

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "record_id": self.record_id,
            "kind": self.kind,
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "absolute_day": self.absolute_day,
            "location_id": self.location_id,
            "primary_actor_id": self.primary_actor_id,
            "secondary_actor_ids": list(self.secondary_actor_ids),
            "description": self.description,
            "severity": self.severity,
            "visibility": self.visibility,
            "calendar_key": self.calendar_key,
            "summary_key": self.summary_key,
        }
        if self.render_params:
            payload["render_params"] = deepcopy(self.render_params)
        payload["tags"] = list(self.tags)
        payload["impacts"] = deepcopy(self.impacts)
        if self.legacy_event_result is not None:
            payload["legacy_event_result"] = deepcopy(self.legacy_event_result)
        if self.legacy_event_log_entry is not None:
            payload["legacy_event_log_entry"] = self.legacy_event_log_entry
        return payload

    @staticmethod
    def _validate_legacy_event_result_payload(payload: Any) -> Optional[Dict[str, Any]]:
        if payload is None:
            return None
        if not isinstance(payload, dict):
            raise ValueError("legacy_event_result must be a dict when provided")
        raw_affected_characters = payload.get("affected_characters", [])
        if not isinstance(raw_affected_characters, list) or any(
            not isinstance(character_id, str) for character_id in raw_affected_characters
        ):
            raise ValueError("legacy_event_result.affected_characters must be a list of strings")
        try:
            projected = EventResult.from_dict(payload)
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise ValueError("legacy_event_result must be a valid EventResult payload") from exc
        if not isinstance(projected.description, str):
            raise ValueError("legacy_event_result.description must be a string")
        if not isinstance(projected.stat_changes, dict):
            raise ValueError("legacy_event_result.stat_changes must be a dict")
        for character_id, stat_changes in projected.stat_changes.items():
            if not isinstance(character_id, str):
                raise ValueError("legacy_event_result.stat_changes keys must be strings")
            if not isinstance(stat_changes, dict):
                raise ValueError("legacy_event_result.stat_changes values must be dicts")
            for stat_name, delta in stat_changes.items():
                if not isinstance(stat_name, str):
                    raise ValueError("legacy_event_result.stat names must be strings")
                if not isinstance(delta, int) or isinstance(delta, bool):
                    raise ValueError("legacy_event_result stat deltas must be integers")
        if not isinstance(projected.event_type, str):
            raise ValueError("legacy_event_result.event_type must be a string")
        if not isinstance(projected.summary_key, str):
            raise ValueError("legacy_event_result.summary_key must be a string")
        if not isinstance(projected.year, int) or isinstance(projected.year, bool):
            raise ValueError("legacy_event_result.year must be an integer")
        if not isinstance(projected.metadata, dict):
            raise ValueError("legacy_event_result.metadata must be a dict")
        return projected.to_dict()

    @staticmethod
    def _validate_legacy_event_log_entry_payload(payload: Any) -> Optional[str]:
        if payload is None:
            return None
        if not isinstance(payload, str):
            raise ValueError("legacy_event_log_entry must be a string when provided")
        return payload

    @staticmethod
    def _validate_string_list_payload(payload: Any, field_name: str) -> List[str]:
        if payload is None:
            raise ValueError(f"{field_name} must be a list of strings when provided")
        if not isinstance(payload, list) or any(not isinstance(item, str) for item in payload):
            raise ValueError(f"{field_name} must be a list of strings")
        return list(payload)

    @staticmethod
    def _validate_string_payload(payload: Any, field_name: str) -> str:
        if not isinstance(payload, str):
            raise ValueError(f"{field_name} must be a string")
        return payload

    @staticmethod
    def _validate_summary_key(payload: str) -> str:
        if payload == "":
            return payload
        normalized = payload.strip()
        if normalized != payload:
            raise ValueError("summary_key must not have leading/trailing whitespace")
        if "." not in payload or " " in payload:
            raise ValueError("summary_key must be empty or use dotted-key format like 'events.some_key.summary'")
        return payload

    @staticmethod
    def _validate_optional_string_payload(payload: Any, field_name: str) -> Optional[str]:
        if payload is None:
            return None
        if not isinstance(payload, str):
            raise ValueError(f"{field_name} must be a string when provided")
        return payload

    @staticmethod
    def _validate_int_payload(payload: Any, field_name: str) -> int:
        if not isinstance(payload, int) or isinstance(payload, bool):
            raise ValueError(f"{field_name} must be an integer")
        return payload

    @staticmethod
    def _validate_impacts_payload(payload: Any) -> List[Dict[str, Any]]:
        if payload is None:
            raise ValueError("impacts must be a list of dicts when provided")
        if not isinstance(payload, list):
            raise ValueError("impacts must be a list of dicts")
        if any(not isinstance(item, dict) for item in payload):
            raise ValueError("impacts entries must be dicts")
        return deepcopy(payload)

    @staticmethod
    def _validate_render_params_payload(payload: Any) -> Dict[str, Any]:
        if payload is None:
            raise ValueError("render_params must be a dict when provided")
        if not isinstance(payload, dict):
            raise ValueError("render_params must be a dict")
        WorldEventRecord._validate_json_object_payload(payload, "render_params")
        return deepcopy(payload)

    @staticmethod
    def _validate_json_object_payload(payload: Any, field_name: str) -> None:
        if not isinstance(payload, dict):
            raise ValueError(f"{field_name} must be a dict")
        for key, value in payload.items():
            if not isinstance(key, str):
                raise ValueError(f"{field_name} keys must be strings")
            WorldEventRecord._validate_json_value_payload(value, f"{field_name}.{key}")

    @staticmethod
    def _validate_json_value_payload(value: Any, field_name: str) -> None:
        if value is None or isinstance(value, str) or isinstance(value, bool):
            return
        if isinstance(value, int):
            return
        if isinstance(value, float):
            if not isfinite(value):
                raise ValueError(f"{field_name} must be JSON-compatible")
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                WorldEventRecord._validate_json_value_payload(item, f"{field_name}[{index}]")
            return
        if isinstance(value, dict):
            WorldEventRecord._validate_json_object_payload(value, field_name)
            return
        raise ValueError(f"{field_name} must be JSON-compatible")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldEventRecord":
        return cls(
            record_id=cls._validate_string_payload(data.get("record_id", uuid.uuid4().hex), "record_id"),
            kind=cls._validate_string_payload(data.get("kind", "generic"), "kind"),
            year=cls._validate_int_payload(data.get("year", 0), "year"),
            month=cls._validate_int_payload(data.get("month", 1), "month"),
            day=cls._validate_int_payload(data.get("day", 1), "day"),
            absolute_day=cls._validate_int_payload(data.get("absolute_day", 0), "absolute_day"),
            location_id=cls._validate_optional_string_payload(data.get("location_id"), "location_id"),
            primary_actor_id=cls._validate_optional_string_payload(data.get("primary_actor_id"), "primary_actor_id"),
            secondary_actor_ids=cls._validate_string_list_payload(
                data.get("secondary_actor_ids", []),
                "secondary_actor_ids",
            ),
            description=cls._validate_string_payload(data.get("description", ""), "description"),
            severity=cls._validate_int_payload(data.get("severity", 1), "severity"),
            visibility=cls._validate_string_payload(data.get("visibility", "public"), "visibility"),
            calendar_key=cls._validate_string_payload(data.get("calendar_key", ""), "calendar_key"),
            summary_key=cls._validate_string_payload(data.get("summary_key", ""), "summary_key"),
            render_params=cls._validate_render_params_payload(data.get("render_params", {})),
            tags=cls._validate_string_list_payload(data.get("tags", []), "tags"),
            impacts=cls._validate_impacts_payload(data.get("impacts", [])),
            legacy_event_result=cls._validate_legacy_event_result_payload(data.get("legacy_event_result")),
            legacy_event_log_entry=cls._validate_legacy_event_log_entry_payload(data.get("legacy_event_log_entry")),
        )

    @classmethod
    def from_event_result(
        cls,
        result: EventResult,
        location_id: Optional[str] = None,
        severity: int = 1,
        record_id: Optional[str] = None,
        rng: Optional[SupportsGetRandBits] = None,
        month: int = 1,
        day: int = 1,
        absolute_day: int = 0,
        calendar_key: str = "",
        summary_key: str = "",
        render_params: Optional[Dict[str, Any]] = None,
    ) -> "WorldEventRecord":
        """Create a WorldEventRecord from an EventResult."""
        primary = result.affected_characters[0] if result.affected_characters else None
        secondary = result.affected_characters[1:] if len(result.affected_characters) > 1 else []
        legacy_event_result = None
        if result.stat_changes or result.metadata:
            legacy_event_result = result.to_dict()
        metadata_summary_key = result.metadata.get("summary_key", "")
        if not isinstance(metadata_summary_key, str):
            raise ValueError("summary_key must be a string when provided in metadata")
        resolved_summary_key = summary_key or result.summary_key or metadata_summary_key
        cls._validate_summary_key(resolved_summary_key)
        return cls(
            record_id=record_id or generate_record_id(rng),
            kind=result.event_type,
            year=result.year,
            month=month,
            day=day,
            absolute_day=absolute_day,
            location_id=location_id,
            primary_actor_id=primary,
            secondary_actor_ids=secondary,
            description=result.description,
            severity=severity,
            calendar_key=calendar_key,
            summary_key=resolved_summary_key,
            render_params=render_params or {},
            legacy_event_result=legacy_event_result,
        )

    def to_event_result(self) -> EventResult:
        """Project a legacy EventResult adapter from the canonical record."""
        affected_characters: List[str] = []
        if self.primary_actor_id is not None:
            affected_characters.append(self.primary_actor_id)
        affected_characters.extend(self.secondary_actor_ids)
        if self.legacy_event_result is not None:
            projected = EventResult.from_dict(self.legacy_event_result)
            projected.description = self.description
            projected.affected_characters = affected_characters
            projected.event_type = self.kind
            projected.summary_key = self.summary_key
            projected.year = self.year
            return projected
        return EventResult(
            description=self.description,
            affected_characters=affected_characters,
            event_type=self.kind,
            summary_key=self.summary_key,
            year=self.year,
        )

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


@dataclass
class EventResult:
    """The outcome of a single in-world event."""

    description: str
    affected_characters: List[str] = field(default_factory=list)
    stat_changes: Dict[str, Dict[str, int]] = field(default_factory=dict)
    event_type: str = "generic"
    year: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "affected_characters": list(self.affected_characters),
            "stat_changes": deepcopy(self.stat_changes),
            "event_type": self.event_type,
            "year": self.year,
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EventResult":
        return cls(
            description=data["description"],
            affected_characters=list(data.get("affected_characters", [])),
            stat_changes=deepcopy(data.get("stat_changes", {})),
            event_type=data.get("event_type", "generic"),
            year=data.get("year", 0),
            metadata=deepcopy(data.get("metadata", {})),
        )


@dataclass
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
    tags: List[str] = field(default_factory=list)
    impacts: List[Dict[str, Any]] = field(default_factory=list)
    legacy_event_result: Optional[Dict[str, Any]] = None
    legacy_event_log_entry: Optional[str] = None

    def __post_init__(self) -> None:
        # Contract checks / normalization for persistence compatibility.
        self.severity = max(1, min(5, int(self.severity)))
        self.month = max(1, int(self.month))
        self.day = max(1, int(self.day))
        self.absolute_day = max(0, int(self.absolute_day))

    def to_dict(self) -> Dict[str, Any]:
        return {
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
            "tags": list(self.tags),
            "impacts": deepcopy(self.impacts),
            "legacy_event_result": deepcopy(self.legacy_event_result) if self.legacy_event_result is not None else None,
            "legacy_event_log_entry": self.legacy_event_log_entry,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldEventRecord":
        return cls(
            record_id=data.get("record_id", uuid.uuid4().hex),
            kind=data.get("kind", "generic"),
            year=data.get("year", 0),
            month=data.get("month", 1),
            day=data.get("day", 1),
            absolute_day=data.get("absolute_day", 0),
            location_id=data.get("location_id"),
            primary_actor_id=data.get("primary_actor_id"),
            secondary_actor_ids=list(data.get("secondary_actor_ids", [])),
            description=data.get("description", ""),
            severity=data.get("severity", 1),
            visibility=data.get("visibility", "public"),
            calendar_key=data.get("calendar_key", ""),
            tags=list(data.get("tags", [])),
            impacts=deepcopy(data.get("impacts", [])),
            legacy_event_result=(
                deepcopy(data["legacy_event_result"])
                if data.get("legacy_event_result") is not None
                else None
            ),
            legacy_event_log_entry=data.get("legacy_event_log_entry"),
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
    ) -> "WorldEventRecord":
        """Create a WorldEventRecord from an EventResult."""
        primary = result.affected_characters[0] if result.affected_characters else None
        secondary = result.affected_characters[1:] if len(result.affected_characters) > 1 else []
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
            legacy_event_result=result.to_dict(),
        )

    def to_event_result(self) -> EventResult:
        """Project a legacy EventResult adapter from the canonical record."""
        if self.legacy_event_result is not None:
            return EventResult.from_dict(self.legacy_event_result)
        affected_characters: List[str] = []
        if self.primary_actor_id is not None:
            affected_characters.append(self.primary_actor_id)
        affected_characters.extend(self.secondary_actor_ids)
        return EventResult(
            description=self.description,
            affected_characters=affected_characters,
            event_type=self.kind,
            year=self.year,
        )

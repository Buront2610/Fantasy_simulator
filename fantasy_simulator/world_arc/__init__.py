"""Persistent long-running world-arc state."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(slots=True)
class WorldArc:
    """Serializable process state for long-running world events."""

    arc_id: str
    kind: str
    phase: str
    start_year: int
    start_month: int = 1
    start_day: int = 1
    last_year: int = 0
    last_month: int = 1
    last_day: int = 1
    cause_event_id: Optional[str] = None
    related_event_ids: List[str] = field(default_factory=list)
    location_ids: Tuple[str, ...] = ()
    participant_faction_ids: Tuple[str, ...] = ()
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.arc_id = self._require_string(self.arc_id, "arc_id")
        self.kind = self._require_string(self.kind, "kind")
        self.phase = self._require_string(self.phase, "phase")
        self.start_year = int(self.start_year)
        self.start_month = max(1, int(self.start_month))
        self.start_day = max(1, int(self.start_day))
        self.last_year = int(self.last_year or self.start_year)
        self.last_month = max(1, int(self.last_month))
        self.last_day = max(1, int(self.last_day))
        self.cause_event_id = self._optional_string(self.cause_event_id, "cause_event_id")
        self.related_event_ids = list(dict.fromkeys(
            self._string_list(self.related_event_ids, "related_event_ids")
        ))
        self.location_ids = tuple(dict.fromkeys(self._string_list(self.location_ids, "location_ids")))
        self.participant_faction_ids = tuple(dict.fromkeys(
            self._string_list(self.participant_faction_ids, "participant_faction_ids")
        ))
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dict")
        self.metadata = deepcopy(self.metadata)

    @property
    def is_active(self) -> bool:
        return self.phase not in {"ended", "resolved", "failed"}

    def touch(self, *, year: int, month: int, day: int, record_id: str) -> None:
        """Attach a record to this arc and update the last observed date."""
        self.last_year = int(year)
        self.last_month = max(1, int(month))
        self.last_day = max(1, int(day))
        if record_id not in self.related_event_ids:
            self.related_event_ids.append(record_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "arc_id": self.arc_id,
            "kind": self.kind,
            "phase": self.phase,
            "start_year": self.start_year,
            "start_month": self.start_month,
            "start_day": self.start_day,
            "last_year": self.last_year,
            "last_month": self.last_month,
            "last_day": self.last_day,
            "cause_event_id": self.cause_event_id,
            "related_event_ids": list(self.related_event_ids),
            "location_ids": list(self.location_ids),
            "participant_faction_ids": list(self.participant_faction_ids),
            "metadata": deepcopy(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldArc":
        if not isinstance(data, dict):
            raise ValueError("world arc payload must be a dict")
        start_year = data.get("start_year", 0)
        start_month = data.get("start_month", 1)
        start_day = data.get("start_day", 1)
        last_year = data.get("last_year", start_year if start_year is not None else 0)
        last_month = data.get("last_month", start_month if start_month is not None else 1)
        last_day = data.get("last_day", start_day if start_day is not None else 1)
        return cls(
            arc_id=cls._require_string(data.get("arc_id"), "arc_id"),
            kind=cls._require_string(data.get("kind"), "kind"),
            phase=cls._require_string(data.get("phase", "active"), "phase"),
            start_year=int(start_year if start_year is not None else 0),
            start_month=int(start_month if start_month is not None else 1),
            start_day=int(start_day if start_day is not None else 1),
            last_year=int(last_year if last_year is not None else 0),
            last_month=int(last_month if last_month is not None else 1),
            last_day=int(last_day if last_day is not None else 1),
            cause_event_id=cls._optional_string(data.get("cause_event_id"), "cause_event_id"),
            related_event_ids=cls._string_list(data.get("related_event_ids", []), "related_event_ids"),
            location_ids=tuple(cls._string_list(data.get("location_ids", []), "location_ids")),
            participant_faction_ids=tuple(cls._string_list(
                data.get("participant_faction_ids", []),
                "participant_faction_ids",
            )),
            metadata=deepcopy(data.get("metadata", {})),
        )

    @staticmethod
    def _require_string(value: Any, field_name: str) -> str:
        if not isinstance(value, str) or not value:
            raise ValueError(f"{field_name} must be a non-empty string")
        return value

    @staticmethod
    def _optional_string(value: Any, field_name: str) -> Optional[str]:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f"{field_name} must be a string when provided")
        return value

    @staticmethod
    def _string_list(value: Any, field_name: str) -> List[str]:
        if isinstance(value, tuple):
            value = list(value)
        if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
            raise ValueError(f"{field_name} must be a list of strings")
        return list(value)

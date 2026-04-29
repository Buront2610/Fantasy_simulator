"""Small persistent records owned by the world aggregate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from .content.setting_bundle import CalendarDefinition


@dataclass(slots=True)
class MemorialRecord:
    """A permanent memorial created when a character dies at a location."""

    memorial_id: str
    character_id: str
    character_name: str
    location_id: str
    year: int
    cause: str
    epitaph: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memorial_id": self.memorial_id,
            "character_id": self.character_id,
            "character_name": self.character_name,
            "location_id": self.location_id,
            "year": self.year,
            "cause": self.cause,
            "epitaph": self.epitaph,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemorialRecord":
        return cls(
            memorial_id=data["memorial_id"],
            character_id=data["character_id"],
            character_name=data["character_name"],
            location_id=data["location_id"],
            year=data["year"],
            cause=data["cause"],
            epitaph=data["epitaph"],
        )


@dataclass(slots=True)
class CalendarChangeRecord:
    """A dated calendar-definition transition for future world-timeline features."""

    year: int
    month: int
    day: int
    calendar: CalendarDefinition

    def to_dict(self) -> Dict[str, Any]:
        return {
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "calendar": self.calendar.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarChangeRecord":
        return cls(
            year=int(data.get("year", 0)),
            month=max(1, int(data.get("month", 1))),
            day=max(1, int(data.get("day", 1))),
            calendar=CalendarDefinition.from_dict(data.get("calendar", {})),
        )

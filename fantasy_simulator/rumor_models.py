"""Data models for world rumors."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .rumor_constants import RELIABILITY_LEVELS, RUMOR_MAX_AGE_MONTHS


@dataclass
class Rumor:
    """A piece of information circulating in the world.

    Rumors are derived from WorldEventRecord entries but may have
    degraded reliability depending on distance and time elapsed.
    """

    id: str = field(default_factory=lambda: f"rum_{uuid.uuid4().hex[:12]}")
    category: str = "event"
    source_location_id: Optional[str] = None
    target_subject: str = ""
    reliability: str = "plausible"
    spread_level: int = 1
    age_in_months: int = 0
    content_tags: List[str] = field(default_factory=list)
    description: str = ""
    source_event_id: Optional[str] = None
    year_created: int = 0
    month_created: int = 1
    created_absolute_day: int = 0
    created_calendar_key: str = ""

    def __post_init__(self) -> None:
        if self.reliability not in RELIABILITY_LEVELS:
            self.reliability = "plausible"
        self.spread_level = max(0, min(10, self.spread_level))
        self.age_in_months = max(0, self.age_in_months)

    @property
    def is_expired(self) -> bool:
        return self.age_in_months >= RUMOR_MAX_AGE_MONTHS

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "source_location_id": self.source_location_id,
            "target_subject": self.target_subject,
            "reliability": self.reliability,
            "spread_level": self.spread_level,
            "age_in_months": self.age_in_months,
            "content_tags": list(self.content_tags),
            "description": self.description,
            "source_event_id": self.source_event_id,
            "year_created": self.year_created,
            "month_created": self.month_created,
            "created_absolute_day": self.created_absolute_day,
            "created_calendar_key": self.created_calendar_key,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Rumor":
        return cls(
            id=data.get("id", f"rum_{uuid.uuid4().hex[:12]}"),
            category=data.get("category", "event"),
            source_location_id=data.get("source_location_id"),
            target_subject=data.get("target_subject", ""),
            reliability=data.get("reliability", "plausible"),
            spread_level=data.get("spread_level", 1),
            age_in_months=data.get("age_in_months", 0),
            content_tags=list(data.get("content_tags", [])),
            description=data.get("description", ""),
            source_event_id=data.get("source_event_id"),
            year_created=data.get("year_created", 0),
            month_created=data.get("month_created", 1),
            created_absolute_day=max(0, int(data.get("created_absolute_day", 0))),
            created_calendar_key=data.get("created_calendar_key", ""),
        )

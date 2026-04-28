"""Calendar schema definitions for setting bundles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class CalendarMonthDefinition:
    """One month entry in a world-specific calendar."""

    month_key: str
    display_name: str
    days: int
    season: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "month_key": self.month_key,
            "display_name": self.display_name,
            "days": int(self.days),
            "season": self.season,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarMonthDefinition":
        return cls(
            month_key=data["month_key"],
            display_name=data.get("display_name", data["month_key"]),
            days=max(1, int(data.get("days", 30))),
            season=data.get("season", ""),
        )


@dataclass
class CalendarDefinition:
    """Serializable calendar metadata for a world setting."""

    calendar_key: str
    display_name: str
    months: List[CalendarMonthDefinition] = field(default_factory=list)

    @property
    def months_per_year(self) -> int:
        return max(1, len(self.months))

    @property
    def days_per_year(self) -> int:
        if not self.months:
            return 30
        return sum(max(1, month.days) for month in self.months)

    def days_in_month(self, month: int) -> int:
        if not self.months:
            return 30
        month_index = max(1, min(self.months_per_year, month)) - 1
        return max(1, self.months[month_index].days)

    def month_definition(self, month: int) -> CalendarMonthDefinition:
        if not self.months:
            return CalendarMonthDefinition(
                month_key=f"month_{max(1, int(month))}",
                display_name=f"Month {max(1, int(month))}",
                days=30,
            )
        month_index = max(1, min(self.months_per_year, month)) - 1
        return self.months[month_index]

    def month_display_name(self, month: int) -> str:
        return self.month_definition(month).display_name

    def season_for_month(self, month: int) -> str:
        if not self.months:
            return "unknown"
        month_index = max(1, min(self.months_per_year, month)) - 1
        season = self.months[month_index].season
        return season or "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "calendar_key": self.calendar_key,
            "display_name": self.display_name,
            "months": [month.to_dict() for month in self.months],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CalendarDefinition":
        return cls(
            calendar_key=data.get("calendar_key", "default_calendar"),
            display_name=data.get("display_name", "Default Calendar"),
            months=[
                CalendarMonthDefinition.from_dict(item)
                for item in data.get("months", [])
            ],
        )


def default_calendar_definition() -> CalendarDefinition:
    """Return the bundled Aethorian default calendar."""

    return CalendarDefinition(
        calendar_key="aethorian_reckoning",
        display_name="Aethorian Reckoning",
        months=[
            CalendarMonthDefinition("embermorn", "Embermorn", 30, season="winter"),
            CalendarMonthDefinition("frostwane", "Frostwane", 30, season="winter"),
            CalendarMonthDefinition("raincall", "Raincall", 30, season="spring"),
            CalendarMonthDefinition("bloomtide", "Bloomtide", 30, season="spring"),
            CalendarMonthDefinition("suncrest", "Suncrest", 30, season="spring"),
            CalendarMonthDefinition("highsun", "Highsun", 30, season="summer"),
            CalendarMonthDefinition("goldleaf", "Goldleaf", 30, season="summer"),
            CalendarMonthDefinition("hearthwane", "Hearthwane", 30, season="summer"),
            CalendarMonthDefinition("duskmarch", "Duskmarch", 30, season="autumn"),
            CalendarMonthDefinition("cinderfall", "Cinderfall", 30, season="autumn"),
            CalendarMonthDefinition("longshade", "Longshade", 30, season="autumn"),
            CalendarMonthDefinition("nightfrost", "Nightfrost", 30, season="winter"),
        ],
    )

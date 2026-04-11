"""Minimal setting bundle schema and loader for PR-I foundation work."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from .world_data import WORLD_LORE


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


@dataclass
class WorldDefinition:
    """Static lore metadata for a world setting bundle."""

    world_key: str
    display_name: str
    lore_text: str
    era: str = ""
    cultures: List[str] = field(default_factory=list)
    factions: List[str] = field(default_factory=list)
    calendar: CalendarDefinition = field(default_factory=default_calendar_definition)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "world_key": self.world_key,
            "display_name": self.display_name,
            "lore_text": self.lore_text,
            "era": self.era,
            "cultures": list(self.cultures),
            "factions": list(self.factions),
            "calendar": self.calendar.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldDefinition":
        return cls(
            world_key=data["world_key"],
            display_name=data["display_name"],
            lore_text=data["lore_text"],
            era=data.get("era", ""),
            cultures=list(data.get("cultures", [])),
            factions=list(data.get("factions", [])),
            calendar=CalendarDefinition.from_dict(
                data.get("calendar", default_calendar_definition().to_dict())
            ),
        )


@dataclass
class SettingBundle:
    """Minimal serializable container for static world-definition data."""

    schema_version: int
    world_definition: WorldDefinition

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "world_definition": self.world_definition.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SettingBundle":
        return cls(
            schema_version=int(data.get("schema_version", 1)),
            world_definition=WorldDefinition.from_dict(data["world_definition"]),
        )


def default_aethoria_bundle(
    *,
    display_name: str = "Aethoria",
    lore_text: str = WORLD_LORE,
) -> SettingBundle:
    """Return the default in-repo bundle until PR-J authors external data."""

    return SettingBundle(
        schema_version=1,
        world_definition=WorldDefinition(
            world_key="aethoria",
            display_name=display_name,
            lore_text=lore_text,
            era="Age of Embers",
        ),
    )


def load_setting_bundle(path: str | Path) -> SettingBundle:
    """Load a setting bundle from a JSON file."""

    bundle_path = Path(path)
    try:
        data = json.loads(bundle_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Setting bundle not found: {bundle_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid setting bundle JSON in {bundle_path}: {exc.msg}") from exc

    try:
        return SettingBundle.from_dict(data)
    except KeyError as exc:
        missing = exc.args[0]
        raise ValueError(f"Setting bundle {bundle_path} is missing required field: {missing}") from exc

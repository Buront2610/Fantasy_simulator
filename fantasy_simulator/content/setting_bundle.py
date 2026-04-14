"""Serializable setting-bundle schema and loader for static world data."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List


BUNDLES_DIR = Path(__file__).with_name("bundles")
DEFAULT_AETHORIA_BUNDLE_PATH = BUNDLES_DIR / "aethoria.json"


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


@dataclass
class RaceDefinition:
    """Static race metadata for a setting bundle."""

    name: str
    description: str
    stat_bonuses: Dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "stat_bonuses": {key: int(value) for key, value in self.stat_bonuses.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RaceDefinition":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            stat_bonuses={
                key: int(value)
                for key, value in dict(data.get("stat_bonuses", {})).items()
            },
        )


@dataclass
class JobDefinition:
    """Static job metadata for a setting bundle."""

    name: str
    description: str
    primary_skills: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "primary_skills": list(self.primary_skills),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobDefinition":
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            primary_skills=list(data.get("primary_skills", [])),
        )


@dataclass
class SiteSeedDefinition:
    """A default location/site seed for bundle-driven world bootstrapping."""

    location_id: str
    name: str
    description: str
    region_type: str
    x: int
    y: int
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location_id": self.location_id,
            "name": self.name,
            "description": self.description,
            "region_type": self.region_type,
            "x": int(self.x),
            "y": int(self.y),
            "tags": list(self.tags),
        }

    def as_world_data_entry(self) -> tuple[str, str, str, str, int, int]:
        return (
            self.location_id,
            self.name,
            self.description,
            self.region_type,
            int(self.x),
            int(self.y),
        )

    def has_tag(self, tag: str) -> bool:
        """Return whether this seed carries the given semantic tag."""
        return tag in self.tags

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SiteSeedDefinition":
        return cls(
            location_id=data["location_id"],
            name=data["name"],
            description=data.get("description", ""),
            region_type=data.get("region_type", "plains"),
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            tags=list(data.get("tags", [])),
        )


@dataclass
class NamingRulesDefinition:
    """Simple name pools for default character generation."""

    first_names_male: List[str] = field(default_factory=list)
    first_names_female: List[str] = field(default_factory=list)
    first_names_non_binary: List[str] = field(default_factory=list)
    last_names: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "first_names_male": list(self.first_names_male),
            "first_names_female": list(self.first_names_female),
            "first_names_non_binary": list(self.first_names_non_binary),
            "last_names": list(self.last_names),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NamingRulesDefinition":
        male = list(data.get("first_names_male", []))
        female = list(data.get("first_names_female", []))
        non_binary = list(data.get("first_names_non_binary", []))
        if not non_binary:
            non_binary = male + female
        return cls(
            first_names_male=male,
            first_names_female=female,
            first_names_non_binary=non_binary,
            last_names=list(data.get("last_names", [])),
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
    calendar: CalendarDefinition = field(default_factory=lambda: default_calendar_definition())
    races: List[RaceDefinition] = field(default_factory=list)
    jobs: List[JobDefinition] = field(default_factory=list)
    site_seeds: List[SiteSeedDefinition] = field(default_factory=list)
    naming_rules: NamingRulesDefinition = field(default_factory=NamingRulesDefinition)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "world_key": self.world_key,
            "display_name": self.display_name,
            "lore_text": self.lore_text,
            "era": self.era,
            "cultures": list(self.cultures),
            "factions": list(self.factions),
            "calendar": self.calendar.to_dict(),
            "races": [race.to_dict() for race in self.races],
            "jobs": [job.to_dict() for job in self.jobs],
            "site_seeds": [seed.to_dict() for seed in self.site_seeds],
            "naming_rules": self.naming_rules.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorldDefinition":
        calendar = CalendarDefinition.from_dict(
            data.get("calendar", default_calendar_definition().to_dict())
        )
        return cls(
            world_key=data["world_key"],
            display_name=data["display_name"],
            lore_text=data["lore_text"],
            era=data.get("era", ""),
            cultures=list(data.get("cultures", [])),
            factions=list(data.get("factions", [])),
            calendar=calendar,
            races=[
                RaceDefinition.from_dict(item)
                for item in data.get("races", [])
            ],
            jobs=[
                JobDefinition.from_dict(item)
                for item in data.get("jobs", [])
            ],
            site_seeds=[
                SiteSeedDefinition.from_dict(item)
                for item in data.get("site_seeds", [])
            ],
            naming_rules=NamingRulesDefinition.from_dict(data.get("naming_rules", {})),
        )


@dataclass
class SettingBundle:
    """Serializable container for static world-definition data."""

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


@lru_cache(maxsize=1)
def _default_aethoria_bundle_data() -> Dict[str, Any]:
    try:
        return json.loads(DEFAULT_AETHORIA_BUNDLE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Bundled Aethoria setting not found: {DEFAULT_AETHORIA_BUNDLE_PATH}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Bundled Aethoria setting JSON is invalid: {DEFAULT_AETHORIA_BUNDLE_PATH}: {exc.msg}"
        ) from exc


def _validate_setting_bundle(bundle: SettingBundle, *, source: str) -> None:
    world = bundle.world_definition
    if bundle.schema_version < 1:
        raise ValueError(f"Setting bundle {source} has invalid schema_version: {bundle.schema_version}")
    if not world.world_key:
        raise ValueError(f"Setting bundle {source} must define world_definition.world_key")
    if not world.display_name:
        raise ValueError(f"Setting bundle {source} must define world_definition.display_name")
    if not world.lore_text:
        raise ValueError(f"Setting bundle {source} must define world_definition.lore_text")

    race_names = [race.name for race in world.races]
    if race_names and len(race_names) != len(set(race_names)):
        raise ValueError(f"Setting bundle {source} contains duplicate race names")

    job_names = [job.name for job in world.jobs]
    if job_names and len(job_names) != len(set(job_names)):
        raise ValueError(f"Setting bundle {source} contains duplicate job names")

    site_ids = [seed.location_id for seed in world.site_seeds]
    if site_ids and len(site_ids) != len(set(site_ids)):
        raise ValueError(f"Setting bundle {source} contains duplicate site seed ids")

    site_coords = [(seed.x, seed.y) for seed in world.site_seeds]
    if site_coords and len(site_coords) != len(set(site_coords)):
        raise ValueError(f"Setting bundle {source} contains duplicate site seed coordinates")

    naming = world.naming_rules
    has_first_name_rules = (
        naming.first_names_male
        or naming.first_names_female
        or naming.first_names_non_binary
    )
    if has_first_name_rules and not naming.first_names_male:
        raise ValueError(f"Setting bundle {source} must provide first_names_male when naming rules are defined")
    if has_first_name_rules and not naming.first_names_female:
        raise ValueError(f"Setting bundle {source} must provide first_names_female when naming rules are defined")
    if has_first_name_rules and not naming.last_names:
        raise ValueError(f"Setting bundle {source} must provide last_names when naming rules are defined")


def _bundle_from_data(data: Dict[str, Any], *, source: str) -> SettingBundle:
    try:
        bundle = SettingBundle.from_dict(data)
    except KeyError as exc:
        missing = exc.args[0]
        raise ValueError(f"Setting bundle {source} is missing required field: {missing}") from exc
    _validate_setting_bundle(bundle, source=source)
    return bundle


def default_aethoria_bundle(
    *,
    display_name: str | None = None,
    lore_text: str | None = None,
) -> SettingBundle:
    """Return the default bundled Aethoria setting as a mutable copy."""

    bundle = _bundle_from_data(_default_aethoria_bundle_data(), source=str(DEFAULT_AETHORIA_BUNDLE_PATH))
    if display_name is not None:
        bundle.world_definition.display_name = display_name
    if lore_text is not None:
        bundle.world_definition.lore_text = lore_text
    return bundle


def load_setting_bundle(path: str | Path) -> SettingBundle:
    """Load a setting bundle from a JSON file."""

    bundle_path = Path(path)
    try:
        data = json.loads(bundle_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Setting bundle not found: {bundle_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid setting bundle JSON in {bundle_path}: {exc.msg}") from exc
    return _bundle_from_data(data, source=str(bundle_path))

"""Report view-model dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class CharacterReportEntry:
    """A single character's summary within a report."""

    char_id: str
    name: str
    events: List[str] = field(default_factory=list)


@dataclass
class LocationReportEntry:
    """A single location's summary within a report."""

    location_id: str
    name: str
    event_count: int = 0
    notable_events: List[str] = field(default_factory=list)


@dataclass
class RumorReportEntry:
    """A single rumor entry within a report."""

    rumor_id: str
    description: str
    reliability: str
    category: str = "event"


@dataclass
class MonthlyReport:
    """Data model for a monthly report."""

    year: int
    month: int
    month_label: str = ""
    season: str = "unknown"
    character_entries: List[CharacterReportEntry] = field(default_factory=list)
    notable_events: List[str] = field(default_factory=list)
    location_entries: List[LocationReportEntry] = field(default_factory=list)
    rumor_entries: List[RumorReportEntry] = field(default_factory=list)
    total_events: int = 0


@dataclass
class YearlyReport:
    """Data model for a yearly report."""

    year: int
    character_entries: List[CharacterReportEntry] = field(default_factory=list)
    notable_events: List[str] = field(default_factory=list)
    location_entries: List[LocationReportEntry] = field(default_factory=list)
    total_events: int = 0
    deaths_this_year: int = 0

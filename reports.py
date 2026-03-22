"""
reports.py - Monthly and yearly report generation from WorldEventRecord.

Reports are non-persistent view models derived from the canonical
WorldEventRecord store.  They are generated on demand for display
and never saved to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List

from i18n import tr

if TYPE_CHECKING:
    from character import Character
    from events import WorldEventRecord
    from world import World


# ------------------------------------------------------------------
# Report data models
# ------------------------------------------------------------------

@dataclass
class CharacterReportEntry:
    """A single character's summary within a report."""

    char_id: str
    name: str
    status: str
    location_name: str
    events: List[str] = field(default_factory=list)


@dataclass
class LocationReportEntry:
    """A single location's summary within a report."""

    location_id: str
    name: str
    event_count: int = 0
    notable_events: List[str] = field(default_factory=list)


@dataclass
class MonthlyReport:
    """Data model for a monthly report."""

    year: int
    month: int
    character_entries: List[CharacterReportEntry] = field(default_factory=list)
    notable_events: List[str] = field(default_factory=list)
    location_entries: List[LocationReportEntry] = field(default_factory=list)
    total_events: int = 0


@dataclass
class YearlyReport:
    """Data model for a yearly report."""

    year: int
    character_entries: List[CharacterReportEntry] = field(default_factory=list)
    notable_events: List[str] = field(default_factory=list)
    location_entries: List[LocationReportEntry] = field(default_factory=list)
    total_events: int = 0
    alive_count: int = 0
    dead_count: int = 0


# ------------------------------------------------------------------
# Season helpers
# ------------------------------------------------------------------

_SEASON_MAP: Dict[int, str] = {
    1: "winter", 2: "winter", 3: "spring",
    4: "spring", 5: "spring", 6: "summer",
    7: "summer", 8: "summer", 9: "autumn",
    10: "autumn", 11: "autumn", 12: "winter",
}

_SEVERITY_THRESHOLD_MONTHLY = 2
_SEVERITY_THRESHOLD_YEARLY = 3


def _season_for_month(month: int) -> str:
    return _SEASON_MAP.get(month, "unknown")


# ------------------------------------------------------------------
# Report generation
# ------------------------------------------------------------------

def generate_monthly_report(
    world: World,
    year: int,
    month: int,
) -> MonthlyReport:
    """Generate a monthly report from WorldEventRecord entries.

    Filters event_records for the given year/month and builds a
    structured report highlighting favorite/spotlighted characters
    and notable events.
    """
    records = [
        r for r in world.event_records
        if r.year == year and r.month == month
    ]

    # Build character entries for favorite / spotlighted / playable chars
    watched_chars = [
        c for c in world.characters
        if c.favorite or c.spotlighted or c.playable
    ]
    char_entries: List[CharacterReportEntry] = []
    for char in watched_chars:
        char_records = [
            r for r in records
            if r.primary_actor_id == char.char_id
            or char.char_id in r.secondary_actor_ids
        ]
        loc_name = world.location_name(char.location_id)
        status = _char_status_label(char)
        entry = CharacterReportEntry(
            char_id=char.char_id,
            name=char.name,
            status=status,
            location_name=loc_name,
            events=[r.description for r in char_records],
        )
        char_entries.append(entry)

    # Notable events (severity >= threshold)
    notable = [r.description for r in records if r.severity >= _SEVERITY_THRESHOLD_MONTHLY]

    # Location summaries
    loc_event_map: Dict[str, List[WorldEventRecord]] = {}
    for r in records:
        if r.location_id:
            loc_event_map.setdefault(r.location_id, []).append(r)

    loc_entries: List[LocationReportEntry] = []
    for loc_id, loc_records in sorted(loc_event_map.items()):
        loc_name = world.location_name(loc_id)
        notable_loc = [r.description for r in loc_records if r.severity >= _SEVERITY_THRESHOLD_MONTHLY]
        loc_entries.append(LocationReportEntry(
            location_id=loc_id,
            name=loc_name,
            event_count=len(loc_records),
            notable_events=notable_loc,
        ))

    return MonthlyReport(
        year=year,
        month=month,
        character_entries=char_entries,
        notable_events=notable,
        location_entries=loc_entries,
        total_events=len(records),
    )


def generate_yearly_report(
    world: World,
    year: int,
) -> YearlyReport:
    """Generate a yearly report from WorldEventRecord entries.

    Aggregates all event_records for the given year and builds a
    structured report with character summaries and world highlights.
    """
    records = [r for r in world.event_records if r.year == year]

    alive = sum(1 for c in world.characters if c.alive)
    dead = sum(1 for c in world.characters if not c.alive)

    # Build character entries for favorite / spotlighted / playable chars
    watched_chars = [
        c for c in world.characters
        if c.favorite or c.spotlighted or c.playable
    ]
    char_entries: List[CharacterReportEntry] = []
    for char in watched_chars:
        char_records = [
            r for r in records
            if r.primary_actor_id == char.char_id
            or char.char_id in r.secondary_actor_ids
        ]
        loc_name = world.location_name(char.location_id)
        status = _char_status_label(char)
        events = [r.description for r in char_records if r.severity >= _SEVERITY_THRESHOLD_YEARLY]
        if not events:
            events = [r.description for r in char_records[:3]]
        entry = CharacterReportEntry(
            char_id=char.char_id,
            name=char.name,
            status=status,
            location_name=loc_name,
            events=events,
        )
        char_entries.append(entry)

    # Notable events for the year (severity >= threshold)
    notable = [r.description for r in records if r.severity >= _SEVERITY_THRESHOLD_YEARLY]

    # Location summaries
    loc_event_map: Dict[str, List[WorldEventRecord]] = {}
    for r in records:
        if r.location_id:
            loc_event_map.setdefault(r.location_id, []).append(r)

    loc_entries: List[LocationReportEntry] = []
    for loc_id, loc_records in sorted(loc_event_map.items()):
        loc_name = world.location_name(loc_id)
        notable_loc = [r.description for r in loc_records if r.severity >= _SEVERITY_THRESHOLD_YEARLY]
        if notable_loc:
            loc_entries.append(LocationReportEntry(
                location_id=loc_id,
                name=loc_name,
                event_count=len(loc_records),
                notable_events=notable_loc,
            ))

    return YearlyReport(
        year=year,
        character_entries=char_entries,
        notable_events=notable,
        location_entries=loc_entries,
        total_events=len(records),
        alive_count=alive,
        dead_count=dead,
    )


# ------------------------------------------------------------------
# Report formatting (i18n-aware text output)
# ------------------------------------------------------------------

def format_monthly_report(report: MonthlyReport) -> str:
    """Format a MonthlyReport as displayable text."""
    season = _season_for_month(report.month)
    lines = [
        "=" * 55,
        f"  {tr('report_monthly_title', year=report.year, month=report.month, season=tr('season_' + season))}",
        "=" * 55,
    ]

    # Watched characters section
    if report.character_entries:
        lines.append("")
        lines.append(f"  {tr('report_section_characters')}")
        for entry in report.character_entries:
            lines.append(
                f"    {entry.name} [{entry.status}]  {tr('at_label')} {entry.location_name}"
            )
            for ev in entry.events:
                lines.append(f"      - {ev}")

    # Notable events
    if report.notable_events:
        lines.append("")
        lines.append(f"  {tr('report_section_notable')}")
        for ev in report.notable_events:
            lines.append(f"    - {ev}")

    # Location highlights
    if report.location_entries:
        lines.append("")
        lines.append(f"  {tr('report_section_world')}")
        for loc in report.location_entries:
            if loc.notable_events:
                for ev in loc.notable_events:
                    lines.append(f"    {loc.name}: {ev}")

    # Footer
    lines.append("")
    lines.append(f"  {tr('report_total_events', count=report.total_events)}")
    lines.append("=" * 55)
    return "\n".join(lines)


def format_yearly_report(report: YearlyReport) -> str:
    """Format a YearlyReport as displayable text."""
    lines = [
        "=" * 55,
        f"  {tr('report_yearly_title', year=report.year)}",
        "=" * 55,
    ]

    # World overview
    lines.append("")
    lines.append(f"  {tr('report_section_world_overview')}")
    lines.append(
        f"    {tr('characters_alive')}: {report.alive_count}  "
        f"{tr('characters_deceased')}: {report.dead_count}"
    )
    lines.append(f"    {tr('total_events')}: {report.total_events}")

    # Notable events
    if report.notable_events:
        lines.append("")
        lines.append(f"  {tr('report_section_notable')}")
        for ev in report.notable_events:
            lines.append(f"    - {ev}")

    # Location highlights
    if report.location_entries:
        lines.append("")
        lines.append(f"  {tr('report_section_locations')}")
        for loc in report.location_entries:
            for ev in loc.notable_events:
                lines.append(f"    {loc.name}: {ev}")

    # Watched characters
    if report.character_entries:
        lines.append("")
        lines.append(f"  {tr('report_section_your_adventurers')}")
        for entry in report.character_entries:
            if entry.events:
                summary = "; ".join(entry.events[:2])
                lines.append(f"    {entry.name} [{entry.status}]: {summary}")
            else:
                lines.append(
                    f"    {entry.name} [{entry.status}]  {tr('at_label')} {entry.location_name}"
                )

    # Footer
    lines.append("=" * 55)
    return "\n".join(lines)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _char_status_label(char: Character) -> str:
    """Return a localized status label for a character."""
    if not char.alive:
        return tr("status_dead")
    if char.injury_status == "injured":
        return tr("injury_status_injured")
    return tr("status_alive")

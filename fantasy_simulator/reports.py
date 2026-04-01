"""
reports.py - Monthly and yearly report generation from WorldEventRecord.

Reports are non-persistent view models derived exclusively from the
canonical WorldEventRecord store.  Character status and location are
derived from the event records of the period rather than from current
world state, so that past reports remain stable over time.

Reports are generated on demand for display and never saved to disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Set

from .i18n import tr
from .narrative.constants import EVENT_KINDS_FATAL
from .rumor import RUMOR_MAX_AGE_MONTHS

if TYPE_CHECKING:
    from .events import WorldEventRecord
    from .world import World


# ------------------------------------------------------------------
# Report data models
# ------------------------------------------------------------------

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


def _watched_char_ids(world: World) -> Set[str]:
    """Return char_ids for favorite / spotlighted / playable characters."""
    return {
        c.char_id for c in world.characters
        if c.favorite or c.spotlighted or c.playable
    }


def _char_name_map(world: World) -> Dict[str, str]:
    """Return a char_id → name lookup."""
    return {c.char_id: c.name for c in world.characters}


def _actors_in_record(record: WorldEventRecord) -> List[str]:
    """Return all actor ids mentioned in a record."""
    ids: List[str] = []
    if record.primary_actor_id:
        ids.append(record.primary_actor_id)
    ids.extend(record.secondary_actor_ids)
    return ids


# ------------------------------------------------------------------
# Report generation
# ------------------------------------------------------------------

def generate_monthly_report(
    world: World,
    year: int,
    month: int,
) -> MonthlyReport:
    """Generate a monthly report purely from WorldEventRecord entries.

    Character entries are built only for watched characters that actually
    appear in that month's event records.  No current-world character
    state (location, alive, injury) is mixed in, so past-month reports
    remain stable.
    """
    records = [
        r for r in world.event_records
        if r.year == year and r.month == month
    ]

    watched = _watched_char_ids(world)
    names = _char_name_map(world)

    # Collect events per watched char that appeared in this period
    char_event_map: Dict[str, List[str]] = {}
    for r in records:
        for cid in _actors_in_record(r):
            if cid in watched:
                char_event_map.setdefault(cid, []).append(r.description)

    char_entries = [
        CharacterReportEntry(
            char_id=cid,
            name=names.get(cid, cid),
            events=evts,
        )
        for cid, evts in sorted(char_event_map.items())
    ]

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

    # Rumor entries — evaluate expiration and freshness relative to the
    # report's own year/month so that historical reports stay stable even
    # after the simulation advances and ages/removes rumors.
    # Read from both active rumors and the archive so that past reports
    # remain reproducible after rumors expire or are trimmed.
    _RUMOR_FRESHNESS_MONTHS = 6
    report_abs_month = year * 12 + month
    all_rumors = list(world.rumors) + list(world.rumor_archive)
    rumor_entries = []
    for r in all_rumors:
        created_abs = r.year_created * 12 + r.month_created
        if created_abs > report_abs_month:
            continue
        age_at_report = report_abs_month - created_abs
        if age_at_report >= RUMOR_MAX_AGE_MONTHS:
            continue
        if age_at_report > _RUMOR_FRESHNESS_MONTHS:
            continue
        rumor_entries.append(RumorReportEntry(
            rumor_id=r.id,
            description=r.description,
            reliability=r.reliability,
            category=r.category,
        ))

    return MonthlyReport(
        year=year,
        month=month,
        character_entries=char_entries,
        notable_events=notable,
        location_entries=loc_entries,
        rumor_entries=rumor_entries,
        total_events=len(records),
    )


def generate_yearly_report(
    world: World,
    year: int,
) -> YearlyReport:
    """Generate a yearly report purely from WorldEventRecord entries.

    Character entries are built only for watched characters that actually
    appear in that year's event records.  Death counts are derived from
    fatal event records, not from current world state.
    """
    records = [r for r in world.event_records if r.year == year]

    deaths_this_year = sum(1 for r in records if r.kind in EVENT_KINDS_FATAL)

    watched = _watched_char_ids(world)
    names = _char_name_map(world)

    # Collect events per watched char that appeared this year
    char_event_map: Dict[str, List[WorldEventRecord]] = {}
    for r in records:
        for cid in _actors_in_record(r):
            if cid in watched:
                char_event_map.setdefault(cid, []).append(r)

    char_entries: List[CharacterReportEntry] = []
    for cid, char_records in sorted(char_event_map.items()):
        events = [r.description for r in char_records if r.severity >= _SEVERITY_THRESHOLD_YEARLY]
        if not events:
            events = [r.description for r in char_records[:3]]
        char_entries.append(CharacterReportEntry(
            char_id=cid,
            name=names.get(cid, cid),
            events=events,
        ))

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
        deaths_this_year=deaths_this_year,
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

    # Watched characters section — only those with events this month
    if report.character_entries:
        lines.append("")
        lines.append(f"  {tr('report_section_watched')}")
        for entry in report.character_entries:
            lines.append(f"    {entry.name}")
            for ev in entry.events:
                lines.append(f"      - {ev}")

    # Notable events
    if report.notable_events:
        lines.append("")
        lines.append(f"  {tr('report_section_notable')}")
        for ev in report.notable_events:
            lines.append(f"    - {ev}")

    # Location highlights — only locations with notable events
    location_entries_with_notables = [
        loc for loc in report.location_entries if loc.notable_events
    ]
    if location_entries_with_notables:
        lines.append("")
        lines.append(f"  {tr('report_section_world')}")
        for loc in location_entries_with_notables:
            for ev in loc.notable_events:
                lines.append(f"    {loc.name}: {ev}")

    # Rumors
    if report.rumor_entries:
        lines.append("")
        lines.append(f"  {tr('report_section_rumors')}")
        for entry in report.rumor_entries:
            reliability_label = tr(f"rumor_reliability_{entry.reliability}")
            lines.append(f"    - {entry.description} ({reliability_label})")

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

    # World overview — derived from events only
    lines.append("")
    lines.append(f"  {tr('report_section_world_overview')}")
    lines.append(f"    {tr('total_events')}: {report.total_events}")
    if report.deaths_this_year:
        lines.append(f"    {tr('report_deaths_this_year', count=report.deaths_this_year)}")

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

    # Watched characters — only those with events this year
    if report.character_entries:
        lines.append("")
        lines.append(f"  {tr('report_section_watched_year')}")
        for entry in report.character_entries:
            if entry.events:
                summary = "; ".join(entry.events[:2])
                lines.append(f"    {entry.name}: {summary}")
            else:
                lines.append(f"    {entry.name}")

    # Footer
    lines.append("=" * 55)
    return "\n".join(lines)

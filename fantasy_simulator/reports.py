"""
reports.py - Monthly and yearly report generation from WorldEventRecord.

Reports are non-persistent view models derived from the canonical
WorldEventRecord store.  Period membership and event grouping come from the
record payload, while display names are resolved through the current world
context so renamed locations and authored faction names use current labels.
That means report membership is stable for a saved event history, while
rendered labels may intentionally follow the active world context.

Reports are generated on demand for display and never saved to disk.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Dict, List, Set

from .event_rendering import render_event_record
from .narrative.constants import EVENT_KINDS_FATAL
from .reports_formatting import format_monthly_report, format_yearly_report
from .reports_models import (
    CharacterReportEntry,
    LocationReportEntry,
    MonthlyReport,
    RumorReportEntry,
    YearlyReport,
)
from .rumor import RUMOR_MAX_AGE_MONTHS
from .world_event_index import location_ids_for_record

if TYPE_CHECKING:
    from .event_models import WorldEventRecord
    from .world import World

__all__ = [
    "CharacterReportEntry",
    "LocationReportEntry",
    "RumorReportEntry",
    "MonthlyReport",
    "YearlyReport",
    "generate_monthly_report",
    "generate_yearly_report",
    "format_monthly_report",
    "format_yearly_report",
]


_SEVERITY_THRESHOLD_MONTHLY = 2
_SEVERITY_THRESHOLD_YEARLY = 3


def _watched_char_ids(world: World, records: List[WorldEventRecord]) -> Set[str]:
    """Return watched char_ids using immutable event tags when available."""
    current_watched = {
        c.char_id for c in world.characters
        if c.favorite or c.spotlighted or c.playable
    }
    tagged_ids = {
        tag.split(world.WATCHED_ACTOR_TAG_PREFIX, 1)[1]
        for record in records
        for tag in record.tags
        if tag.startswith(world.WATCHED_ACTOR_TAG_PREFIX)
    }
    if tagged_ids:
        legacy_actor_ids = {
            actor_id
            for record in records
            if not any(tag.startswith(world.WATCHED_ACTOR_TAG_PREFIX) for tag in record.tags)
            for actor_id in _actors_in_record(record)
            if actor_id in current_watched
        }
        return tagged_ids | legacy_actor_ids
    return current_watched


def _char_name_map(world: World) -> Dict[str, str]:
    """Return a char_id → name lookup."""
    return {c.char_id: c.name for c in world.characters}


def _sort_location_entries(entries: List[LocationReportEntry]) -> List[LocationReportEntry]:
    """Sort location report entries by player-facing importance and name."""
    return sorted(
        entries,
        key=lambda entry: (-entry.event_count, entry.name.casefold(), entry.location_id),
    )


def _actors_in_record(record: WorldEventRecord) -> List[str]:
    """Return all actor ids mentioned in a record."""
    ids: List[str] = []
    if record.primary_actor_id:
        ids.append(record.primary_actor_id)
    ids.extend(record.secondary_actor_ids)
    return ids


def _render_report_event(world: World, record: WorldEventRecord) -> str:
    """Render one canonical event for report display using the active locale."""
    return render_event_record(record, world=world)


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
    state (location, alive, injury) is mixed in, so past-month event
    membership remains record-derived.  Rendered names may reflect the
    current world context.
    """
    records = world.get_events_by_month(year, month)
    record_calendar_key = next((r.calendar_key for r in records if r.calendar_key), "")
    month_label = world.month_display_name_for_date(
        year,
        month,
        calendar_key=record_calendar_key,
    )
    season = world.season_for_date(year, month, calendar_key=record_calendar_key)

    watched = _watched_char_ids(world, records)
    names = _char_name_map(world)

    # Collect events per watched char that appeared in this period
    char_event_map: Dict[str, List[str]] = {}
    for r in records:
        for cid in _actors_in_record(r):
            if cid in watched:
                char_event_map.setdefault(cid, []).append(_render_report_event(world, r))

    char_entries = [
        CharacterReportEntry(
            char_id=cid,
            name=names.get(cid, cid),
            events=evts,
        )
        for cid, evts in sorted(char_event_map.items())
    ]

    # Notable events (severity >= threshold)
    notable = [_render_report_event(world, r) for r in records if r.severity >= _SEVERITY_THRESHOLD_MONTHLY]

    # Location summaries
    loc_event_map: Dict[str, List[WorldEventRecord]] = {}
    for r in records:
        for loc_id in location_ids_for_record(r):
            loc_event_map.setdefault(loc_id, []).append(r)

    loc_entries: List[LocationReportEntry] = []
    for loc_id, loc_records in sorted(loc_event_map.items()):
        loc_name = world.location_name(loc_id)
        notable_loc = [
            _render_report_event(world, r)
            for r in loc_records
            if r.severity >= _SEVERITY_THRESHOLD_MONTHLY
        ]
        loc_entries.append(LocationReportEntry(
            location_id=loc_id,
            name=loc_name,
            event_count=len(loc_records),
            notable_events=notable_loc,
        ))

    # Rumor entries — evaluate expiration and freshness relative to the
    # report's own year/month so that historical rumor membership stays
    # stable even after the simulation advances and ages/removes rumors.
    # Read from both active rumors and the archive so that past reports
    # remain reproducible after rumors expire or are trimmed.
    period_calendar = world.calendar_definition_for_date(year, month, calendar_key=record_calendar_key)
    _RUMOR_FRESHNESS_MONTHS = max(1, period_calendar.months_per_year // 2)
    report_absolute_day = max(
        (record.absolute_day for record in records if record.absolute_day > 0),
        default=world.latest_absolute_day_before_or_on(year, month),
    )
    all_rumors = list(world.rumors) + list(world.rumor_archive)
    rumor_entries = []
    for rumor in all_rumors:
        if (rumor.year_created, rumor.month_created) > (year, month):
            continue
        if report_absolute_day > 0 and rumor.created_absolute_day > 0:
            age_at_report = world.months_elapsed_between(
                rumor.year_created,
                rumor.month_created,
                year,
                month,
                start_day=1,
                end_day=period_calendar.days_in_month(month),
                start_calendar_key=rumor.created_calendar_key,
            )
        else:
            age_at_report = world.months_elapsed_between(
                rumor.year_created,
                rumor.month_created,
                year,
                month,
                start_calendar_key=rumor.created_calendar_key,
            )
        if age_at_report >= RUMOR_MAX_AGE_MONTHS:
            continue
        if age_at_report > _RUMOR_FRESHNESS_MONTHS:
            continue
        rumor_entries.append(RumorReportEntry(
            rumor_id=rumor.id,
            description=rumor.description,
            reliability=rumor.reliability,
            category=rumor.category,
        ))

    return MonthlyReport(
        year=year,
        month=month,
        month_label=month_label,
        season=season,
        character_entries=char_entries,
        notable_events=notable,
        location_entries=_sort_location_entries(loc_entries),
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
    fatal event records, not from current world state.  Rendered names may
    reflect the current world context.
    """
    records = world.get_events_by_year(year)

    deaths_this_year = sum(1 for r in records if r.kind in EVENT_KINDS_FATAL)

    watched = _watched_char_ids(world, records)
    names = _char_name_map(world)

    # Collect events per watched char that appeared this year
    char_event_map: Dict[str, List[WorldEventRecord]] = {}
    for r in records:
        for cid in _actors_in_record(r):
            if cid in watched:
                char_event_map.setdefault(cid, []).append(r)

    char_entries: List[CharacterReportEntry] = []
    for cid, char_records in sorted(char_event_map.items()):
        events = [
            _render_report_event(world, r)
            for r in char_records
            if r.severity >= _SEVERITY_THRESHOLD_YEARLY
        ]
        if not events:
            events = [_render_report_event(world, r) for r in char_records[:3]]
        char_entries.append(CharacterReportEntry(
            char_id=cid,
            name=names.get(cid, cid),
            events=events,
        ))

    # Notable events for the year (severity >= threshold)
    notable = [_render_report_event(world, r) for r in records if r.severity >= _SEVERITY_THRESHOLD_YEARLY]

    # Location summaries
    loc_event_map: Dict[str, List[WorldEventRecord]] = {}
    for r in records:
        for loc_id in location_ids_for_record(r):
            loc_event_map.setdefault(loc_id, []).append(r)

    loc_entries: List[LocationReportEntry] = []
    for loc_id, loc_records in sorted(loc_event_map.items()):
        loc_name = world.location_name(loc_id)
        notable_loc = [
            _render_report_event(world, r)
            for r in loc_records
            if r.severity >= _SEVERITY_THRESHOLD_YEARLY
        ]
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
        location_entries=_sort_location_entries(loc_entries),
        total_events=len(records),
        deaths_this_year=deaths_this_year,
    )

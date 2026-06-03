"""UI view models derived from canonical WorldEventRecord data.

This module is intentionally small and additive: it provides stable
data shapes for screen rendering without exposing domain internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, TYPE_CHECKING

from ..event_rendering import render_event_record
from ..i18n import tr
from ..observation import (
    build_era_timeline_projection,
    build_route_status_projection,
    build_war_map_projection,
    build_world_change_report_projection,
)
from ..world_event_index import location_ids_for_record
from ..location_observation import (
    LocationObservationView,
    RumorSummaryView,
    build_location_observation_view,
    build_rumor_summary_views,
    render_rumor_brief,
)

if TYPE_CHECKING:
    from ..events import WorldEventRecord
    from ..world import World


__all__ = [
    "AdventureSummaryView",
    "ActiveWarView",
    "CurrentOccupationView",
    "CurrentRouteClosureView",
    "EraStatusView",
    "LocationHistoryView",
    "LocationObservationView",
    "MonthlyReportCardView",
    "NotificationItemView",
    "RumorSummaryView",
    "WorldChangeEntryView",
    "WorldChangeSummaryView",
    "WorldDashboardView",
    "YearlyReportCardView",
    "build_location_observation_view",
    "build_monthly_report_card_view",
    "build_notification_views",
    "build_rumor_summary_views",
    "build_world_dashboard_view",
    "build_yearly_report_card_view",
]


@dataclass
class AdventureSummaryView:
    title: str
    status: str
    origin: str
    destination: str
    policy: str = ""
    loot: List[str] = field(default_factory=list)
    injury: str = "none"


@dataclass
class LocationHistoryView:
    location_name: str
    region_type: str
    aliases: List[str] = field(default_factory=list)
    memorials: List[str] = field(default_factory=list)
    traces: List[str] = field(default_factory=list)
    recent_event_count: int = 0


@dataclass
class WorldChangeSummaryView:
    category: str
    count: int


@dataclass
class WorldChangeEntryView:
    record_id: str
    category: str
    text: str
    location_ids: List[str] = field(default_factory=list)
    year: int = 0
    month: int = 0
    day: int = 0


@dataclass
class ActiveWarView:
    record_id: str
    aggressor_faction_id: str
    target_faction_id: str
    text: str
    location_ids: List[str] = field(default_factory=list)
    year: int = 0
    month: int = 0
    day: int = 0


@dataclass
class CurrentOccupationView:
    record_id: str
    location_id: str
    previous_faction_id: str | None
    controlling_faction_id: str
    text: str
    year: int = 0
    month: int = 0
    day: int = 0


@dataclass
class CurrentRouteClosureView:
    route_id: str
    record_id: str
    from_location_id: str
    to_location_id: str
    text: str
    year: int = 0
    month: int = 0
    day: int = 0


@dataclass
class EraStatusView:
    era_id: str | None
    civilization_phase: str | None
    text: str


@dataclass
class MonthlyReportCardView:
    year: int
    month: int
    month_label: str = ""
    highlighted_characters: List[str] = field(default_factory=list)
    highlighted_locations: List[str] = field(default_factory=list)
    completed_adventures: List[str] = field(default_factory=list)
    new_memory_items: List[str] = field(default_factory=list)
    hot_rumors: List[str] = field(default_factory=list)
    world_changes: List[WorldChangeSummaryView] = field(default_factory=list)
    world_change_entries: List[WorldChangeEntryView] = field(default_factory=list)


@dataclass
class YearlyReportCardView:
    year: int
    total_events: int = 0
    highlighted_locations: List[str] = field(default_factory=list)
    world_changes: List[WorldChangeSummaryView] = field(default_factory=list)
    world_change_entries: List[WorldChangeEntryView] = field(default_factory=list)


@dataclass
class WorldDashboardView:
    world_name: str
    year: int
    month: int
    month_label: str
    alive_count: int
    deceased_count: int
    active_adventure_count: int
    pending_choice_count: int
    major_events: List[str] = field(default_factory=list)
    watched_actors: List[str] = field(default_factory=list)
    hot_rumors: List[str] = field(default_factory=list)
    dangerous_locations: List[str] = field(default_factory=list)
    world_changes: List[WorldChangeSummaryView] = field(default_factory=list)
    active_wars: List[ActiveWarView] = field(default_factory=list)
    current_occupations: List[CurrentOccupationView] = field(default_factory=list)
    current_route_closures: List[CurrentRouteClosureView] = field(default_factory=list)
    era_status: EraStatusView | None = None
    world_change_entries: List[WorldChangeEntryView] = field(default_factory=list)


@dataclass
class NotificationItemView:
    year: int
    month: int
    text: str
    kind: str
    location_id: str | None


def _render_view_event(record: "WorldEventRecord", world: "World" | None = None) -> str:
    return render_event_record(record, world=world)


def build_notification_views(
    records: List["WorldEventRecord"],
    world: "World" | None = None,
) -> List[NotificationItemView]:
    return [
        NotificationItemView(
            year=r.year,
            month=r.month,
            text=_render_view_event(r, world),
            kind=r.kind,
            location_id=r.location_id,
        )
        for r in records
    ]


def _records_for_year(world: "World", year: int) -> List["WorldEventRecord"]:
    if hasattr(world, "get_events_by_year"):
        return list(world.get_events_by_year(year))
    event_records = getattr(world, "event_records", [])
    return [record for record in event_records if record.year == year]


def _records_for_month(world: "World", year: int, month: int) -> List["WorldEventRecord"]:
    if hasattr(world, "get_events_by_month"):
        return list(world.get_events_by_month(year, month))
    return [record for record in getattr(world, "event_records", []) if record.year == year and record.month == month]


def _world_change_views(
    world: "World",
    records: List["WorldEventRecord"],
    *,
    year: int,
    month: int | None = None,
) -> tuple[List[WorldChangeSummaryView], List[WorldChangeEntryView]]:
    world_change_projection = build_world_change_report_projection(
        event_records=records,
        year=year,
        month=month,
    )
    records_by_id = {record.record_id: record for record in records}
    summaries = [
        WorldChangeSummaryView(category=count.category, count=count.count)
        for count in world_change_projection.counts_by_category
    ]
    entries = []
    for entry in world_change_projection.entries:
        record = records_by_id.get(entry.record_id)
        text = entry.description if record is None else _render_view_event(record, world)
        entries.append(
            WorldChangeEntryView(
                record_id=entry.record_id,
                category=entry.category,
                text=text,
                location_ids=list(entry.location_ids),
                year=entry.year,
                month=entry.month,
                day=entry.day,
            )
        )
    return summaries, entries


def _active_war_views(world: "World", records: List["WorldEventRecord"]) -> List[ActiveWarView]:
    projection = build_war_map_projection(event_records=records)
    records_by_id = {record.record_id: record for record in records}
    views: List[ActiveWarView] = []
    for entry in projection.active_wars:
        record = records_by_id.get(entry.record_id)
        text = entry.description if record is None else _render_view_event(record, world)
        views.append(
            ActiveWarView(
                record_id=entry.record_id,
                aggressor_faction_id=entry.aggressor_faction_id,
                target_faction_id=entry.target_faction_id,
                text=text,
                location_ids=list(entry.location_ids),
                year=entry.year,
                month=entry.month,
                day=entry.day,
            )
        )
    return views


def _current_occupation_views(world: "World", records: List["WorldEventRecord"]) -> List[CurrentOccupationView]:
    projection = build_war_map_projection(event_records=records)
    records_by_id = {record.record_id: record for record in records}
    views: List[CurrentOccupationView] = []
    for entry in projection.current_occupations:
        if entry.controlling_faction_id is None:
            continue
        record = records_by_id.get(entry.record_id)
        text = entry.description if record is None else _render_view_event(record, world)
        views.append(
            CurrentOccupationView(
                record_id=entry.record_id,
                location_id=entry.location_id,
                previous_faction_id=entry.previous_faction_id,
                controlling_faction_id=entry.controlling_faction_id,
                text=text,
                year=entry.year,
                month=entry.month,
                day=entry.day,
            )
        )
    return views


def _location_name(world: "World", location_id: str) -> str:
    if hasattr(world, "location_name"):
        return world.location_name(location_id)
    return location_id


def _current_route_closure_views(world: "World", records: List["WorldEventRecord"]) -> List[CurrentRouteClosureView]:
    records_by_id = {record.record_id: record for record in records}
    views: List[CurrentRouteClosureView] = []
    for route in getattr(world, "routes", []):
        if not getattr(route, "blocked", False):
            continue
        projection = build_route_status_projection(
            routes=getattr(world, "routes", []),
            event_records=records,
            route_id=route.route_id,
        )
        route_events = list(getattr(projection, "history"))
        latest = route_events[-1] if route_events else None
        record = records_by_id.get(latest.record_id) if latest is not None else None
        text = (
            _render_view_event(record, world)
            if record is not None
            else tr(
                "dashboard_route_closure_line",
                from_location=_location_name(world, projection.from_location_id),
                to_location=_location_name(world, projection.to_location_id),
            )
        )
        views.append(
            CurrentRouteClosureView(
                route_id=projection.route_id,
                record_id=latest.record_id if latest is not None else projection.route_id,
                from_location_id=projection.from_location_id,
                to_location_id=projection.to_location_id,
                text=text,
                year=latest.year if latest is not None else 0,
                month=latest.month if latest is not None else 0,
                day=latest.day if latest is not None else 0,
            )
        )
    return views


def _era_status_view(records: List["WorldEventRecord"]) -> EraStatusView | None:
    projection = build_era_timeline_projection(event_records=records)
    if projection.current_era_id is None and projection.current_civilization_phase is None:
        return None
    era = projection.current_era_id or tr("dashboard_era_unknown")
    phase = projection.current_civilization_phase or tr("dashboard_civilization_unknown")
    return EraStatusView(
        era_id=projection.current_era_id,
        civilization_phase=projection.current_civilization_phase,
        text=tr("dashboard_era_status_line", era=era, phase=phase),
    )


def build_monthly_report_card_view(world: "World", year: int, month: int) -> MonthlyReportCardView:
    records = _records_for_month(world, year, month)
    record_calendar_key = next(
        (record.calendar_key for record in records if getattr(record, "calendar_key", "")),
        "",
    )
    chars: Dict[str, int] = {}
    locs: Dict[str, int] = {}
    completed_adventures: List[str] = []
    new_memory: List[str] = []
    for r in records:
        if r.primary_actor_id:
            chars[r.primary_actor_id] = chars.get(r.primary_actor_id, 0) + 1
        for location_id in location_ids_for_record(r):
            locs[location_id] = locs.get(location_id, 0) + 1
        if r.kind in (
            "adventure_returned",
            "adventure_returned_injured",
            "adventure_retreated",
            "adventure_death",
        ):
            completed_adventures.append(_render_view_event(r, world))
        if r.kind in ("death", "adventure_death", "adventure_discovery"):
            new_memory.append(_render_view_event(r, world))

    char_lookup = {c.char_id: c.name for c in getattr(world, "characters", [])}
    highlights = [char_lookup.get(cid, cid) for cid, _ in sorted(chars.items(), key=lambda x: -x[1])[:3]]
    if hasattr(world, "location_name"):
        location_highlights = [world.location_name(lid) for lid, _ in sorted(locs.items(), key=lambda x: -x[1])[:3]]
    else:
        location_highlights = [lid for lid, _ in sorted(locs.items(), key=lambda x: -x[1])[:3]]
    if hasattr(world, "month_display_name_for_date"):
        try:
            month_label = world.month_display_name_for_date(
                year,
                month,
                calendar_key=record_calendar_key,
            )
        except TypeError:
            month_label = world.month_display_name_for_date(year, month)
    else:
        month_label = str(month)

    world_changes, world_change_entries = _world_change_views(world, records, year=year, month=month)

    hot_rumors: List[str] = []
    if hasattr(world, "event_records") and hasattr(world, "rumors") and hasattr(world, "location_name"):
        hot_rumors = [
            f"{rumor.description} ({tr(f'rumor_reliability_{rumor.reliability}')})"
            for rumor in getattr(world, "rumors", [])
            if not rumor.is_expired and rumor.year_created == year and rumor.month_created == month
        ][:2]

    return MonthlyReportCardView(
        year=year,
        month=month,
        month_label=month_label,
        highlighted_characters=highlights,
        highlighted_locations=location_highlights,
        completed_adventures=completed_adventures[:3],
        new_memory_items=new_memory[:3],
        hot_rumors=hot_rumors,
        world_changes=world_changes,
        world_change_entries=world_change_entries,
    )


def build_yearly_report_card_view(world: "World", year: int) -> YearlyReportCardView:
    records = _records_for_year(world, year)
    locs: Dict[str, int] = {}
    for record in records:
        for location_id in location_ids_for_record(record):
            locs[location_id] = locs.get(location_id, 0) + 1

    if hasattr(world, "location_name"):
        highlighted_locations = [
            world.location_name(location_id)
            for location_id, _ in sorted(locs.items(), key=lambda item: -item[1])[:5]
        ]
    else:
        highlighted_locations = [location_id for location_id, _ in sorted(locs.items(), key=lambda item: -item[1])[:5]]

    world_changes, world_change_entries = _world_change_views(world, records, year=year)
    return YearlyReportCardView(
        year=year,
        total_events=len(records),
        highlighted_locations=highlighted_locations,
        world_changes=world_changes,
        world_change_entries=world_change_entries,
    )


def build_world_dashboard_view(
    world: "World",
    *,
    current_month: int,
    pending_choice_count: int = 0,
) -> WorldDashboardView:
    """Build a compact observer dashboard from canonical world state."""
    records = list(getattr(world, "event_records", []))
    recent_records = sorted(
        records,
        key=lambda record: (
            record.severity,
            record.year,
            record.month,
            record.day,
            record.absolute_day,
            record.record_id,
        ),
        reverse=True,
    )
    notable_records = [record for record in recent_records if record.severity >= 3] or recent_records
    major_events = [_render_view_event(record, world) for record in notable_records[:5]]

    alive_count = sum(1 for character in getattr(world, "characters", []) if character.alive)
    deceased_count = sum(1 for character in getattr(world, "characters", []) if not character.alive)
    watched_actors = [
        _format_dashboard_actor(world, character)
        for character in getattr(world, "characters", [])
        if character.favorite or character.spotlighted or character.playable
    ][:5]
    dangerous_locations = [
        tr(
            "dashboard_location_status",
            location=location.canonical_name,
            danger=location.danger,
            rumor=location.rumor_heat,
        )
        for location in sorted(
            getattr(world, "grid", {}).values(),
            key=lambda item: (-item.danger, -item.rumor_heat, item.canonical_name.lower()),
        )[:5]
    ]
    hot_rumors = [
        render_rumor_brief(rumor)
        for rumor in _dashboard_hot_rumors(world, limit=5)
    ]
    month_label = _dashboard_month_label(world, current_month)
    world_changes, world_change_entries = _world_change_views(world, records, year=getattr(world, "year", 0))
    active_wars = _active_war_views(world, records)
    current_occupations = _current_occupation_views(world, records)
    current_route_closures = _current_route_closure_views(world, records)
    era_status = _era_status_view(records)

    return WorldDashboardView(
        world_name=getattr(world, "name", ""),
        year=getattr(world, "year", 0),
        month=current_month,
        month_label=month_label,
        alive_count=alive_count,
        deceased_count=deceased_count,
        active_adventure_count=len(getattr(world, "active_adventures", [])),
        pending_choice_count=pending_choice_count,
        major_events=major_events,
        watched_actors=watched_actors,
        hot_rumors=hot_rumors,
        dangerous_locations=dangerous_locations,
        world_changes=world_changes,
        active_wars=active_wars,
        current_occupations=current_occupations,
        current_route_closures=current_route_closures,
        era_status=era_status,
        world_change_entries=world_change_entries,
    )


def _dashboard_month_label(world: "World", current_month: int) -> str:
    if hasattr(world, "month_display_name_for_date"):
        try:
            return world.month_display_name_for_date(world.year, current_month)
        except TypeError:
            return world.month_display_name(current_month)
    return str(current_month)


def _dashboard_hot_rumors(world: "World", *, limit: int) -> List[RumorSummaryView]:
    """Return observer-dashboard rumors ordered by current attention value."""
    rumors = build_rumor_summary_views(world)

    def source_rumor_heat(rumor: RumorSummaryView) -> int:
        if not rumor.source_location_id or not hasattr(world, "get_location_by_id"):
            return 0
        location = world.get_location_by_id(rumor.source_location_id)
        return getattr(location, "rumor_heat", 0) if location is not None else 0

    rumors.sort(
        key=lambda rumor: (
            -rumor.spread_level,
            -source_rumor_heat(rumor),
            rumor.age_in_months,
            rumor.rumor_id,
        )
    )
    return rumors[: max(0, limit)]


def _format_dashboard_actor(world: "World", character) -> str:
    markers = []
    if character.favorite:
        markers.append(tr("dashboard_marker_favorite"))
    if character.spotlighted:
        markers.append(tr("dashboard_marker_spotlighted"))
    if character.playable:
        markers.append(tr("dashboard_marker_playable"))
    marker_text = f" [{' / '.join(markers)}]" if markers else ""
    injury = tr(f"injury_status_{character.injury_status}")
    life_status = tr("alive") if character.alive else tr("status_dead")
    return tr(
        "dashboard_actor_status",
        name=character.name,
        markers=marker_text,
        status=life_status,
        injury=injury,
        location=world.location_name(character.location_id),
    )

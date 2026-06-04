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
    "FollowUpActionView",
    "LocationHistoryView",
    "LocationObservationView",
    "MonthlyReportCardView",
    "NotificationItemView",
    "ReportHeadlineView",
    "ReportLocationThreadView",
    "ReportRumorThreadView",
    "ReportWatchedThreadView",
    "ReportWorldChangeThreadView",
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
class FollowUpActionView:
    key: str
    label: str
    target_type: str
    target_id: str
    location_id: str = ""
    record_id: str = ""


@dataclass
class ReportHeadlineView:
    record_id: str
    category: str
    text: str
    year: int = 0
    month: int = 0
    day: int = 0


@dataclass
class ReportLocationThreadView:
    location_id: str
    location_name: str
    event_count: int
    world_change_count: int
    headline: str = ""


@dataclass
class ReportWatchedThreadView:
    actor_id: str
    actor_name: str
    event_count: int
    headline: str = ""


@dataclass
class ReportWorldChangeThreadView:
    category: str
    count: int
    headline: str = ""
    location_names: List[str] = field(default_factory=list)


@dataclass
class ReportRumorThreadView:
    source_event_id: str
    source_event_text: str
    rumor_count: int
    source_location_name: str
    reliability: str
    spread_level: int
    headline: str = ""


@dataclass
class MonthlyReportCardView:
    year: int
    month: int
    month_label: str = ""
    headline_events: List[ReportHeadlineView] = field(default_factory=list)
    location_threads: List[ReportLocationThreadView] = field(default_factory=list)
    watched_threads: List[ReportWatchedThreadView] = field(default_factory=list)
    world_change_threads: List[ReportWorldChangeThreadView] = field(default_factory=list)
    rumor_threads: List[ReportRumorThreadView] = field(default_factory=list)
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
    headline_events: List[ReportHeadlineView] = field(default_factory=list)
    location_threads: List[ReportLocationThreadView] = field(default_factory=list)
    watched_threads: List[ReportWatchedThreadView] = field(default_factory=list)
    world_change_threads: List[ReportWorldChangeThreadView] = field(default_factory=list)
    rumor_threads: List[ReportRumorThreadView] = field(default_factory=list)
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
    follow_up_actions: List[FollowUpActionView] = field(default_factory=list)


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


def _world_change_thread_views(
    world: "World",
    entries: List[WorldChangeEntryView],
    *,
    limit: int,
) -> List[ReportWorldChangeThreadView]:
    grouped: Dict[str, List[WorldChangeEntryView]] = {}
    for entry in entries:
        grouped.setdefault(entry.category, []).append(entry)

    views: List[ReportWorldChangeThreadView] = []
    for category, category_entries in grouped.items():
        ranked_entries = sorted(
            category_entries,
            key=lambda entry: (entry.year, entry.month, entry.day, entry.record_id),
            reverse=True,
        )
        location_names: List[str] = []
        for entry in ranked_entries:
            for location_id in entry.location_ids:
                location_name = _location_name(world, location_id)
                if location_name not in location_names:
                    location_names.append(location_name)
                if len(location_names) >= 3:
                    break
            if len(location_names) >= 3:
                break
        views.append(
            ReportWorldChangeThreadView(
                category=category,
                count=len(category_entries),
                headline=ranked_entries[0].text if ranked_entries else "",
                location_names=location_names,
            )
        )
    views.sort(key=lambda view: (-view.count, view.category))
    return views[: max(0, limit)]


def _rumor_thread_views(
    world: "World",
    records: List["WorldEventRecord"],
    *,
    year: int,
    month: int | None = None,
    limit: int,
) -> List[ReportRumorThreadView]:
    rumors = list(getattr(world, "rumors", [])) + list(getattr(world, "rumor_archive", []))
    period_rumors = [
        rumor
        for rumor in rumors
        if getattr(rumor, "year_created", 0) == year
        and (month is None or getattr(rumor, "month_created", 0) == month)
    ]
    grouped: Dict[str, List[object]] = {}
    for rumor in period_rumors:
        source_event_id = str(getattr(rumor, "source_event_id", "") or getattr(rumor, "id", ""))
        if source_event_id:
            grouped.setdefault(source_event_id, []).append(rumor)

    records_by_id = {record.record_id: record for record in records}
    views: List[ReportRumorThreadView] = []
    for source_event_id, source_rumors in grouped.items():
        ranked_rumors = sorted(
            source_rumors,
            key=lambda rumor: (
                getattr(rumor, "spread_level", 0),
                -getattr(rumor, "age_in_months", 0),
                getattr(rumor, "month_created", 0),
                getattr(rumor, "id", ""),
            ),
            reverse=True,
        )
        headline_rumor = ranked_rumors[0]
        source_record = records_by_id.get(source_event_id)
        source_location_id = str(getattr(headline_rumor, "source_location_id", "") or "")
        views.append(
            ReportRumorThreadView(
                source_event_id=getattr(headline_rumor, "source_event_id", None) or "",
                source_event_text=_render_view_event(source_record, world) if source_record is not None else "",
                rumor_count=len(source_rumors),
                source_location_name=_location_name(world, source_location_id) if source_location_id else "",
                reliability=str(getattr(headline_rumor, "reliability", "plausible")),
                spread_level=int(getattr(headline_rumor, "spread_level", 0)),
                headline=str(getattr(headline_rumor, "description", "")),
            )
        )
    views.sort(
        key=lambda view: (
            -view.rumor_count,
            -view.spread_level,
            view.source_event_id or view.headline,
        )
    )
    return views[: max(0, limit)]


def _headline_category(record: "WorldEventRecord") -> str:
    if "world_change" in getattr(record, "tags", []):
        return "world_change"
    if record.kind.startswith("adventure_"):
        return "adventure"
    if record.kind in {"death", "birth", "marriage"}:
        return "life"
    if record.kind in {"battle", "duel"}:
        return "conflict"
    return "event"


def _headline_event_views(
    world: "World",
    records: List["WorldEventRecord"],
    *,
    limit: int,
) -> List[ReportHeadlineView]:
    ranked_records = sorted(
        records,
        key=lambda record: (
            "world_change" in getattr(record, "tags", []),
            record.severity,
            record.year,
            record.month,
            record.day,
            record.absolute_day,
            record.record_id,
        ),
        reverse=True,
    )
    return [
        ReportHeadlineView(
            record_id=record.record_id,
            category=_headline_category(record),
            text=_render_view_event(record, world),
            year=record.year,
            month=record.month,
            day=record.day,
        )
        for record in ranked_records[: max(0, limit)]
    ]


def _location_thread_views(
    world: "World",
    records: List["WorldEventRecord"],
    *,
    limit: int,
) -> List[ReportLocationThreadView]:
    grouped: Dict[str, List["WorldEventRecord"]] = {}
    for record in records:
        for location_id in location_ids_for_record(record):
            grouped.setdefault(location_id, []).append(record)

    views: List[ReportLocationThreadView] = []
    for location_id, location_records in grouped.items():
        ranked_records = sorted(
            location_records,
            key=lambda record: (
                "world_change" in getattr(record, "tags", []),
                record.severity,
                record.year,
                record.month,
                record.day,
                record.absolute_day,
                record.record_id,
            ),
            reverse=True,
        )
        views.append(
            ReportLocationThreadView(
                location_id=location_id,
                location_name=_location_name(world, location_id),
                event_count=len(location_records),
                world_change_count=sum(1 for record in location_records if "world_change" in record.tags),
                headline=_render_view_event(ranked_records[0], world) if ranked_records else "",
            )
        )
    views.sort(
        key=lambda view: (
            -view.world_change_count,
            -view.event_count,
            view.location_name.lower(),
            view.location_id,
        )
    )
    return views[: max(0, limit)]


def _actor_ids_for_record(record: "WorldEventRecord") -> List[str]:
    actor_ids: List[str] = []

    def add_actor_id(value: object) -> None:
        if isinstance(value, str) and value and value not in actor_ids:
            actor_ids.append(value)

    add_actor_id(record.primary_actor_id)
    for actor_id in record.secondary_actor_ids:
        add_actor_id(actor_id)
    render_actor_ids = record.render_params.get("actor_ids", [])
    if isinstance(render_actor_ids, list):
        for actor_id in render_actor_ids:
            add_actor_id(actor_id)
    return actor_ids


def _watched_character_lookup(world: "World") -> Dict[str, object]:
    return {
        character.char_id: character
        for character in getattr(world, "characters", [])
        if character.favorite or character.spotlighted or character.playable
    }


def _watched_thread_views(
    world: "World",
    records: List["WorldEventRecord"],
    *,
    limit: int,
) -> List[ReportWatchedThreadView]:
    watched_characters = _watched_character_lookup(world)
    grouped: Dict[str, List["WorldEventRecord"]] = {}
    for record in records:
        for actor_id in _actor_ids_for_record(record):
            if actor_id in watched_characters:
                grouped.setdefault(actor_id, []).append(record)

    views: List[ReportWatchedThreadView] = []
    for actor_id, actor_records in grouped.items():
        ranked_records = sorted(
            actor_records,
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
        character = watched_characters[actor_id]
        views.append(
            ReportWatchedThreadView(
                actor_id=actor_id,
                actor_name=getattr(character, "name", actor_id),
                event_count=len(actor_records),
                headline=_render_view_event(ranked_records[0], world) if ranked_records else "",
            )
        )
    views.sort(key=lambda view: (-view.event_count, view.actor_name.lower(), view.actor_id))
    return views[: max(0, limit)]


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


def _append_follow_up_action(actions: List[FollowUpActionView], action: FollowUpActionView) -> None:
    identity = (action.key, action.target_type, action.target_id, action.location_id, action.record_id)
    if any(
        (item.key, item.target_type, item.target_id, item.location_id, item.record_id) == identity
        for item in actions
    ):
        return
    actions.append(action)


def _character_follow_up_actions(world: "World", watched_characters: List[object]) -> List[FollowUpActionView]:
    actions: List[FollowUpActionView] = []
    for character in watched_characters:
        character_id = getattr(character, "char_id", "")
        location_id = getattr(character, "location_id", "")
        if not character_id:
            continue
        actions.append(
            FollowUpActionView(
                key="inspect_character",
                label=tr(
                    "dashboard_follow_up_inspect_character",
                    actor=getattr(character, "name", character_id),
                    location=_location_name(world, location_id) if location_id else "",
                ),
                target_type="character",
                target_id=character_id,
                location_id=location_id,
            )
        )
    return actions


def _route_follow_up_actions(world: "World", routes: List[CurrentRouteClosureView]) -> List[FollowUpActionView]:
    return [
        FollowUpActionView(
            key="inspect_route_closure",
            label=tr(
                "dashboard_follow_up_inspect_route_closure",
                from_location=_location_name(world, route.from_location_id),
                to_location=_location_name(world, route.to_location_id),
            ),
            target_type="route",
            target_id=route.route_id,
            location_id=route.from_location_id,
            record_id=route.record_id,
        )
        for route in routes
    ]


def _occupation_follow_up_actions(world: "World", occupations: List[CurrentOccupationView]) -> List[FollowUpActionView]:
    return [
        FollowUpActionView(
            key="inspect_occupation",
            label=tr(
                "dashboard_follow_up_inspect_occupation",
                location=_location_name(world, occupation.location_id),
            ),
            target_type="location",
            target_id=occupation.location_id,
            location_id=occupation.location_id,
            record_id=occupation.record_id,
        )
        for occupation in occupations
    ]


def _war_follow_up_actions(wars: List[ActiveWarView]) -> List[FollowUpActionView]:
    return [
        FollowUpActionView(
            key="review_active_war",
            label=tr("dashboard_follow_up_review_active_war", text=war.text),
            target_type="war",
            target_id=war.record_id,
            location_id=war.location_ids[0] if war.location_ids else "",
            record_id=war.record_id,
        )
        for war in wars
    ]


def _rumor_follow_up_actions(rumors: List[RumorSummaryView]) -> List[FollowUpActionView]:
    return [
        FollowUpActionView(
            key="review_rumor",
            label=tr("dashboard_follow_up_review_rumor", text=rumor.description),
            target_type="rumor",
            target_id=rumor.rumor_id,
            location_id=rumor.source_location_id or "",
            record_id=rumor.source_event_id or "",
        )
        for rumor in rumors
    ]


def _world_change_follow_up_actions(entries: List[WorldChangeEntryView]) -> List[FollowUpActionView]:
    return [
        FollowUpActionView(
            key="review_world_change",
            label=tr("dashboard_follow_up_review_world_change", text=entry.text),
            target_type="world_change",
            target_id=entry.record_id,
            location_id=entry.location_ids[0] if entry.location_ids else "",
            record_id=entry.record_id,
        )
        for entry in entries
    ]


def _dashboard_follow_up_actions(
    world: "World",
    *,
    watched_characters: List[object],
    hot_rumors: List[RumorSummaryView],
    active_wars: List[ActiveWarView],
    current_occupations: List[CurrentOccupationView],
    current_route_closures: List[CurrentRouteClosureView],
    world_change_entries: List[WorldChangeEntryView],
) -> List[FollowUpActionView]:
    actions: List[FollowUpActionView] = []
    action_groups = [
        _character_follow_up_actions(world, watched_characters),
        _route_follow_up_actions(world, current_route_closures),
        _occupation_follow_up_actions(world, current_occupations),
        _war_follow_up_actions(active_wars),
        _rumor_follow_up_actions(hot_rumors),
        _world_change_follow_up_actions(world_change_entries),
    ]
    for group in action_groups:
        for action in group:
            _append_follow_up_action(actions, action)
    return actions[:5]


def _dashboard_watched_characters(world: "World", *, limit: int) -> List[object]:
    return [
        character
        for character in getattr(world, "characters", [])
        if character.favorite or character.spotlighted or character.playable
    ][:limit]


def _dashboard_dangerous_locations(world: "World", *, limit: int) -> List[str]:
    return [
        tr(
            "dashboard_location_status",
            location=location.canonical_name,
            danger=location.danger,
            rumor=location.rumor_heat,
        )
        for location in sorted(
            getattr(world, "grid", {}).values(),
            key=lambda item: (-item.danger, -item.rumor_heat, item.canonical_name.lower()),
        )[:limit]
    ]


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
        headline_events=_headline_event_views(world, records, limit=3),
        location_threads=_location_thread_views(world, records, limit=3),
        watched_threads=_watched_thread_views(world, records, limit=3),
        world_change_threads=_world_change_thread_views(world, world_change_entries, limit=3),
        rumor_threads=_rumor_thread_views(world, records, year=year, month=month, limit=3),
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
        headline_events=_headline_event_views(world, records, limit=5),
        location_threads=_location_thread_views(world, records, limit=5),
        watched_threads=_watched_thread_views(world, records, limit=5),
        world_change_threads=_world_change_thread_views(world, world_change_entries, limit=5),
        rumor_threads=_rumor_thread_views(world, records, year=year, limit=5),
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
    watched_characters = _dashboard_watched_characters(world, limit=5)
    watched_actors = [_format_dashboard_actor(world, character) for character in watched_characters]
    dangerous_locations = _dashboard_dangerous_locations(world, limit=5)
    hot_rumor_views = _dashboard_hot_rumors(world, limit=5)
    hot_rumors = [render_rumor_brief(rumor) for rumor in hot_rumor_views]
    month_label = _dashboard_month_label(world, current_month)
    world_changes, world_change_entries = _world_change_views(world, records, year=getattr(world, "year", 0))
    active_wars = _active_war_views(world, records)
    current_occupations = _current_occupation_views(world, records)
    current_route_closures = _current_route_closure_views(world, records)
    era_status = _era_status_view(records)
    follow_up_actions = _dashboard_follow_up_actions(
        world,
        watched_characters=watched_characters,
        hot_rumors=hot_rumor_views,
        active_wars=active_wars,
        current_occupations=current_occupations,
        current_route_closures=current_route_closures,
        world_change_entries=world_change_entries,
    )

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
        follow_up_actions=follow_up_actions,
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
            not rumor.tracked,
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

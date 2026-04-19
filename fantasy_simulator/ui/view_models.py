"""UI view models derived from canonical WorldEventRecord data.

This module is intentionally small and additive: it provides stable
data shapes for screen rendering without exposing domain internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, TYPE_CHECKING

from ..i18n import tr, tr_term

if TYPE_CHECKING:
    from ..events import WorldEventRecord
    from ..world import World


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
class MonthlyReportCardView:
    year: int
    month: int
    month_label: str = ""
    highlighted_characters: List[str] = field(default_factory=list)
    highlighted_locations: List[str] = field(default_factory=list)
    completed_adventures: List[str] = field(default_factory=list)
    new_memory_items: List[str] = field(default_factory=list)
    hot_rumors: List[str] = field(default_factory=list)


@dataclass
class NotificationItemView:
    year: int
    month: int
    text: str
    kind: str
    location_id: str | None


@dataclass
class RumorSummaryView:
    rumor_id: str
    description: str
    reliability: str
    category: str = "event"
    source_location_id: str | None = None
    source_location_name: str = ""
    age_in_months: int = 0
    spread_level: int = 0


@dataclass
class LocationObservationView:
    location_id: str
    location_name: str
    region_type: str
    generated_endonym: str = ""
    aliases: List[str] = field(default_factory=list)
    memorials: List[str] = field(default_factory=list)
    traces: List[str] = field(default_factory=list)
    recent_events: List[str] = field(default_factory=list)
    connected_routes: List[str] = field(default_factory=list)
    rumors: List[RumorSummaryView] = field(default_factory=list)
    resident_names: List[str] = field(default_factory=list)


def build_notification_views(records: List["WorldEventRecord"]) -> List[NotificationItemView]:
    return [
        NotificationItemView(
            year=r.year,
            month=r.month,
            text=r.description,
            kind=r.kind,
            location_id=r.location_id,
        )
        for r in records
    ]


def build_monthly_report_card_view(world: "World", year: int, month: int) -> MonthlyReportCardView:
    event_records = getattr(world, "event_records", [])
    records = [r for r in event_records if r.year == year and r.month == month]
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
        if r.location_id:
            locs[r.location_id] = locs.get(r.location_id, 0) + 1
        if r.kind in (
            "adventure_returned",
            "adventure_returned_injured",
            "adventure_retreated",
            "adventure_death",
        ):
            completed_adventures.append(r.description)
        if r.kind in ("death", "adventure_death", "adventure_discovery"):
            new_memory.append(r.description)

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
    )


def build_rumor_summary_views(
    world: "World",
    *,
    location_id: str | None = None,
    include_archive: bool = False,
    limit: int | None = None,
) -> List[RumorSummaryView]:
    """Return rumor rows suitable for inspection UIs and query surfaces."""
    rumors = list(getattr(world, "rumors", []))
    if include_archive:
        rumors.extend(getattr(world, "rumor_archive", []))
    if location_id is not None:
        rumors = [rumor for rumor in rumors if rumor.source_location_id == location_id]

    rumors.sort(
        key=lambda rumor: (
            rumor.is_expired,
            rumor.age_in_months,
            -rumor.year_created,
            -rumor.month_created,
            rumor.id,
        )
    )
    if limit is not None:
        rumors = rumors[: max(0, limit)]

    return [
        RumorSummaryView(
            rumor_id=rumor.id,
            description=rumor.description,
            reliability=rumor.reliability,
            category=rumor.category,
            source_location_id=rumor.source_location_id,
            source_location_name=(
                world.location_name(rumor.source_location_id)
                if rumor.source_location_id
                else ""
            ),
            age_in_months=rumor.age_in_months,
            spread_level=rumor.spread_level,
        )
        for rumor in rumors
        if not rumor.is_expired
    ]


def build_location_observation_view(
    world: "World",
    location_id: str,
    *,
    rumor_limit: int = 3,
    event_limit: int = 5,
    route_limit: int = 5,
) -> LocationObservationView:
    """Return an inspectable snapshot of one location's current local context."""
    location = world.get_location_by_id(location_id)
    if location is None:
        raise ValueError(f"Unknown location id: {location_id}")

    memorials = [
        tr("memorial_entry", year=memorial.year, epitaph=memorial.epitaph)
        for memorial in world.get_memorials_for_location(location_id)
    ]
    traces = [
        trace.get("text", "")
        for trace in reversed(location.live_traces[-event_limit:])
        if trace.get("text")
    ]

    record_lookup = {record.record_id: record for record in getattr(world, "event_records", [])}
    recent_events = [
        tr("location_recent_event_entry", year=record.year, description=record.description)
        for record_id in reversed(location.recent_event_ids[-event_limit:])
        for record in [record_lookup.get(record_id)]
        if record is not None
    ]

    route_summaries: List[str] = []
    for route in world.get_routes_for_site(location_id)[:route_limit]:
        other_location_id = route.to_site_id if route.from_site_id == location_id else route.from_site_id
        blocked = f" {tr('route_blocked')}" if route.blocked else ""
        route_summaries.append(
            f"{world.location_name(other_location_id)} ({tr_term(route.route_type)}){blocked}"
        )

    residents = [
        character.name
        for character in world.get_characters_at_location(location_id)
    ]

    return LocationObservationView(
        location_id=location.id,
        location_name=location.canonical_name,
        region_type=tr_term(location.region_type),
        generated_endonym=location.generated_endonym,
        aliases=list(location.aliases),
        memorials=memorials,
        traces=traces,
        recent_events=recent_events,
        connected_routes=route_summaries,
        rumors=build_rumor_summary_views(world, location_id=location_id, limit=rumor_limit),
        resident_names=residents[:event_limit],
    )

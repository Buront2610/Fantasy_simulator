"""UI view models derived from canonical WorldEventRecord data.

This module is intentionally small and additive: it provides stable
data shapes for screen rendering without exposing domain internals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, TYPE_CHECKING

from ..i18n import tr
from ..location_observation import (
    LocationObservationView,
    RumorSummaryView,
    build_location_observation_view,
    build_rumor_summary_views,
)

if TYPE_CHECKING:
    from ..events import WorldEventRecord
    from ..world import World


__all__ = [
    "AdventureSummaryView",
    "LocationHistoryView",
    "LocationObservationView",
    "MonthlyReportCardView",
    "NotificationItemView",
    "RumorSummaryView",
    "build_location_observation_view",
    "build_monthly_report_card_view",
    "build_notification_views",
    "build_rumor_summary_views",
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

"""Headless report projection for PR-K world-change event records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from fantasy_simulator.event_models import WorldEventRecord

from ._record_helpers import record_location_ids, semantic_render_params


ROUTE_CHANGE_KINDS = {"route_blocked", "route_reopened"}
LOCATION_CHANGE_KINDS = {"location_renamed"}
TERRAIN_CHANGE_KINDS = {"terrain_cell_mutated"}
OCCUPATION_CHANGE_KINDS = {
    "location_faction_changed",
    "location_occupied",
    "location_liberated",
    "occupation_started",
    "occupation_ended",
}


@dataclass(frozen=True)
class WorldChangeReportEntry:
    """A canonical world-change event summarized for reporting."""

    record_id: str
    category: str
    kind: str
    year: int
    month: int
    day: int
    location_ids: tuple[str, ...]
    summary_key: str
    description: str
    render_params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class WorldChangeCategoryCount:
    """A stable category count for a world-change report projection."""

    category: str
    count: int


@dataclass(frozen=True)
class WorldChangeReportProjection:
    """Read model for monthly/yearly/headless world-change reports."""

    year: int | None
    month: int | None
    entries: tuple[WorldChangeReportEntry, ...]
    counts_by_category: tuple[WorldChangeCategoryCount, ...]
    affected_location_ids: tuple[str, ...]


def _change_category(record: WorldEventRecord) -> str | None:
    kind = record.kind.casefold()
    if kind in ROUTE_CHANGE_KINDS:
        return "route"
    if kind in LOCATION_CHANGE_KINDS:
        return "location"
    if kind in TERRAIN_CHANGE_KINDS or kind.startswith("terrain_"):
        return "terrain"
    if (
        kind in OCCUPATION_CHANGE_KINDS
        or kind.startswith("occupation_")
        or kind.endswith("_occupied")
        or kind.endswith("_liberated")
    ):
        return "occupation"
    if kind.startswith("war_") or kind.startswith("conflict_"):
        return "war"
    if kind.startswith("era_") or "era_shift" in kind:
        return "era"
    if kind.startswith("civilization_") or kind.startswith("civilisation_"):
        return "civilization"
    if "world_change" in record.tags:
        return "world_change"
    return None


def _period_matches(record: WorldEventRecord, *, year: int | None, month: int | None) -> bool:
    if year is not None and record.year != year:
        return False
    if month is not None and record.month != month:
        return False
    return True


def _append_unique(values: list[str], value: str) -> None:
    if value not in values:
        values.append(value)


def build_world_change_report_projection(
    *,
    event_records: Iterable[WorldEventRecord],
    year: int | None = None,
    month: int | None = None,
) -> WorldChangeReportProjection:
    """Build a world-change report projection using only canonical event records."""
    entries: list[WorldChangeReportEntry] = []
    counts: dict[str, int] = {}
    affected_location_ids: list[str] = []

    for record in event_records:
        if not _period_matches(record, year=year, month=month):
            continue
        category = _change_category(record)
        if category is None:
            continue
        location_ids = record_location_ids(record)
        for location_id in location_ids:
            _append_unique(affected_location_ids, location_id)
        counts[category] = counts.get(category, 0) + 1
        entries.append(
            WorldChangeReportEntry(
                record_id=record.record_id,
                category=category,
                kind=record.kind,
                year=record.year,
                month=record.month,
                day=record.day,
                location_ids=location_ids,
                summary_key=record.summary_key,
                render_params=semantic_render_params(record),
                description=record.description,
            )
        )

    return WorldChangeReportProjection(
        year=year,
        month=month,
        entries=tuple(entries),
        counts_by_category=tuple(
            WorldChangeCategoryCount(category=category, count=count)
            for category, count in sorted(counts.items())
        ),
        affected_location_ids=tuple(affected_location_ids),
    )

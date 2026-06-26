"""Readable event-log projection for CLI screens and live simulation."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterable, List

from ..world_event.rendering import render_event_record
from ..i18n import tr
from .combat_log_presenter import combat_round_count_for_event


_COMBAT_KINDS = frozenset({"battle", "battle_fatal", "war_battle"})
_ADVENTURE_PREFIXES = ("adventure_",)
_WORLD_PREFIXES = ("route_", "location_", "war_", "era_", "civilization_")
_WORLD_KINDS = frozenset({"war_declared", "war_ended", "natural_disaster"})
_LIFE_KINDS = frozenset({"birth", "death", "adventure_death", "battle_fatal", "condition_worsened", "dying_rescued"})
_RELATIONSHIP_KINDS = frozenset({"meeting", "romance", "marriage", "child_born"})


@dataclass(frozen=True)
class EventLogRenderEntry:
    """Small read model for a single event-log line group."""

    record: Any
    date_label: str
    category: str
    headline: str
    actor_names: tuple[str, ...]
    location_name: str
    severity: int
    detail_lines: tuple[str, ...]


def build_event_log_entries(sim: Any, records: Iterable[Any]) -> tuple[EventLogRenderEntry, ...]:
    """Build display-ready event-log entries from canonical event records."""
    world = getattr(sim, "world", None)
    return tuple(_build_entry(sim, world, record) for record in records)


def event_log_summary_line(entries: Iterable[EventLogRenderEntry], *, total_count: int) -> str:
    """Return a compact summary for a rendered event-log slice."""
    entries = tuple(entries)
    counts = Counter(entry.category for entry in entries)
    breakdown = ", ".join(
        tr(f"event_log_category_count_{category}", count=count)
        for category, count in sorted(counts.items())
    )
    if not breakdown:
        breakdown = tr("event_log_summary_no_breakdown")
    return tr("event_log_summary", shown=len(entries), total=total_count, breakdown=breakdown)


def render_event_log_entry_lines(
    entry: EventLogRenderEntry,
    *,
    include_date_divider: bool,
) -> List[str]:
    """Render one event-log entry as multiple readable lines."""
    lines: List[str] = []
    if include_date_divider:
        lines.append(tr("event_log_date_divider", date=entry.date_label))
    lines.append(
        tr(
            "event_log_entry_line",
            category=tr(f"event_log_category_{entry.category}"),
            headline=entry.headline,
        )
    )
    meta = _meta_line(entry)
    if meta:
        lines.append(meta)
    lines.extend(entry.detail_lines)
    return lines


def render_live_event_lines(sim: Any, records: Iterable[Any]) -> List[str]:
    """Render new records for the live daily stream."""
    entries = build_event_log_entries(sim, records)
    lines: List[str] = []
    for entry in entries:
        lines.append(
            tr(
                "live_event_stream_line",
                date=entry.date_label,
                category=tr(f"event_log_category_{entry.category}"),
                headline=entry.headline,
            )
        )
        for detail in entry.detail_lines[:2]:
            lines.append(tr("live_event_stream_detail", detail=detail))
    return lines


def _build_entry(sim: Any, world: Any, record: Any) -> EventLogRenderEntry:
    category = classify_event_record(record)
    details = _detail_lines(world, record)
    return EventLogRenderEntry(
        record=record,
        date_label=_date_label(record),
        category=category,
        headline=render_event_record(record, world=world),
        actor_names=tuple(_actor_names(world, record)),
        location_name=_location_name(world, getattr(record, "location_id", None)),
        severity=int(getattr(record, "severity", 0) or 0),
        detail_lines=tuple(details),
    )


def classify_event_record(record: Any) -> str:
    """Return the event-log lane used for grouping and live labels."""
    kind = str(getattr(record, "kind", "") or "")
    tags = {str(tag) for tag in getattr(record, "tags", []) if isinstance(tag, str)}
    if combat_round_count_for_event(record) or kind in _COMBAT_KINDS or "combat" in tags:
        return "combat"
    if kind.startswith(_ADVENTURE_PREFIXES):
        return "adventure"
    if kind.startswith(_WORLD_PREFIXES) or kind in _WORLD_KINDS:
        return "world"
    if kind in _LIFE_KINDS:
        return "life"
    if kind in _RELATIONSHIP_KINDS:
        return "relationship"
    if kind == "discovery":
        return "discovery"
    return "general"


def _detail_lines(world: Any, record: Any) -> List[str]:
    details: List[str] = []
    cause_text = _cause_text(world, record)
    if cause_text:
        details.append(cause_text)
    relationship_text = _relationship_text(record)
    if relationship_text:
        details.append(relationship_text)
    combat_rounds = combat_round_count_for_event(record)
    if combat_rounds:
        details.append(tr("event_log_combat_summary", rounds=combat_rounds))
    return details


def _cause_text(world: Any, record: Any) -> str:
    cause_ids = list(getattr(record, "cause_event_ids", []))
    if not cause_ids:
        return ""
    get_causes = getattr(world, "get_event_causes", None)
    causes = []
    if callable(get_causes):
        causes = [render_event_record(cause, world=world) for cause in get_causes(getattr(record, "record_id", ""))]
    if not causes:
        return tr("event_log_causes_unavailable")
    return tr("event_log_caused_by", events=" | ".join(causes))


def _relationship_text(record: Any) -> str:
    render_params = getattr(record, "render_params", {})
    if not isinstance(render_params, dict):
        return ""
    parts = []
    if "personality_affinity" in render_params:
        parts.append(
            tr(
                "event_log_personality_reason",
                affinity=render_params.get("personality_affinity", 0),
                factors=render_params.get("personality_factors", tr("event_log_no_personality_factors")),
                delta=render_params.get("relationship_delta", 0),
            )
        )
    catalyst_bonus = int(render_params.get("relationship_catalyst_bonus", 0) or 0)
    if catalyst_bonus:
        parts.append(
            tr(
                "event_log_catalyst_reason",
                bonus=catalyst_bonus,
                factors=render_params.get("relationship_catalyst_factors", tr("event_log_no_catalyst_factors")),
            )
        )
    if not parts:
        return ""
    return tr("event_log_relationship_reason", reasons=" / ".join(parts))


def _actor_names(world: Any, record: Any) -> List[str]:
    actor_ids = []
    primary = getattr(record, "primary_actor_id", None)
    if isinstance(primary, str) and primary:
        actor_ids.append(primary)
    actor_ids.extend(
        actor_id for actor_id in getattr(record, "secondary_actor_ids", [])
        if isinstance(actor_id, str) and actor_id
    )
    names = []
    getter = getattr(world, "get_character_by_id", None)
    for actor_id in dict.fromkeys(actor_ids):
        character = getter(actor_id) if callable(getter) else None
        names.append(getattr(character, "name", actor_id) if character is not None else actor_id)
    return names


def _location_name(world: Any, location_id: Any) -> str:
    if not isinstance(location_id, str) or not location_id:
        return ""
    resolver = getattr(world, "location_name", None)
    if callable(resolver):
        try:
            return str(resolver(location_id))
        except (KeyError, TypeError, ValueError):
            return location_id
    return location_id


def _meta_line(entry: EventLogRenderEntry) -> str:
    parts = []
    if entry.actor_names:
        parts.append(tr("event_log_meta_actors", actors=", ".join(entry.actor_names[:4])))
    if entry.location_name:
        parts.append(tr("event_log_meta_location", location=entry.location_name))
    if entry.severity:
        parts.append(tr("event_log_meta_severity", severity=entry.severity))
    if not parts:
        return ""
    return tr("event_log_meta_line", meta=" | ".join(parts))


def _date_label(record: Any) -> str:
    year = int(getattr(record, "year", 0) or 0)
    month = int(getattr(record, "month", 0) or 0)
    day = int(getattr(record, "day", 0) or 0)
    if day > 0 and month > 0:
        return tr("event_log_prefix_day", year=year, month=month, day=day)
    if month > 0:
        return tr("event_log_prefix_month", year=year, month=month)
    return tr("event_log_prefix", year=year)

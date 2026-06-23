"""Long-run retention policy for canonical history and rumor archives."""

from __future__ import annotations

from typing import Any

from ..character import MAX_RELATION_TAG_SOURCE_EVENTS
from ..event_models import WorldEventRecord


EVENT_HISTORY_TARGET_RECORDS = 2500
EVENT_HISTORY_RECENT_YEARS = 15
RUMOR_ARCHIVE_TARGET_RECORDS = 600
COMPLETED_ADVENTURE_TARGET_RECORDS = 180
COMPLETED_ADVENTURE_RECENT_YEARS = 80
RECENT_ADVENTURE_LOG_LINES = 40
OLD_ADVENTURE_LOG_LINES = 12
RECENT_ADVENTURE_EVENT_REFS = 24
OLD_ADVENTURE_EVENT_REFS = 4
RECENT_ADVENTURE_COMBAT_LOGS = 12
OLD_ADVENTURE_COMBAT_LOGS = 2

_ESSENTIAL_EVENT_KINDS = {
    "birth",
    "death",
    "adventure_death",
    "marriage",
    "immigration",
    "war_declared",
    "war_battle",
    "war_ended",
    "location_renamed",
    "location_faction_changed",
    "location_occupied",
    "location_liberated",
    "route_blocked",
    "route_reopened",
    "terrain_cell_mutated",
    "era_shifted",
    "civilization_phase_drifted",
}
_ESSENTIAL_KIND_PREFIXES = (
    "war_",
    "route_",
    "terrain_",
    "location_",
    "occupation_",
)
_ESSENTIAL_TAGS = {"world_change", "war", "battle"}


def compact_world_history(
    world: Any,
    *,
    max_event_records: int = EVENT_HISTORY_TARGET_RECORDS,
    recent_years: int = EVENT_HISTORY_RECENT_YEARS,
    max_rumor_archive: int = RUMOR_ARCHIVE_TARGET_RECORDS,
    max_completed_adventures: int = COMPLETED_ADVENTURE_TARGET_RECORDS,
    completed_adventure_recent_years: int = COMPLETED_ADVENTURE_RECENT_YEARS,
) -> None:
    """Apply bounded long-run retention without changing the save schema."""
    _compact_relation_tag_sources(world)
    _compact_completed_adventures(
        world,
        max_records=max_completed_adventures,
        recent_years=completed_adventure_recent_years,
    )
    _compact_event_records(world, max_records=max_event_records, recent_years=recent_years)
    _compact_rumor_archive(world, max_records=max_rumor_archive)


def _compact_event_records(world: Any, *, max_records: int, recent_years: int) -> None:
    records = list(getattr(world, "event_records", []))
    if len(records) <= max_records:
        return
    current_year = int(getattr(world, "year", 0))
    by_id = {record.record_id: record for record in records}
    retained_ids = _cause_closure(_referenced_event_ids(world), by_id)
    retained = [record for record in records if record.record_id in retained_ids]
    remaining_slots = max(0, max_records - len(retained))
    if remaining_slots:
        retained_ids.update(
            record.record_id
            for record in sorted(
                (record for record in records if record.record_id not in retained_ids),
                key=lambda record: _retention_score(
                    record,
                    current_year=current_year,
                    recent_years=recent_years,
                ),
                reverse=True,
            )[:remaining_slots]
        )
    retained_ids = _cause_closure(retained_ids, by_id)
    world.event_records = [record for record in records if record.record_id in retained_ids]
    _repair_recent_event_ids(world, retained_ids)
    event_index = getattr(world, "_event_index", None)
    if event_index is not None:
        event_index.ensure_record_ids_current(world.event_records)


def _is_required_record(record: WorldEventRecord, *, current_year: int, recent_years: int) -> bool:
    if current_year - record.year <= recent_years:
        return True
    if record.kind in _ESSENTIAL_EVENT_KINDS or record.kind.startswith(_ESSENTIAL_KIND_PREFIXES):
        return True
    if _ESSENTIAL_TAGS.intersection(record.tags):
        return True
    return False


def _referenced_event_ids(world: Any) -> set[str]:
    ids: set[str] = set()
    for location in getattr(world, "grid", {}).values():
        ids.update(getattr(location, "recent_event_ids", []))
    for arc in getattr(world, "world_arcs", []):
        cause_event_id = getattr(arc, "cause_event_id", None)
        if cause_event_id:
            ids.add(cause_event_id)
        ids.update(getattr(arc, "related_event_ids", []))
    for rumor in list(getattr(world, "rumors", [])) + list(getattr(world, "rumor_archive", [])):
        source_event_id = getattr(rumor, "source_event_id", None)
        if isinstance(source_event_id, str) and source_event_id:
            ids.add(source_event_id)
        ids.update(
            record_id for record_id in getattr(rumor, "related_event_ids", [])
            if isinstance(record_id, str) and record_id
        )
    for run in list(getattr(world, "active_adventures", [])) + list(getattr(world, "completed_adventures", [])):
        ids.update(getattr(run, "related_event_ids", []))
    return ids


def _cause_closure(required_ids: set[str], by_id: dict[str, WorldEventRecord]) -> set[str]:
    retained = set(required_ids)
    pending = list(required_ids)
    while pending:
        record = by_id.get(pending.pop())
        if record is None:
            continue
        for cause_id in _record_cause_ids(record):
            if cause_id in by_id and cause_id not in retained:
                retained.add(cause_id)
                pending.append(cause_id)
    return retained


def _record_cause_ids(record: WorldEventRecord) -> list[str]:
    ids = [
        cause_id for cause_id in getattr(record, "cause_event_ids", [])
        if isinstance(cause_id, str) and cause_id
    ]
    cause_id = record.render_params.get("cause_event_id")
    if isinstance(cause_id, str) and cause_id:
        ids.append(cause_id)
    return list(dict.fromkeys(ids))


def _retention_score(
    record: WorldEventRecord,
    *,
    current_year: int,
    recent_years: int,
) -> tuple[int, int, int, int, int]:
    return (
        1 if _is_required_record(record, current_year=current_year, recent_years=recent_years) else 0,
        int(record.severity),
        1 if record.primary_actor_id else 0,
        int(record.year),
        int(record.absolute_day),
    )


def _repair_recent_event_ids(world: Any, retained_ids: set[str]) -> None:
    for location in getattr(world, "grid", {}).values():
        recent_ids = getattr(location, "recent_event_ids", [])
        if recent_ids:
            location.recent_event_ids = [record_id for record_id in recent_ids if record_id in retained_ids]


def _compact_rumor_archive(world: Any, *, max_records: int) -> None:
    archive = list(getattr(world, "rumor_archive", []))
    if len(archive) <= max_records:
        return
    world.rumor_archive = sorted(
        archive,
        key=lambda rumor: (
            1 if getattr(rumor, "tracked", False) else 0,
            int(getattr(rumor, "year_created", 0)),
            int(getattr(rumor, "created_absolute_day", 0)),
            int(getattr(rumor, "spread_level", 0)),
        ),
        reverse=True,
    )[:max_records]


def _compact_completed_adventures(world: Any, *, max_records: int, recent_years: int) -> None:
    completed = list(getattr(world, "completed_adventures", []))
    if not completed:
        return
    current_year = int(getattr(world, "year", 0))
    for run in completed:
        _trim_completed_adventure_payload(run, current_year=current_year, recent_years=recent_years)
    if len(completed) <= max_records:
        return
    retained_ids = {
        run.adventure_id
        for run in sorted(
            completed,
            key=lambda run: _completed_adventure_retention_score(
                run,
                current_year=current_year,
                recent_years=recent_years,
            ),
            reverse=True,
        )[:max_records]
    }
    world.completed_adventures = [run for run in completed if run.adventure_id in retained_ids]


def _trim_completed_adventure_payload(run: Any, *, current_year: int, recent_years: int) -> None:
    recent = _is_recent_adventure(run, current_year=current_year, recent_years=recent_years)
    line_limit = RECENT_ADVENTURE_LOG_LINES if recent else OLD_ADVENTURE_LOG_LINES
    event_limit = RECENT_ADVENTURE_EVENT_REFS if recent else OLD_ADVENTURE_EVENT_REFS
    combat_limit = RECENT_ADVENTURE_COMBAT_LOGS if recent else OLD_ADVENTURE_COMBAT_LOGS
    for attr in ("summary_log", "detail_log", "loot_summary"):
        values = list(getattr(run, attr, []))
        if len(values) > line_limit:
            setattr(run, attr, values[-line_limit:])
    related_event_ids = list(getattr(run, "related_event_ids", []))
    if len(related_event_ids) > event_limit:
        run.related_event_ids = related_event_ids[-event_limit:]
    combat_logs = list(getattr(run, "combat_logs", []))
    if len(combat_logs) > combat_limit:
        run.combat_logs = combat_logs[-combat_limit:]


def _completed_adventure_retention_score(
    run: Any,
    *,
    current_year: int,
    recent_years: int,
) -> tuple[int, int, int, int]:
    resolved_year = _adventure_resolved_year(run)
    return (
        1 if _is_recent_adventure(run, current_year=current_year, recent_years=recent_years) else 0,
        1 if getattr(run, "outcome", None) == "death" else 0,
        int(resolved_year),
        int(getattr(run, "steps_taken", 0)),
    )


def _is_recent_adventure(run: Any, *, current_year: int, recent_years: int) -> bool:
    return current_year - _adventure_resolved_year(run) <= recent_years


def _adventure_resolved_year(run: Any) -> int:
    value = getattr(run, "resolution_year", None)
    if value is None:
        value = getattr(run, "year_started", 0)
    if value is None:
        return 0
    return int(value)


def _compact_relation_tag_sources(world: Any) -> None:
    for character in getattr(world, "characters", []):
        sources = getattr(character, "relation_tag_sources", None)
        if not isinstance(sources, dict):
            continue
        for key, values in list(sources.items()):
            if not isinstance(values, list):
                del sources[key]
                continue
            sources[key] = [
                value for value in values[-MAX_RELATION_TAG_SOURCE_EVENTS:]
                if isinstance(value, str) and value
            ]

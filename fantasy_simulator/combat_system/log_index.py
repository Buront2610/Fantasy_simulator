"""Read models for lightweight combat-log browsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


COMBAT_EVENT_KINDS = frozenset({"battle", "battle_fatal", "war_battle"})


@dataclass(frozen=True)
class CombatLogEntryView:
    source_id: str
    source_kind: str
    year: int
    month: int
    day: int
    location_id: str
    title: str
    actor_ids: tuple[str, ...]
    round_count: int
    winner_id: str = ""
    loser_id: str = ""
    source: Any = None


def build_combat_log_index(world: Any, *, character_id: str | None = None) -> tuple[CombatLogEntryView, ...]:
    """Return compact combat entries from canonical events and completed adventures."""
    character_filter = character_id or ""
    entries: list[CombatLogEntryView] = []
    for record in getattr(world, "event_records", []):
        entry = _entry_from_event(record)
        if entry is not None and _matches_character(entry, character_filter):
            entries.append(entry)
    for run in [*getattr(world, "completed_adventures", []), *getattr(world, "active_adventures", [])]:
        for entry in _entries_from_adventure(run):
            if _matches_character(entry, character_filter):
                entries.append(entry)
    return tuple(sorted(entries, key=_sort_key, reverse=True))


def _entry_from_event(record: Any) -> CombatLogEntryView | None:
    combat_log = _combat_log_from_mapping(getattr(record, "render_params", {}))
    if not combat_log and getattr(record, "kind", "") not in COMBAT_EVENT_KINDS:
        return None
    actor_ids = _event_actor_ids(record, combat_log)
    if not combat_log:
        return None
    return CombatLogEntryView(
        source_id=str(getattr(record, "record_id", "")),
        source_kind=str(getattr(record, "kind", "")),
        year=int(getattr(record, "year", 0) or 0),
        month=int(getattr(record, "month", 0) or 0),
        day=int(getattr(record, "day", 0) or 0),
        location_id=str(getattr(record, "location_id", "") or _render_location_id(record)),
        title=str(getattr(record, "description", "") or getattr(record, "kind", "")),
        actor_ids=actor_ids,
        round_count=len(combat_log),
        winner_id=str(getattr(record, "render_params", {}).get("winner_id", "")),
        loser_id=str(getattr(record, "render_params", {}).get("loser_id", "")),
        source=record,
    )


def _entries_from_adventure(run: Any) -> list[CombatLogEntryView]:
    entries: list[CombatLogEntryView] = []
    for index, raw in enumerate(getattr(run, "combat_logs", []), 1):
        if not isinstance(raw, dict):
            continue
        combat_log = _combat_log_from_mapping(raw)
        if not combat_log:
            continue
        actor_ids = _adventure_actor_ids(run, raw, combat_log)
        entries.append(
            CombatLogEntryView(
                source_id=f"{getattr(run, 'adventure_id', '')}:combat:{index}",
                source_kind="adventure_combat",
                year=int(getattr(run, "year_started", 0) or 0),
                month=0,
                day=0,
                location_id=str(raw.get("location_id", "")),
                title=str(raw.get("hazard_name", "") or getattr(run, "destination", "") or "adventure"),
                actor_ids=actor_ids,
                round_count=len(combat_log),
                winner_id=str(raw.get("winner_id", "")),
                loser_id=str(raw.get("loser_id", "")),
                source=raw,
            )
        )
    return entries


def _combat_log_from_mapping(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    raw_log = value.get("combat_log")
    if not isinstance(raw_log, list):
        return []
    return [entry for entry in raw_log if isinstance(entry, dict)]


def _event_actor_ids(record: Any, combat_log: list[dict[str, Any]]) -> tuple[str, ...]:
    actor_ids = []
    primary_actor_id = getattr(record, "primary_actor_id", "")
    if isinstance(primary_actor_id, str) and primary_actor_id:
        actor_ids.append(primary_actor_id)
    actor_ids.extend(
        actor_id for actor_id in getattr(record, "secondary_actor_ids", [])
        if isinstance(actor_id, str) and actor_id
    )
    actor_ids.extend(_combat_actor_ids(combat_log))
    return tuple(dict.fromkeys(actor_ids))


def _adventure_actor_ids(run: Any, raw: dict[str, Any], combat_log: list[dict[str, Any]]) -> tuple[str, ...]:
    actor_ids = []
    member_id = raw.get("member_id")
    if isinstance(member_id, str) and member_id:
        actor_ids.append(member_id)
    leader_id = getattr(run, "character_id", "")
    if isinstance(leader_id, str) and leader_id:
        actor_ids.append(leader_id)
    actor_ids.extend(
        member_id for member_id in getattr(run, "member_ids", [])
        if isinstance(member_id, str) and member_id
    )
    actor_ids.extend(_combat_actor_ids(combat_log))
    return tuple(dict.fromkeys(actor_ids))


def _combat_actor_ids(combat_log: list[dict[str, Any]]) -> list[str]:
    actor_ids: list[str] = []
    for entry in combat_log:
        for key in ("actor_id", "target_id"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                actor_ids.append(value)
    return actor_ids


def _render_location_id(record: Any) -> str:
    render_params = getattr(record, "render_params", {})
    if isinstance(render_params, dict):
        value = render_params.get("location_id")
        if isinstance(value, str):
            return value
    return ""


def _matches_character(entry: CombatLogEntryView, character_id: str) -> bool:
    return not character_id or character_id in entry.actor_ids


def _sort_key(entry: CombatLogEntryView) -> tuple[int, int, int, str]:
    return (entry.year, entry.month, entry.day, entry.source_id)

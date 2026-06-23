"""World-health metrics shared by pytest checks and ad-hoc playtests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..world_persistence.serializer import serialize_world_state


def all_characters(world: Any) -> list[Any]:
    """Return world characters regardless of legacy list/dict storage shape."""
    characters = getattr(world, "characters", [])
    if isinstance(characters, dict):
        return list(characters.values())
    return list(characters)


def active_adventure_ids(world: Any) -> set[str]:
    return {
        run.adventure_id
        for run in getattr(world, "active_adventures", [])
    }


def stranded_living_adventurers(world: Any) -> list[Any]:
    """Return living characters pointing at a non-active adventure."""
    active_ids = active_adventure_ids(world)
    return [
        char
        for char in all_characters(world)
        if getattr(char, "alive", True)
        and getattr(char, "active_adventure_id", None)
        and char.active_adventure_id not in active_ids
    ]


def dangling_adventure_member_ids(world: Any) -> list[tuple[str, str]]:
    """Return ``(adventure_id, member_id)`` pairs for missing party members."""
    known_ids = {char.char_id for char in all_characters(world)}
    dangling: list[tuple[str, str]] = []
    runs = list(getattr(world, "active_adventures", [])) + list(getattr(world, "completed_adventures", []))
    for run in runs:
        for member_id in getattr(run, "member_ids", []):
            if member_id not in known_ids:
                dangling.append((run.adventure_id, member_id))
    return dangling


def collect_world_health_metrics(world: Any) -> dict[str, Any]:
    stranded = stranded_living_adventurers(world)
    dangling_members = dangling_adventure_member_ids(world)
    characters = all_characters(world)
    completed_adventures = list(getattr(world, "completed_adventures", []))
    event_records = list(getattr(world, "event_records", []))
    adventure_logs = _adventure_combat_logs(world)
    combat_logs = _combat_logs(event_records) + adventure_logs
    combat_metrics = _combat_metrics(combat_logs, event_records, adventure_logs)
    cause_metrics = _cause_metrics(event_records)
    footprint_metrics = _history_footprint_metrics(world, event_records)
    return {
        "year": getattr(world, "year", None),
        "characters": len(characters),
        "alive": sum(1 for char in characters if getattr(char, "alive", True)),
        "active_adventures": len(getattr(world, "active_adventures", [])),
        "completed_adventures": len(completed_adventures),
        "marriage_count": sum(1 for record in event_records if getattr(record, "kind", "") == "marriage"),
        "birth_count": sum(1 for record in event_records if getattr(record, "kind", "") == "birth"),
        "immigration_count": sum(1 for record in event_records if getattr(record, "kind", "") == "immigration"),
        **footprint_metrics,
        **combat_metrics,
        **cause_metrics,
        "adventure_outcomes": {
            outcome: sum(1 for run in completed_adventures if getattr(run, "outcome", None) == outcome)
            for outcome in sorted({getattr(run, "outcome", None) for run in completed_adventures}, key=str)
        },
        "stranded_living_adventurers": [
            {
                "char_id": char.char_id,
                "name": char.name,
                "active_adventure_id": char.active_adventure_id,
            }
            for char in stranded
        ],
        "dangling_adventure_member_ids": [
            {"adventure_id": adventure_id, "member_id": member_id}
            for adventure_id, member_id in dangling_members
        ],
    }


def _json_size_bytes(payload: Any) -> int:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    return len(text.encode("utf-8"))


def _history_footprint_metrics(world: Any, event_records: list[Any]) -> dict[str, Any]:
    event_payloads = [record.to_dict() for record in event_records if hasattr(record, "to_dict")]
    active_rumors = [
        rumor.to_dict() for rumor in getattr(world, "rumors", [])
        if hasattr(rumor, "to_dict")
    ]
    archived_rumors = [
        rumor.to_dict() for rumor in getattr(world, "rumor_archive", [])
        if hasattr(rumor, "to_dict")
    ]
    event_bytes = _json_size_bytes(event_payloads)
    archive_bytes = _json_size_bytes(archived_rumors)
    world_bytes = _json_size_bytes(serialize_world_state(world))
    return {
        "event_record_count": len(event_payloads),
        "event_records_json_bytes": event_bytes,
        "event_record_average_bytes": round(event_bytes / len(event_payloads), 2) if event_payloads else 0.0,
        "active_rumor_count": len(active_rumors),
        "active_rumors_json_bytes": _json_size_bytes(active_rumors),
        "rumor_archive_count": len(archived_rumors),
        "rumor_archive_json_bytes": archive_bytes,
        "rumor_archive_average_bytes": round(archive_bytes / len(archived_rumors), 2) if archived_rumors else 0.0,
        "estimated_world_save_json_bytes": world_bytes,
    }


def _cause_metrics(event_records: list[Any]) -> dict[str, Any]:
    record_ids = {
        record_id for record in event_records
        for record_id in [getattr(record, "record_id", "")]
        if isinstance(record_id, str) and record_id
    }
    cause_event_ids = []
    dangling_cause_event_ids = []
    for record in event_records:
        record_cause_ids = [
            cause_event_id for cause_event_id in getattr(record, "cause_event_ids", [])
            if isinstance(cause_event_id, str) and cause_event_id
        ]
        render_params = getattr(record, "render_params", {})
        if isinstance(render_params, dict):
            cause_event_id = render_params.get("cause_event_id")
            if isinstance(cause_event_id, str) and cause_event_id:
                record_cause_ids.append(cause_event_id)
        for cause_event_id in dict.fromkeys(record_cause_ids):
            cause_event_ids.append(cause_event_id)
            if cause_event_id not in record_ids:
                dangling_cause_event_ids.append({
                    "record_id": getattr(record, "record_id", ""),
                    "kind": getattr(record, "kind", ""),
                    "cause_event_id": cause_event_id,
                })
    return {
        "causal_event_count": len(cause_event_ids),
        "dangling_cause_event_ids": dangling_cause_event_ids,
    }


def _combat_metrics(
    combat_logs: list[list[dict[str, Any]]],
    event_records: list[Any],
    adventure_logs: list[list[dict[str, Any]]],
) -> dict[str, Any]:
    combat_round_counts = [len(log) for log in combat_logs if log]
    total_rounds = sum(combat_round_counts)
    return {
        "combat_event_count": len(combat_logs),
        "combat_round_count": total_rounds,
        "average_combat_rounds": (
            round(total_rounds / len(combat_round_counts), 2)
            if combat_round_counts else 0.0
        ),
        "magic_combat_action_count": sum(
            1 for log in combat_logs for entry in log if str(entry.get("action_kind", "")).startswith("spell")
        ),
        "war_battle_count": sum(1 for record in event_records if getattr(record, "kind", "") == "war_battle"),
        "adventure_combat_count": len(adventure_logs),
    }


def _combat_logs(event_records: list[Any]) -> list[list[dict[str, Any]]]:
    logs: list[list[dict[str, Any]]] = []
    for record in event_records:
        log = _combat_log_from_record(record)
        if log:
            logs.append(log)
    return logs


def _adventure_combat_logs(world: Any) -> list[list[dict[str, Any]]]:
    logs: list[list[dict[str, Any]]] = []
    runs = list(getattr(world, "active_adventures", [])) + list(getattr(world, "completed_adventures", []))
    for run in runs:
        for entry in getattr(run, "combat_logs", []):
            if not isinstance(entry, dict):
                continue
            log = entry.get("combat_log")
            if isinstance(log, list):
                normalized = [item for item in log if isinstance(item, dict)]
                if normalized:
                    logs.append(normalized)
    return logs


def _combat_log_from_record(record: Any) -> list[dict[str, Any]]:
    render_params = getattr(record, "render_params", {})
    if isinstance(render_params, dict) and isinstance(render_params.get("combat_log"), list):
        return [
            entry for entry in render_params["combat_log"]
            if isinstance(entry, dict)
        ]
    return []


def write_world_health_report(metrics: dict[str, Any], path: str | Path) -> None:
    """Write metrics as deterministic JSON for local health comparisons."""
    Path(path).write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def assert_no_stranded_living_adventurers(world: Any) -> None:
    stranded = stranded_living_adventurers(world)
    assert not stranded, (
        "[world-health] living characters have dangling active_adventure_id "
        f"(count={len(stranded)}, ids={[char.char_id for char in stranded]}). "
        "Meaning: survivors can be excluded from future adventures and random events. "
        "Check death_resolution.resolve_active_adventure_for_death and party cleanup."
    )


def assert_no_dangling_adventure_members(world: Any) -> None:
    dangling = dangling_adventure_member_ids(world)
    assert not dangling, (
        "[world-health] adventures reference missing characters "
        f"(count={len(dangling)}, refs={dangling[:5]}). "
        "Meaning: adventure history cannot be projected safely."
    )


def assert_population_floor(world: Any, minimum_alive: int) -> None:
    alive_count = sum(1 for char in all_characters(world) if getattr(char, "alive", True))
    assert alive_count >= minimum_alive, (
        f"[world-health] alive={alive_count} (expected >= {minimum_alive}). "
        "Meaning: population maintenance is not keeping the world observable over long runs."
    )

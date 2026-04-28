"""Legacy event adapter migration helpers."""

from __future__ import annotations

import json
from typing import Any, Dict

from .migration_context import calendar_key_for_data


def record_from_legacy_history_item(
    item: Dict[str, Any],
    *,
    index: int,
    calendar_key: str,
) -> Dict[str, Any]:
    affected = list(item.get("affected_characters", []))
    return {
        "record_id": f"legacy_history_{index:06d}",
        "kind": item.get("event_type", "generic"),
        "year": item.get("year", 0),
        "month": 1,
        "day": 1,
        "absolute_day": 0,
        "location_id": None,
        "primary_actor_id": affected[0] if affected else None,
        "secondary_actor_ids": affected[1:],
        "description": item.get("description", ""),
        "severity": 1,
        "visibility": "public",
        "calendar_key": calendar_key,
        "tags": [],
        "impacts": [],
        "legacy_event_result": dict(item),
        "legacy_event_log_entry": None,
    }


def record_from_legacy_event_log_entry(
    entry: str,
    *,
    index: int,
    year: int,
    calendar_key: str,
) -> Dict[str, Any]:
    return {
        "record_id": f"legacy_event_log_{index:06d}",
        "kind": "legacy_event_log",
        "year": year,
        "month": 1,
        "day": 1,
        "absolute_day": 0,
        "location_id": None,
        "primary_actor_id": None,
        "secondary_actor_ids": [],
        "description": entry,
        "severity": 1,
        "visibility": "public",
        "calendar_key": calendar_key,
        "tags": ["legacy_event_log"],
        "impacts": [],
        "legacy_event_result": {
            "description": entry,
            "affected_characters": [],
            "stat_changes": {},
            "event_type": "legacy_event_log",
            "year": year,
            "metadata": {"legacy_event_log_entry": True},
        },
        "legacy_event_log_entry": entry,
    }


def canonicalize_legacy_event_adapters(data: Dict[str, Any]) -> None:
    world_data = data.setdefault("world", {})
    event_records = list(world_data.setdefault("event_records", []))
    history = list(data.get("history", []))
    event_log = list(world_data.get("event_log", []))
    calendar_key = calendar_key_for_data(data)

    canonical_records = list(event_records)
    existing_history_payload_counts: Dict[str, int] = {}
    existing_legacy_log_counts: Dict[str, int] = {}
    for record in canonical_records:
        record_id = str(record.get("record_id", ""))
        if record_id.startswith("legacy_history_"):
            payload = record.get("legacy_event_result")
            if payload is not None:
                payload_key = json.dumps(payload, sort_keys=True)
                existing_history_payload_counts[payload_key] = existing_history_payload_counts.get(payload_key, 0) + 1
        elif record_id.startswith("legacy_event_log_"):
            entry = record.get("legacy_event_log_entry")
            if entry is not None:
                existing_legacy_log_counts[entry] = existing_legacy_log_counts.get(entry, 0) + 1

    history_index = sum(
        1 for record in canonical_records if str(record.get("record_id", "")).startswith("legacy_history_")
    )
    event_log_index = sum(
        1 for record in canonical_records if str(record.get("record_id", "")).startswith("legacy_event_log_")
    )

    for item in history:
        payload_key = json.dumps(item, sort_keys=True)
        if existing_history_payload_counts.get(payload_key, 0) > 0:
            existing_history_payload_counts[payload_key] -= 1
            continue
        history_index += 1
        canonical_records.append(
            record_from_legacy_history_item(item, index=history_index, calendar_key=calendar_key)
        )

    year = int(world_data.get("year", 0))
    for entry in event_log:
        if existing_legacy_log_counts.get(entry, 0) > 0:
            existing_legacy_log_counts[entry] -= 1
            continue
        event_log_index += 1
        canonical_records.append(
            record_from_legacy_event_log_entry(entry, index=event_log_index, year=year, calendar_key=calendar_key)
        )

    if canonical_records:
        world_data["event_records"] = canonical_records

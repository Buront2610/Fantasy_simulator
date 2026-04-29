"""Canonical world-event state mutation helpers.

TD-3 responsibility split: isolate event-driven world state mutations from
``World`` orchestration.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Mapping, Optional, Protocol, Set

from .event_models import WorldEventRecord
from .rule_override_resolution import (
    DEFAULT_EVENT_IMPACT_RULES,
    clone_default_event_impact_rules as _clone_default_event_impact_rules,
    validate_event_impact_rules,
)


class SupportsEventIndex(Protocol):
    id: str
    safety: int
    mood: int
    danger: int
    traffic: int
    rumor_heat: int
    prosperity: int
    road_condition: int
    recent_event_ids: List[str]


def apply_event_impact_to_location(
    *,
    kind: str,
    location_id: Optional[str],
    location_index: Mapping[str, SupportsEventIndex],
    clamp_state: Callable[[int], int],
    impact_rules: Optional[Mapping[str, Mapping[str, int]]] = None,
) -> List[Dict[str, int | str]]:
    """Apply event impact rules to one location and return impact records."""
    impacts: List[Dict[str, int | str]] = []
    if location_id is None:
        return impacts

    location = location_index.get(location_id)
    if location is None:
        return impacts

    rules = DEFAULT_EVENT_IMPACT_RULES if impact_rules is None else impact_rules
    validate_event_impact_rules(rules)
    deltas = rules.get(kind, {})
    for attr, delta in deltas.items():
        old = getattr(location, attr)
        new_val = clamp_state(old + delta)
        setattr(location, attr, new_val)
        impacts.append({
            "target_type": "location",
            "target_id": location_id,
            "attribute": attr,
            "old_value": old,
            "new_value": new_val,
            "delta": new_val - old,
        })
    return impacts


def append_canonical_event_record(
    *,
    record: WorldEventRecord,
    event_records: List[WorldEventRecord],
    location_index: Mapping[str, SupportsEventIndex],
    grid: Mapping[object, SupportsEventIndex],
    max_event_records: int,
    existing_record_ids: Optional[Set[str]] = None,
) -> WorldEventRecord:
    """Append an event record and maintain related per-location indexes.

    Contract:
    - Mutates ``event_records`` and location ``recent_event_ids`` in place.
    - If ``record.location_id`` is unknown, a normalized copy (``location_id=None``) is stored.

    Returns the canonical record instance actually stored in ``event_records``.
    """
    stored_record = record
    if record.location_id is not None and record.location_id not in location_index:
        cloned = record.to_dict()
        cloned["location_id"] = None
        stored_record = WorldEventRecord.from_dict(cloned)

    if existing_record_ids is not None:
        duplicate = stored_record.record_id in existing_record_ids
    else:
        duplicate = any(existing.record_id == stored_record.record_id for existing in event_records)
    if duplicate:
        raise ValueError(f"Duplicate event record ID: {stored_record.record_id!r}")

    event_records.append(stored_record)
    if existing_record_ids is not None:
        existing_record_ids.add(stored_record.record_id)

    if stored_record.location_id is not None:
        location = location_index[stored_record.location_id]
        location.recent_event_ids.append(stored_record.record_id)
        location.recent_event_ids = location.recent_event_ids[-12:]

    if len(event_records) <= max_event_records:
        return stored_record

    del event_records[:-max_event_records]
    surviving_ids = {item.record_id for item in event_records}
    if existing_record_ids is not None:
        existing_record_ids.intersection_update(surviving_ids)
    for location in grid.values():
        if location.recent_event_ids:
            location.recent_event_ids = [
                record_id
                for record_id in location.recent_event_ids
                if record_id in surviving_ids
            ]

    return stored_record


def clone_default_event_impact_rules() -> Dict[str, Dict[str, int]]:
    """Compatibility wrapper around the shared rule-table owner."""
    return _clone_default_event_impact_rules()

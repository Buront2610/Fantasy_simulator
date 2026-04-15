"""Canonical world-event state mutation helpers.

TD-3 responsibility split: isolate event-driven world state mutations from
``World`` orchestration.
"""

from __future__ import annotations

from typing import Callable, Dict, List, MutableMapping, Optional, Protocol

from .event_models import WorldEventRecord


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


# Event kind -> location state impact (design doc §5.5)
EVENT_IMPACT_RULES: Dict[str, Dict[str, int]] = {
    "death": {"safety": -3, "mood": -5, "rumor_heat": +10},
    "battle_fatal": {"safety": -5, "mood": -8, "danger": +5, "rumor_heat": +15},
    "battle": {"safety": -2, "mood": -3, "danger": +3, "rumor_heat": +5},
    "discovery": {"rumor_heat": +5, "traffic": +3},
    "marriage": {"mood": +3},
    "adventure_death": {"danger": +5, "mood": -5, "rumor_heat": +10},
    "adventure_discovery": {"rumor_heat": +5, "traffic": +2, "prosperity": +2},
    "adventure_started": {"traffic": +2},
    "adventure_returned": {"mood": +2, "traffic": +1},
    "journey": {"traffic": +1},
    "injury_recovery": {"mood": +1},
    "condition_worsened": {"mood": -2, "rumor_heat": +3},
    "dying_rescued": {"mood": +3, "rumor_heat": +5},
}


def apply_event_impact_to_location(
    *,
    kind: str,
    location_id: Optional[str],
    location_index: MutableMapping[str, SupportsEventIndex],
    clamp_state: Callable[[int], int],
) -> List[Dict[str, int | str]]:
    """Apply event impact rules to one location and return impact records."""
    impacts: List[Dict[str, int | str]] = []
    if location_id is None:
        return impacts

    location = location_index.get(location_id)
    if location is None:
        return impacts

    deltas = EVENT_IMPACT_RULES.get(kind, {})
    for attr, delta in deltas.items():
        old = getattr(location, attr, None)
        if old is None:
            continue
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
    location_index: MutableMapping[str, SupportsEventIndex],
    grid: MutableMapping[object, SupportsEventIndex],
    max_event_records: int,
) -> None:
    """Append an event record and maintain related per-location indexes.

    Contract:
    - Mutates ``event_records`` and location ``recent_event_ids`` in place.
    - If ``record.location_id`` is unknown, it is normalized to ``None`` (destructive update).
    """
    if record.location_id not in location_index:
        record.location_id = None

    event_records.append(record)

    if record.location_id is not None:
        location = location_index[record.location_id]
        location.recent_event_ids.append(record.record_id)
        location.recent_event_ids = location.recent_event_ids[-12:]

    if len(event_records) <= max_event_records:
        return

    del event_records[:-max_event_records]
    surviving_ids = {item.record_id for item in event_records}
    for location in grid.values():
        if location.recent_event_ids:
            location.recent_event_ids = [
                record_id
                for record_id in location.recent_event_ids
                if record_id in surviving_ids
            ]

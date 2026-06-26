"""Location-state pressure helpers for PR-K world changes."""

from __future__ import annotations

from typing import Any, Mapping, Protocol, cast

from ..world_event.models import WorldEventRecord
from ..world_event.rendering import render_event_record
from ..i18n import tr
from ..world_location.state import clamp_state


class SupportsConflictPressureLocation(Protocol):
    prosperity: int
    danger: int
    rumor_heat: int
    safety: int
    mood: int
    road_condition: int
    traffic: int
    live_traces: list[dict[str, Any]]


def _append_world_trace(
    location: SupportsConflictPressureLocation,
    *,
    text: str,
    year: int,
    max_live_traces: int,
) -> None:
    location.live_traces.append({"year": year, "char_name": "world", "text": text})
    if len(location.live_traces) > max_live_traces:
        location.live_traces = location.live_traces[-max_live_traces:]


def apply_war_pressure_to_locations(
    record: WorldEventRecord,
    *,
    location_index: Mapping[str, SupportsConflictPressureLocation],
    max_live_traces: int,
    world_context: Any,
) -> None:
    """Apply deterministic local pressure from a war event after canonical recording succeeds."""
    location_ids = record.render_params.get("location_ids", ())
    if not isinstance(location_ids, list):
        return
    if record.kind == "war_declared":
        deltas = {"danger": 15, "rumor_heat": 25, "safety": -10, "mood": -10}
        trace_key = "live_trace_war_declared"
    elif record.kind == "war_ended":
        deltas = {"danger": -8, "rumor_heat": 12, "safety": 6, "mood": 8}
        trace_key = "live_trace_war_ended"
    else:
        return
    description = render_event_record(record, world=cast(Any, world_context))
    for location_id in location_ids:
        if not isinstance(location_id, str):
            continue
        location = location_index.get(location_id)
        if location is None:
            continue
        for attr, delta in deltas.items():
            setattr(location, attr, clamp_state(int(getattr(location, attr)) + delta))
        _append_world_trace(
            location,
            text=tr(trace_key, description=description, year=record.year),
            year=record.year,
            max_live_traces=max_live_traces,
        )


def _record_endpoint_location_ids(record: WorldEventRecord) -> list[str]:
    endpoint_ids = record.render_params.get("endpoint_location_ids")
    if isinstance(endpoint_ids, list):
        candidates = endpoint_ids
    else:
        candidates = [
            record.render_params.get("from_location_id"),
            record.render_params.get("to_location_id"),
        ]
    location_ids: list[str] = []
    seen: set[str] = set()
    for location_id in candidates:
        if isinstance(location_id, str) and location_id not in seen:
            seen.add(location_id)
            location_ids.append(location_id)
    return location_ids


def apply_route_pressure_to_locations(
    record: WorldEventRecord,
    *,
    location_index: Mapping[str, SupportsConflictPressureLocation],
    max_live_traces: int,
    world_context: Any,
) -> None:
    """Apply endpoint pressure from a route closure or reopening after recording succeeds."""
    location_ids = _record_endpoint_location_ids(record)
    if not location_ids:
        return
    if record.kind == "route_blocked":
        deltas = {"road_condition": -15, "traffic": -10, "rumor_heat": 8, "mood": -3, "danger": 3}
        trace_key = "live_trace_route_blocked"
    elif record.kind == "route_reopened":
        deltas = {"road_condition": 12, "traffic": 8, "rumor_heat": 5, "mood": 3, "danger": -2, "safety": 2}
        trace_key = "live_trace_route_reopened"
    else:
        return

    description = render_event_record(record, world=cast(Any, world_context))
    for location_id in location_ids:
        location = location_index.get(location_id)
        if location is None:
            continue
        for attr, delta in deltas.items():
            setattr(location, attr, clamp_state(int(getattr(location, attr)) + delta))
        _append_world_trace(
            location,
            text=tr(trace_key, description=description, year=record.year),
            year=record.year,
            max_live_traces=max_live_traces,
        )


def apply_rename_pressure_to_location(
    record: WorldEventRecord,
    *,
    location_index: Mapping[str, SupportsConflictPressureLocation],
    max_live_traces: int,
    world_context: Any,
) -> None:
    """Apply local attention pressure from a location rename after recording succeeds."""
    location_id = record.render_params.get("location_id")
    if not isinstance(location_id, str):
        return
    location = location_index.get(location_id)
    if location is None:
        return

    location.rumor_heat = clamp_state(location.rumor_heat + 12)
    location.traffic = clamp_state(location.traffic + 4)
    location.mood = clamp_state(location.mood + 2)
    description = render_event_record(record, world=cast(Any, world_context))
    _append_world_trace(
        location,
        text=tr("live_trace_location_renamed", description=description, year=record.year),
        year=record.year,
        max_live_traces=max_live_traces,
    )


def apply_occupation_pressure_to_location(
    record: WorldEventRecord,
    *,
    location_index: Mapping[str, SupportsConflictPressureLocation],
    max_live_traces: int,
    world_context: Any,
) -> None:
    """Apply local pressure from a controlling-faction transition after recording succeeds."""
    location_id = record.render_params.get("location_id")
    if not isinstance(location_id, str):
        return
    location = location_index.get(location_id)
    if location is None:
        return
    new_faction_id = record.render_params.get("new_faction_id")
    if new_faction_id is None:
        location.danger = clamp_state(location.danger - 5)
        location.rumor_heat = clamp_state(location.rumor_heat + 8)
        location.safety = clamp_state(location.safety + 8)
        location.mood = clamp_state(location.mood + 8)
    else:
        location.danger = clamp_state(location.danger + 8)
        location.rumor_heat = clamp_state(location.rumor_heat + 12)
        location.safety = clamp_state(location.safety - 8)
        location.mood = clamp_state(location.mood - 6)
    description = render_event_record(record, world=cast(Any, world_context))
    _append_world_trace(
        location,
        text=tr("live_trace_occupation_changed", description=description, year=record.year),
        year=record.year,
        max_live_traces=max_live_traces,
    )


_BIOME_PRESSURE: dict[str, dict[str, int]] = {
    "forest": {"danger": 6, "rumor_heat": 8, "mood": 4},
    "swamp": {"danger": 10, "rumor_heat": 6, "safety": -8, "road_condition": -10},
    "desert": {"danger": 8, "safety": -6, "mood": -6, "road_condition": -8},
    "mountain": {"danger": 8, "safety": -4, "road_condition": -12},
    "hills": {"danger": 4, "road_condition": -4},
    "river": {"rumor_heat": 4, "road_condition": -6},
    "coast": {"traffic": 4, "rumor_heat": 4, "mood": 2},
    "plains": {"danger": -4, "safety": 4, "road_condition": 4},
}


def _terrain_delta_for_record(record: WorldEventRecord) -> dict[str, int]:
    params = record.render_params
    deltas = dict(_BIOME_PRESSURE.get(str(params.get("new_biome", "")), {}))
    if "elevation" in params.get("changed_attributes", ()):
        old_elevation = int(params.get("old_elevation", 128))
        new_elevation = int(params.get("new_elevation", old_elevation))
        if new_elevation > old_elevation:
            deltas["road_condition"] = deltas.get("road_condition", 0) - min(10, (new_elevation - old_elevation) // 8)
        elif new_elevation < old_elevation:
            deltas["road_condition"] = deltas.get("road_condition", 0) + min(8, (old_elevation - new_elevation) // 10)
    if "moisture" in params.get("changed_attributes", ()):
        old_moisture = int(params.get("old_moisture", 128))
        new_moisture = int(params.get("new_moisture", old_moisture))
        if new_moisture > old_moisture + 30:
            deltas["rumor_heat"] = deltas.get("rumor_heat", 0) + 4
            deltas["road_condition"] = deltas.get("road_condition", 0) - 4
        elif new_moisture < old_moisture - 30:
            deltas["mood"] = deltas.get("mood", 0) - 4
    if "temperature" in params.get("changed_attributes", ()):
        old_temperature = int(params.get("old_temperature", 128))
        new_temperature = int(params.get("new_temperature", old_temperature))
        if abs(new_temperature - old_temperature) >= 40:
            deltas["danger"] = deltas.get("danger", 0) + 4
            deltas["mood"] = deltas.get("mood", 0) - 4
    return deltas


def apply_terrain_pressure_to_location(
    record: WorldEventRecord,
    *,
    location_index: Mapping[str, SupportsConflictPressureLocation],
    max_live_traces: int,
    world_context: Any,
) -> None:
    """Apply local pressure from a terrain mutation after canonical recording succeeds."""
    location_id = record.render_params.get("location_id")
    if not isinstance(location_id, str):
        return
    location = location_index.get(location_id)
    if location is None:
        return

    for attr, delta in _terrain_delta_for_record(record).items():
        setattr(location, attr, clamp_state(int(getattr(location, attr)) + delta))

    description = render_event_record(record, world=cast(Any, world_context))
    _append_world_trace(
        location,
        text=tr("live_trace_terrain_changed", description=description, year=record.year),
        year=record.year,
        max_live_traces=max_live_traces,
    )


def apply_era_pressure_to_locations(
    record: WorldEventRecord,
    *,
    location_index: Mapping[str, SupportsConflictPressureLocation],
    max_live_traces: int,
    world_context: Any,
) -> None:
    """Apply broad local pressure from an era shift after canonical recording succeeds."""
    if record.kind != "era_shifted":
        return
    description = render_event_record(record, world=cast(Any, world_context))
    for location in location_index.values():
        location.prosperity = clamp_state(location.prosperity + 3)
        location.rumor_heat = clamp_state(location.rumor_heat + 20)
        location.traffic = clamp_state(location.traffic + 6)
        location.mood = clamp_state(location.mood + 4)
        _append_world_trace(
            location,
            text=tr("live_trace_era_shifted", description=description, year=record.year),
            year=record.year,
            max_live_traces=max_live_traces,
        )


def _civilization_score_deltas(record: WorldEventRecord) -> dict[str, int]:
    deltas: dict[str, int] = {}
    score_changes = record.render_params.get("score_changes", ())
    if isinstance(score_changes, list):
        for score_change in score_changes:
            if not isinstance(score_change, Mapping):
                continue
            attr = score_change.get("score_key")
            old_value = score_change.get("old_value")
            new_value = score_change.get("new_value")
            if not isinstance(attr, str) or attr not in {"prosperity", "safety", "traffic", "mood"}:
                continue
            if not isinstance(old_value, int) or not isinstance(new_value, int):
                continue
            deltas[attr] = new_value - old_value
    return deltas


def apply_civilization_pressure_to_locations(
    record: WorldEventRecord,
    *,
    location_index: Mapping[str, SupportsConflictPressureLocation],
    max_live_traces: int,
    world_context: Any,
) -> None:
    """Apply world-score drift to all known locations after canonical recording succeeds."""
    deltas = _civilization_score_deltas(record)
    if not deltas and record.render_params.get("old_civilization_phase") == record.render_params.get(
        "new_civilization_phase"
    ):
        return

    description = render_event_record(record, world=cast(Any, world_context))
    safety_delta = deltas.get("safety", 0)
    danger_delta = 0
    if safety_delta < 0:
        danger_delta = min(20, abs(safety_delta) // 2)
    elif safety_delta > 0:
        danger_delta = -min(10, safety_delta // 2)

    for location in location_index.values():
        for attr, delta in deltas.items():
            setattr(location, attr, clamp_state(int(getattr(location, attr)) + delta))
        if danger_delta:
            location.danger = clamp_state(location.danger + danger_delta)
        location.rumor_heat = clamp_state(location.rumor_heat + 10)
        _append_world_trace(
            location,
            text=tr("live_trace_civilization_drifted", description=description, year=record.year),
            year=record.year,
            max_live_traces=max_live_traces,
        )

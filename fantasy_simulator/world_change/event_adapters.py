"""Adapters from PR-K domain events to canonical event records."""

from __future__ import annotations

from typing import Any, Callable

from fantasy_simulator.event_models import LOCATION_TAG_PREFIX, WorldEventRecord

from .domain_events import (
    CivilizationPhaseDrifted,
    EraShifted,
    LocationOccupationChanged,
    LocationRenamed,
    RouteStatusChanged,
    TerrainCellMutated,
    WorldScoreChanged,
)


def route_status_render_params(event: RouteStatusChanged) -> dict[str, Any]:
    """Return semantic render params for a route status event."""
    return {
        "route_id": str(event.route_id),
        "from_location_id": str(event.from_location_id),
        "to_location_id": str(event.to_location_id),
        "endpoint_location_ids": event.endpoint_location_ids,
    }


def route_status_fallback_description(
    event: RouteStatusChanged,
    *,
    location_name: Callable[[str], str],
) -> str:
    """Return a non-localized compatibility fallback for route status events."""
    route_verb = "blocked" if event.new_blocked else "reopened"
    from_location = location_name(str(event.from_location_id))
    to_location = location_name(str(event.to_location_id))
    return f"The route from {from_location} to {to_location} was {route_verb}."


def route_status_changed_to_record(
    event: RouteStatusChanged,
    *,
    description: str,
) -> WorldEventRecord:
    """Adapt a route status domain event into the canonical event history model."""
    render_params = route_status_render_params(event)
    return WorldEventRecord(
        kind=event.kind,
        year=event.year,
        month=event.month,
        day=event.day,
        location_id=str(event.from_location_id),
        description=description,
        severity=2,
        visibility="public",
        calendar_key=event.calendar_key,
        summary_key=event.summary_key,
        render_params=render_params,
        tags=[
            "world_change",
            f"{LOCATION_TAG_PREFIX}{event.from_location_id}",
            f"{LOCATION_TAG_PREFIX}{event.to_location_id}",
        ],
        impacts=[
            {
                "target_type": "route",
                "target_id": str(event.route_id),
                "attribute": "blocked",
                "old_value": event.old_blocked,
                "new_value": event.new_blocked,
            }
        ],
    )


def location_rename_render_params(event: LocationRenamed) -> dict[str, Any]:
    """Return semantic render params for a location rename event."""
    return {
        "location_id": str(event.location_id),
        "old_name": event.old_name,
        "new_name": event.new_name,
    }


def location_rename_fallback_description(event: LocationRenamed) -> str:
    """Return a non-localized compatibility fallback for location rename events."""
    return f"{event.old_name} was renamed {event.new_name}."


def location_renamed_to_record(
    event: LocationRenamed,
    *,
    description: str,
) -> WorldEventRecord:
    """Adapt a location rename domain event into the canonical event history model."""
    return WorldEventRecord(
        kind=event.kind,
        year=event.year,
        month=event.month,
        day=event.day,
        location_id=str(event.location_id),
        description=description,
        severity=2,
        visibility="public",
        calendar_key=event.calendar_key,
        summary_key=event.summary_key,
        render_params=location_rename_render_params(event),
        tags=["world_change"],
        impacts=[
            {
                "target_type": "location",
                "target_id": str(event.location_id),
                "attribute": "canonical_name",
                "old_value": event.old_name,
                "new_value": event.new_name,
            }
        ],
    )


def location_occupation_render_params(event: LocationOccupationChanged) -> dict[str, Any]:
    """Return semantic render params for a location occupation/control event."""
    return {
        "location_id": str(event.location_id),
        "old_faction_id": None if event.old_faction_id is None else str(event.old_faction_id),
        "new_faction_id": None if event.new_faction_id is None else str(event.new_faction_id),
    }


def location_occupation_fallback_description(
    event: LocationOccupationChanged,
    *,
    location_name: str,
) -> str:
    """Return a non-localized compatibility fallback for occupation/control events."""
    old_faction = event.old_faction_id or "none"
    new_faction = event.new_faction_id or "none"
    return f"{location_name} changed controlling faction from {old_faction} to {new_faction}."


def location_occupation_changed_to_record(
    event: LocationOccupationChanged,
    *,
    description: str,
) -> WorldEventRecord:
    """Adapt a location occupation/control domain event into canonical event history."""
    return WorldEventRecord(
        kind=event.kind,
        year=event.year,
        month=event.month,
        day=event.day,
        location_id=str(event.location_id),
        description=description,
        severity=2,
        visibility="public",
        calendar_key=event.calendar_key,
        summary_key=event.summary_key,
        render_params=location_occupation_render_params(event),
        tags=["world_change", f"{LOCATION_TAG_PREFIX}{event.location_id}"],
        impacts=[
            {
                "target_type": "location",
                "target_id": str(event.location_id),
                "attribute": "controlling_faction_id",
                "old_value": None if event.old_faction_id is None else str(event.old_faction_id),
                "new_value": None if event.new_faction_id is None else str(event.new_faction_id),
            }
        ],
    )


def terrain_cell_render_params(event: TerrainCellMutated) -> dict[str, Any]:
    """Return semantic render params for a terrain-cell mutation event."""
    params = {
        "terrain_cell_id": str(event.terrain_cell_id),
        "x": event.x,
        "y": event.y,
        "old_biome": event.old_biome,
        "new_biome": event.new_biome,
        "old_elevation": event.old_elevation,
        "new_elevation": event.new_elevation,
        "old_moisture": event.old_moisture,
        "new_moisture": event.new_moisture,
        "old_temperature": event.old_temperature,
        "new_temperature": event.new_temperature,
    }
    changed_attributes = [
        attribute
        for attribute, old_value, new_value in (
            ("biome", event.old_biome, event.new_biome),
            ("elevation", event.old_elevation, event.new_elevation),
            ("moisture", event.old_moisture, event.new_moisture),
            ("temperature", event.old_temperature, event.new_temperature),
        )
        if old_value != new_value
    ]
    if changed_attributes:
        params["changed_attributes"] = changed_attributes
    if event.location_id is not None:
        params["location_id"] = str(event.location_id)
    params.update(_cause_render_params(reason_key=event.reason_key, cause_event_id=event.cause_event_id))
    return params


def terrain_cell_fallback_description(event: TerrainCellMutated) -> str:
    """Return a non-localized compatibility fallback for terrain mutation events."""
    changes = []
    if event.old_biome != event.new_biome:
        changes.append(f"biome from {event.old_biome} to {event.new_biome}")
    if event.old_elevation != event.new_elevation:
        changes.append(f"elevation from {event.old_elevation} to {event.new_elevation}")
    if event.old_moisture != event.new_moisture:
        changes.append(f"moisture from {event.old_moisture} to {event.new_moisture}")
    if event.old_temperature != event.new_temperature:
        changes.append(f"temperature from {event.old_temperature} to {event.new_temperature}")
    change_summary = ", ".join(changes) if changes else "no visible attributes"
    return f"Terrain at ({event.x}, {event.y}) changed: {change_summary}."


def _terrain_cell_impacts(event: TerrainCellMutated) -> list[dict[str, Any]]:
    target_id = str(event.terrain_cell_id)
    changes = (
        ("biome", event.old_biome, event.new_biome),
        ("elevation", event.old_elevation, event.new_elevation),
        ("moisture", event.old_moisture, event.new_moisture),
        ("temperature", event.old_temperature, event.new_temperature),
    )
    return [
        {
            "target_type": "terrain_cell",
            "target_id": target_id,
            "attribute": attribute,
            "old_value": old_value,
            "new_value": new_value,
        }
        for attribute, old_value, new_value in changes
        if old_value != new_value
    ]


def terrain_cell_mutated_to_record(
    event: TerrainCellMutated,
    *,
    description: str,
) -> WorldEventRecord:
    """Adapt a terrain-cell mutation domain event into canonical event history."""
    tags = ["world_change", "terrain", f"terrain_cell:{event.terrain_cell_id}"]
    if event.location_id is not None:
        tags.append(f"{LOCATION_TAG_PREFIX}{event.location_id}")
    return WorldEventRecord(
        kind=event.kind,
        year=event.year,
        month=event.month,
        day=event.day,
        location_id=None if event.location_id is None else str(event.location_id),
        description=description,
        severity=3,
        visibility="public",
        calendar_key=event.calendar_key,
        summary_key=event.summary_key,
        render_params=terrain_cell_render_params(event),
        tags=tags,
        impacts=_terrain_cell_impacts(event),
    )


def world_score_change_payload(change: WorldScoreChanged) -> dict[str, Any]:
    """Return JSON-compatible render payload for one world-score change."""
    return {
        "score_key": change.score_key,
        "old_value": change.old_value,
        "new_value": change.new_value,
        "delta": change.delta,
    }


def _cause_render_params(
    *,
    cause_key: str = "",
    reason_key: str = "",
    cause_event_id: object | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {}
    if cause_key:
        params["cause_key"] = cause_key
    if reason_key:
        params["reason_key"] = reason_key
    if cause_event_id is not None:
        params["cause_event_id"] = str(cause_event_id)
    return params


def era_shift_render_params(event: EraShifted) -> dict[str, Any]:
    """Return semantic render params for an era shift event."""
    return {
        "old_era_key": str(event.old_era_key),
        "new_era_key": str(event.new_era_key),
        "old_civilization_phase": event.old_civilization_phase,
        "new_civilization_phase": event.new_civilization_phase,
        **_cause_render_params(cause_key=event.cause_key, cause_event_id=event.cause_event_id),
    }


def era_shift_fallback_description(event: EraShifted) -> str:
    """Return a non-localized compatibility fallback for era shift events."""
    return (
        f"The era shifted from {event.old_era_key} to {event.new_era_key}; "
        f"civilization entered {event.new_civilization_phase}."
    )


def era_shifted_to_record(event: EraShifted, *, description: str) -> WorldEventRecord:
    """Adapt an era shift domain event into canonical event history."""
    return WorldEventRecord(
        kind=event.kind,
        year=event.year,
        month=event.month,
        day=event.day,
        description=description,
        severity=4,
        visibility="public",
        calendar_key=event.calendar_key,
        summary_key=event.summary_key,
        render_params=era_shift_render_params(event),
        tags=["world_change", "era"],
        impacts=[
            {
                "target_type": "world",
                "target_id": "era",
                "attribute": "era_key",
                "old_value": str(event.old_era_key),
                "new_value": str(event.new_era_key),
            },
            {
                "target_type": "world",
                "target_id": "civilization",
                "attribute": "civilization_phase",
                "old_value": event.old_civilization_phase,
                "new_value": event.new_civilization_phase,
            },
        ],
    )


def civilization_phase_drift_render_params(event: CivilizationPhaseDrifted) -> dict[str, Any]:
    """Return semantic render params for civilization phase drift events."""
    return {
        "era_key": str(event.era_key),
        "old_civilization_phase": event.old_civilization_phase,
        "new_civilization_phase": event.new_civilization_phase,
        "score_changes": [world_score_change_payload(change) for change in event.score_changes],
        **_cause_render_params(reason_key=event.reason_key, cause_event_id=event.cause_event_id),
    }


def civilization_phase_drift_fallback_description(event: CivilizationPhaseDrifted) -> str:
    """Return a non-localized compatibility fallback for civilization drift events."""
    reason = f" due to {event.reason_key}" if event.reason_key else ""
    return (
        f"Civilization drifted from {event.old_civilization_phase} "
        f"to {event.new_civilization_phase}{reason}."
    )


def civilization_phase_drifted_to_record(
    event: CivilizationPhaseDrifted,
    *,
    description: str,
) -> WorldEventRecord:
    """Adapt a civilization phase drift domain event into canonical event history."""
    impacts: list[dict[str, Any]] = [
        {
            "target_type": "world",
            "target_id": "civilization",
            "attribute": "civilization_phase",
            "old_value": event.old_civilization_phase,
            "new_value": event.new_civilization_phase,
        }
    ]
    impacts.extend(
        {
            "target_type": "world",
            "target_id": "world_scores",
            "attribute": change.score_key,
            "old_value": change.old_value,
            "new_value": change.new_value,
        }
        for change in event.score_changes
    )
    return WorldEventRecord(
        kind=event.kind,
        year=event.year,
        month=event.month,
        day=event.day,
        description=description,
        severity=3,
        visibility="public",
        calendar_key=event.calendar_key,
        summary_key=event.summary_key,
        render_params=civilization_phase_drift_render_params(event),
        tags=["world_change", "era", "civilization"],
        impacts=impacts,
    )

"""Commands for PR-K world-change slices."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from fantasy_simulator.ids import EraKey, EventRecordId, FactionId, LocationId, RouteId


@dataclass(frozen=True)
class SetRouteBlockedCommand:
    """Request a route blocked/open transition."""

    route_id: RouteId
    blocked: bool
    year: int
    month: int = 1
    day: int = 1
    calendar_key: str = ""
    cause_event_id: EventRecordId | None = None


@dataclass(frozen=True)
class RenameLocationCommand:
    """Request an official location rename."""

    location_id: LocationId
    new_name: str
    year: int
    month: int = 1
    day: int = 1
    calendar_key: str = ""
    cause_event_id: EventRecordId | None = None


@dataclass(frozen=True)
class SetLocationControllingFactionCommand:
    """Request a location occupation/control transition."""

    location_id: LocationId
    faction_id: FactionId | None
    year: int
    month: int = 1
    day: int = 1
    calendar_key: str = ""
    cause_event_id: EventRecordId | None = None


@dataclass(frozen=True)
class MutateTerrainCellCommand:
    """Request a runtime terrain-cell mutation."""

    x: int
    y: int
    year: int
    month: int = 1
    day: int = 1
    biome: str | None = None
    elevation: int | None = None
    moisture: int | None = None
    temperature: int | None = None
    location_id: LocationId | None = None
    calendar_key: str = ""
    reason_key: str = ""
    cause_event_id: EventRecordId | None = None


@dataclass(frozen=True)
class ShiftEraCommand:
    """Request a world era transition."""

    new_era_key: EraKey
    year: int
    month: int = 1
    day: int = 1
    new_civilization_phase: str = "new_era"
    calendar_key: str = ""
    cause_key: str = ""
    cause_event_id: EventRecordId | None = None


@dataclass(frozen=True)
class DriftCivilizationPhaseCommand:
    """Request a civilization phase drift and optional bounded world-score drift."""

    new_phase: str
    year: int
    month: int = 1
    day: int = 1
    score_deltas: Mapping[str, int] = field(default_factory=dict)
    reason_key: str = ""
    calendar_key: str = ""
    cause_event_id: EventRecordId | None = None

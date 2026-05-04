"""Domain events for PR-K world-change slices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fantasy_simulator.ids import EraKey, EventRecordId, FactionId, LocationId, RouteId, TerrainCellId


RouteEventKind = Literal["route_blocked", "route_reopened"]


@dataclass(frozen=True)
class RouteStatusChanged:
    """Domain fact that a route moved between open and blocked states."""

    route_id: RouteId
    from_location_id: LocationId
    to_location_id: LocationId
    old_blocked: bool
    new_blocked: bool
    year: int
    month: int
    day: int
    calendar_key: str = ""
    cause_event_id: EventRecordId | None = None

    @property
    def kind(self) -> RouteEventKind:
        return "route_blocked" if self.new_blocked else "route_reopened"

    @property
    def summary_key(self) -> str:
        return f"events.{self.kind}.summary"

    @property
    def endpoint_location_ids(self) -> list[str]:
        return [str(self.from_location_id), str(self.to_location_id)]


@dataclass(frozen=True)
class LocationRenamed:
    """Domain fact that a location's official name changed."""

    location_id: LocationId
    old_name: str
    new_name: str
    year: int
    month: int
    day: int
    calendar_key: str = ""
    cause_event_id: EventRecordId | None = None

    @property
    def kind(self) -> Literal["location_renamed"]:
        return "location_renamed"

    @property
    def summary_key(self) -> str:
        return "events.location_renamed.summary"


@dataclass(frozen=True)
class LocationOccupationChanged:
    """Domain fact that a location's controlling faction changed."""

    location_id: LocationId
    old_faction_id: FactionId | None
    new_faction_id: FactionId | None
    year: int
    month: int
    day: int
    calendar_key: str = ""
    cause_event_id: EventRecordId | None = None

    @property
    def kind(self) -> Literal["location_faction_changed"]:
        return "location_faction_changed"

    @property
    def summary_key(self) -> str:
        return "events.location_faction_changed.summary"


@dataclass(frozen=True)
class TerrainCellMutated:
    """Domain fact that one runtime terrain cell changed."""

    x: int
    y: int
    old_biome: str
    new_biome: str
    old_elevation: int
    new_elevation: int
    old_moisture: int
    new_moisture: int
    old_temperature: int
    new_temperature: int
    year: int
    month: int
    day: int
    location_id: LocationId | None = None
    calendar_key: str = ""
    reason_key: str = ""
    cause_event_id: EventRecordId | None = None

    @property
    def kind(self) -> Literal["terrain_cell_mutated"]:
        return "terrain_cell_mutated"

    @property
    def summary_key(self) -> str:
        return "events.terrain_cell_mutated.summary"

    @property
    def terrain_cell_id(self) -> TerrainCellId:
        return TerrainCellId(f"terrain:{self.x}:{self.y}")


@dataclass(frozen=True)
class WorldScoreChanged:
    """Domain fact for one bounded world-score change."""

    score_key: str
    old_value: int
    new_value: int

    @property
    def delta(self) -> int:
        return self.new_value - self.old_value


@dataclass(frozen=True)
class EraShifted:
    """Domain fact that the world moved from one era to another."""

    old_era_key: EraKey
    new_era_key: EraKey
    old_civilization_phase: str
    new_civilization_phase: str
    year: int
    month: int
    day: int
    calendar_key: str = ""
    cause_key: str = ""
    cause_event_id: EventRecordId | None = None

    @property
    def kind(self) -> Literal["era_shifted"]:
        return "era_shifted"

    @property
    def summary_key(self) -> str:
        return "events.era_shifted.summary"


@dataclass(frozen=True)
class CivilizationPhaseDrifted:
    """Domain fact that civilization phase or world scores drifted."""

    era_key: EraKey
    old_civilization_phase: str
    new_civilization_phase: str
    score_changes: tuple[WorldScoreChanged, ...]
    year: int
    month: int
    day: int
    calendar_key: str = ""
    reason_key: str = ""
    cause_event_id: EventRecordId | None = None

    @property
    def kind(self) -> Literal["civilization_phase_drifted"]:
        return "civilization_phase_drifted"

    @property
    def summary_key(self) -> str:
        return "events.civilization_phase_drifted.summary"

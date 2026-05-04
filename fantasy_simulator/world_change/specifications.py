"""Validation rules for PR-K world-change commands."""

from __future__ import annotations

from typing import Container, Iterable, Mapping, Protocol

from fantasy_simulator.ids import FactionId, RouteId

from .commands import (
    DriftCivilizationPhaseCommand,
    RenameLocationCommand,
    SetLocationControllingFactionCommand,
    SetRouteBlockedCommand,
    ShiftEraCommand,
    MutateTerrainCellCommand,
)
from .state_machines import CivilizationPhase, validate_civilization_phase


class SupportsRouteStatus(Protocol):
    route_id: str
    from_site_id: str
    to_site_id: str
    blocked: bool


class SupportsLocationNameState(Protocol):
    id: str
    canonical_name: str
    aliases: list[str]


class SupportsLocationOccupationState(Protocol):
    id: str
    canonical_name: str
    controlling_faction_id: str | None


class SupportsTerrainCellState(Protocol):
    x: int
    y: int
    biome: str
    elevation: int
    moisture: int
    temperature: int


class SupportsTerrainMapState(Protocol):
    width: int
    height: int

    def get(self, x: int, y: int) -> SupportsTerrainCellState | None: ...


class SupportsEraRuntimeState(Protocol):
    era_key: str
    civilization_phase: str
    world_scores: Mapping[str, int]


def route_by_id(routes: Iterable[SupportsRouteStatus], *, route_id: RouteId) -> SupportsRouteStatus:
    """Return a route by ID or raise ``KeyError``."""
    for route in routes:
        if route.route_id == route_id:
            return route
    raise KeyError(str(route_id))


def validate_set_route_blocked_command(
    command: SetRouteBlockedCommand,
    *,
    routes: Iterable[SupportsRouteStatus],
    location_ids: Container[str],
) -> SupportsRouteStatus:
    """Validate that a route blocked/open command can be evaluated."""
    if not isinstance(command.blocked, bool):
        raise TypeError("blocked must be a bool")
    route = route_by_id(routes, route_id=command.route_id)
    if not route.from_site_id or not route.to_site_id:
        raise ValueError(f"route {route.route_id} must have two endpoint location IDs")
    if route.from_site_id not in location_ids:
        raise ValueError(f"route {route.route_id} references unknown endpoint: {route.from_site_id}")
    if route.to_site_id not in location_ids:
        raise ValueError(f"route {route.route_id} references unknown endpoint: {route.to_site_id}")
    return route


def validate_rename_location_command(
    command: RenameLocationCommand,
    *,
    location_index: Mapping[str, SupportsLocationNameState],
    location_name_index: Mapping[str, SupportsLocationNameState],
) -> tuple[SupportsLocationNameState, str]:
    """Validate that a location rename command can be evaluated."""
    location = location_index.get(str(command.location_id))
    if location is None:
        raise KeyError(str(command.location_id))
    normalized_name = command.new_name.strip()
    if not normalized_name:
        raise ValueError("new_name must not be blank")
    existing = location_name_index.get(normalized_name)
    if existing is not None and existing is not location:
        raise ValueError(f"location name already exists: {normalized_name}")
    return location, normalized_name


def normalize_faction_id(faction_id: FactionId | str | None) -> FactionId | None:
    """Return a normalized faction ID, with blank values treated as no faction."""
    if faction_id is None:
        return None
    normalized = str(faction_id).strip()
    return FactionId(normalized) if normalized else None


def validate_set_location_controlling_faction_command(
    command: SetLocationControllingFactionCommand,
    *,
    location_index: Mapping[str, SupportsLocationOccupationState],
    known_faction_ids: Container[str] | None = None,
) -> tuple[SupportsLocationOccupationState, FactionId | None]:
    """Validate that a location occupation/control command can be evaluated."""
    location = location_index.get(str(command.location_id))
    if location is None:
        raise KeyError(str(command.location_id))
    normalized_faction_id = normalize_faction_id(command.faction_id)
    if (
        normalized_faction_id is not None
        and known_faction_ids is not None
        and str(normalized_faction_id) not in known_faction_ids
    ):
        raise ValueError(f"unknown faction id: {normalized_faction_id}")
    return location, normalized_faction_id


def _terrain_coord(value: int, *, field_name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _terrain_scalar(value: int | None, fallback: int, *, field_name: str) -> int:
    if value is None:
        return fallback
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{field_name} must be an integer")
    if not 0 <= value <= 255:
        raise ValueError(f"{field_name} must be between 0 and 255")
    return value


def _terrain_biome(value: str | None, fallback: str, *, allowed_biomes: Container[str]) -> str:
    if value is None:
        return fallback
    normalized = value.strip()
    if not normalized:
        raise ValueError("biome must not be blank")
    if normalized not in allowed_biomes:
        raise ValueError(f"unknown terrain biome: {normalized}")
    return normalized


def validate_mutate_terrain_cell_command(
    command: MutateTerrainCellCommand,
    *,
    terrain_map: SupportsTerrainMapState | None,
    allowed_biomes: Container[str],
) -> tuple[SupportsTerrainCellState, str, int, int, int]:
    """Validate a terrain-cell mutation and return normalized requested values."""
    if terrain_map is None:
        raise ValueError("terrain_map is required for terrain cell mutations")
    x = _terrain_coord(command.x, field_name="x")
    y = _terrain_coord(command.y, field_name="y")
    if not 0 <= x < terrain_map.width or not 0 <= y < terrain_map.height:
        raise ValueError(f"terrain cell is outside world bounds: ({x}, {y})")
    cell = terrain_map.get(x, y)
    if cell is None:
        raise KeyError(f"terrain cell does not exist: ({x}, {y})")
    return (
        cell,
        _terrain_biome(command.biome, cell.biome, allowed_biomes=allowed_biomes),
        _terrain_scalar(command.elevation, cell.elevation, field_name="elevation"),
        _terrain_scalar(command.moisture, cell.moisture, field_name="moisture"),
        _terrain_scalar(command.temperature, cell.temperature, field_name="temperature"),
    )


def _known_era_keys(authored_era_keys: Iterable[str]) -> set[str]:
    return {str(era_key).strip() for era_key in authored_era_keys if str(era_key).strip()}


def validate_shift_era_command(
    command: ShiftEraCommand,
    *,
    era_runtime: SupportsEraRuntimeState,
    authored_era_keys: Iterable[str],
) -> tuple[str, CivilizationPhase]:
    """Validate that an era shift references known authored era definitions."""
    known_eras = _known_era_keys(authored_era_keys)
    current_era_key = str(era_runtime.era_key).strip()
    requested_era_key = str(command.new_era_key).strip()
    if not current_era_key:
        raise ValueError("runtime era must not be blank")
    if not requested_era_key:
        raise ValueError("new_era_key must not be blank")
    if current_era_key not in known_eras:
        raise ValueError(f"runtime era references unknown era definition: {current_era_key}")
    if requested_era_key not in known_eras:
        raise ValueError(f"new era references unknown era definition: {requested_era_key}")
    validate_civilization_phase(era_runtime.civilization_phase)
    return requested_era_key, validate_civilization_phase(command.new_civilization_phase)


def validate_drift_civilization_phase_command(
    command: DriftCivilizationPhaseCommand,
    *,
    era_runtime: SupportsEraRuntimeState,
) -> CivilizationPhase:
    """Validate that a civilization drift command can be evaluated against runtime state."""
    if not str(era_runtime.era_key).strip():
        raise ValueError("runtime era must not be blank")
    validate_civilization_phase(era_runtime.civilization_phase)
    return validate_civilization_phase(command.new_phase)

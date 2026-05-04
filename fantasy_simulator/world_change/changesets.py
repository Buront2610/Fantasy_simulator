"""ChangeSet construction for PR-K world-change slices."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Container, Iterable, Mapping

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.ids import EraKey, FactionId, LocationId, RouteId

from .commands import (
    DriftCivilizationPhaseCommand,
    MutateTerrainCellCommand,
    RenameLocationCommand,
    SetLocationControllingFactionCommand,
    SetRouteBlockedCommand,
    ShiftEraCommand,
)
from .domain_events import (
    CivilizationPhaseDrifted,
    EraShifted,
    LocationOccupationChanged,
    LocationRenamed,
    RouteStatusChanged,
    TerrainCellMutated,
    WorldScoreChanged,
)
from .event_adapters import (
    civilization_phase_drift_fallback_description,
    civilization_phase_drift_render_params,
    civilization_phase_drifted_to_record,
    era_shift_fallback_description,
    era_shift_render_params,
    era_shifted_to_record,
    location_occupation_changed_to_record,
    location_occupation_fallback_description,
    location_occupation_render_params,
    location_rename_fallback_description,
    location_rename_render_params,
    location_renamed_to_record,
    route_status_changed_to_record,
    route_status_fallback_description,
    route_status_render_params,
    terrain_cell_fallback_description,
    terrain_cell_mutated_to_record,
    terrain_cell_render_params,
)
from .specifications import (
    SupportsEraRuntimeState,
    SupportsLocationNameState,
    SupportsLocationOccupationState,
    SupportsRouteStatus,
    SupportsTerrainMapState,
    validate_drift_civilization_phase_command,
    validate_mutate_terrain_cell_command,
    validate_rename_location_command,
    validate_set_location_controlling_faction_command,
    validate_set_route_blocked_command,
    validate_shift_era_command,
)
from .state_machines import (
    transition_civilization_phase,
    transition_era_shift,
    transition_location_name,
    transition_location_occupation_state,
    transition_route_blocked_state,
    transition_terrain_cell,
    transition_world_scores,
    validate_civilization_phase,
)


DescriptionBuilder = Callable[[str, dict[str, Any], str], str]


@dataclass(frozen=True)
class RouteUpdate:
    """Runtime route state update emitted by a world-change command."""

    route_id: RouteId
    old_blocked: bool
    new_blocked: bool


@dataclass(frozen=True)
class LocationRenameUpdate:
    """Runtime location rename update emitted by a world-change command."""

    location_id: LocationId
    old_name: str
    new_name: str
    old_aliases: tuple[str, ...]
    new_aliases: tuple[str, ...]


@dataclass(frozen=True)
class LocationOccupationUpdate:
    """Runtime location occupation/control update emitted by a world-change command."""

    location_id: LocationId
    old_faction_id: FactionId | None
    new_faction_id: FactionId | None


@dataclass(frozen=True)
class TerrainCellUpdate:
    """Runtime terrain-cell update emitted by a world-change command."""

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


@dataclass(frozen=True)
class WorldScoreUpdate:
    """Runtime world-score update emitted by a civilization drift command."""

    score_key: str
    old_value: int
    new_value: int


@dataclass(frozen=True)
class EraRuntimeUpdate:
    """Runtime era/civilization update emitted by a world-change command."""

    old_era_key: EraKey
    new_era_key: EraKey
    old_civilization_phase: str
    new_civilization_phase: str
    score_updates: tuple[WorldScoreUpdate, ...] = ()


@dataclass(frozen=True)
class WorldChangeSet:
    """Prepared domain changes that can be reduced into runtime state."""

    events: tuple[WorldEventRecord, ...]
    location_updates: tuple[LocationRenameUpdate, ...] = ()
    occupation_updates: tuple[LocationOccupationUpdate, ...] = ()
    route_updates: tuple[RouteUpdate, ...] = ()
    terrain_updates: tuple[TerrainCellUpdate, ...] = ()
    era_updates: tuple[EraRuntimeUpdate, ...] = ()
    projection_hints: tuple[str, ...] = ()


def build_route_blocked_change_set(
    command: SetRouteBlockedCommand,
    *,
    routes: Iterable[SupportsRouteStatus],
    location_ids: Container[str],
    location_name: Callable[[str], str],
    describe: DescriptionBuilder,
) -> WorldChangeSet | None:
    """Build a route block/reopen ChangeSet, or ``None`` for an idempotent no-op."""
    route = validate_set_route_blocked_command(
        command,
        routes=routes,
        location_ids=location_ids,
    )
    transition = transition_route_blocked_state(route.blocked, command.blocked)
    if transition is None:
        return None

    event = RouteStatusChanged(
        route_id=command.route_id,
        from_location_id=LocationId(route.from_site_id),
        to_location_id=LocationId(route.to_site_id),
        old_blocked=transition.old_blocked,
        new_blocked=transition.new_blocked,
        year=command.year,
        month=command.month,
        day=command.day,
        calendar_key=command.calendar_key,
        cause_event_id=command.cause_event_id,
    )
    render_params = route_status_render_params(event)
    fallback_description = route_status_fallback_description(event, location_name=location_name)
    record = route_status_changed_to_record(
        event,
        description=describe(event.summary_key, render_params, fallback_description),
    )
    return WorldChangeSet(
        events=(record,),
        route_updates=(
            RouteUpdate(
                route_id=RouteId(route.route_id),
                old_blocked=transition.old_blocked,
                new_blocked=transition.new_blocked,
            ),
        ),
        projection_hints=("route_status",),
    )


def build_location_rename_change_set(
    command: RenameLocationCommand,
    *,
    location_index: Mapping[str, SupportsLocationNameState],
    location_name_index: Mapping[str, SupportsLocationNameState],
    max_aliases: int,
    describe: DescriptionBuilder,
) -> WorldChangeSet | None:
    """Build a location rename ChangeSet, or ``None`` for an idempotent no-op."""
    location, normalized_name = validate_rename_location_command(
        command,
        location_index=location_index,
        location_name_index=location_name_index,
    )
    transition = transition_location_name(
        old_name=location.canonical_name,
        requested_name=normalized_name,
        aliases=location.aliases,
        max_aliases=max_aliases,
    )
    if transition is None:
        return None

    event = LocationRenamed(
        location_id=command.location_id,
        old_name=transition.old_name,
        new_name=transition.new_name,
        year=command.year,
        month=command.month,
        day=command.day,
        calendar_key=command.calendar_key,
        cause_event_id=command.cause_event_id,
    )
    record = location_renamed_to_record(
        event,
        description=describe(
            event.summary_key,
            location_rename_render_params(event),
            location_rename_fallback_description(event),
        ),
    )
    return WorldChangeSet(
        events=(record,),
        location_updates=(
            LocationRenameUpdate(
                location_id=command.location_id,
                old_name=transition.old_name,
                new_name=transition.new_name,
                old_aliases=transition.old_aliases,
                new_aliases=transition.new_aliases,
            ),
        ),
        projection_hints=("location_history",),
    )


def build_location_occupation_change_set(
    command: SetLocationControllingFactionCommand,
    *,
    location_index: Mapping[str, SupportsLocationOccupationState],
    location_name: Callable[[str], str],
    describe: DescriptionBuilder,
    known_faction_ids: Container[str] | None = None,
) -> WorldChangeSet | None:
    """Build a location occupation/control ChangeSet, or ``None`` for an idempotent no-op."""
    location, normalized_faction_id = validate_set_location_controlling_faction_command(
        command,
        location_index=location_index,
        known_faction_ids=known_faction_ids,
    )
    transition = transition_location_occupation_state(
        location.controlling_faction_id,
        None if normalized_faction_id is None else str(normalized_faction_id),
    )
    if transition is None:
        return None

    event = LocationOccupationChanged(
        location_id=command.location_id,
        old_faction_id=None if transition.old_faction_id is None else FactionId(transition.old_faction_id),
        new_faction_id=None if transition.new_faction_id is None else FactionId(transition.new_faction_id),
        year=command.year,
        month=command.month,
        day=command.day,
        calendar_key=command.calendar_key,
        cause_event_id=command.cause_event_id,
    )
    resolved_location_name = location_name(str(command.location_id))
    record = location_occupation_changed_to_record(
        event,
        description=describe(
            event.summary_key,
            location_occupation_render_params(event),
            location_occupation_fallback_description(event, location_name=resolved_location_name),
        ),
    )
    return WorldChangeSet(
        events=(record,),
        occupation_updates=(
            LocationOccupationUpdate(
                location_id=command.location_id,
                old_faction_id=event.old_faction_id,
                new_faction_id=event.new_faction_id,
            ),
        ),
        projection_hints=("location_history", "war_map"),
    )


def build_terrain_cell_mutation_change_set(
    command: MutateTerrainCellCommand,
    *,
    terrain_map: SupportsTerrainMapState | None,
    allowed_biomes: Container[str],
    describe: DescriptionBuilder,
) -> WorldChangeSet | None:
    """Build a terrain-cell mutation ChangeSet, or ``None`` for an idempotent no-op."""
    cell, new_biome, new_elevation, new_moisture, new_temperature = validate_mutate_terrain_cell_command(
        command,
        terrain_map=terrain_map,
        allowed_biomes=allowed_biomes,
    )
    transition = transition_terrain_cell(
        x=cell.x,
        y=cell.y,
        old_biome=cell.biome,
        requested_biome=new_biome,
        old_elevation=cell.elevation,
        requested_elevation=new_elevation,
        old_moisture=cell.moisture,
        requested_moisture=new_moisture,
        old_temperature=cell.temperature,
        requested_temperature=new_temperature,
    )
    if transition is None:
        return None

    event = TerrainCellMutated(
        x=transition.x,
        y=transition.y,
        old_biome=transition.old_biome,
        new_biome=transition.new_biome,
        old_elevation=transition.old_elevation,
        new_elevation=transition.new_elevation,
        old_moisture=transition.old_moisture,
        new_moisture=transition.new_moisture,
        old_temperature=transition.old_temperature,
        new_temperature=transition.new_temperature,
        year=command.year,
        month=command.month,
        day=command.day,
        location_id=command.location_id,
        calendar_key=command.calendar_key,
        reason_key=command.reason_key,
        cause_event_id=command.cause_event_id,
    )
    record = terrain_cell_mutated_to_record(
        event,
        description=describe(
            event.summary_key,
            terrain_cell_render_params(event),
            terrain_cell_fallback_description(event),
        ),
    )
    return WorldChangeSet(
        events=(record,),
        terrain_updates=(
            TerrainCellUpdate(
                x=transition.x,
                y=transition.y,
                old_biome=transition.old_biome,
                new_biome=transition.new_biome,
                old_elevation=transition.old_elevation,
                new_elevation=transition.new_elevation,
                old_moisture=transition.old_moisture,
                new_moisture=transition.new_moisture,
                old_temperature=transition.old_temperature,
                new_temperature=transition.new_temperature,
            ),
        ),
        projection_hints=("terrain",),
    )


def _score_update_from_transition(transition: Any) -> WorldScoreUpdate:
    return WorldScoreUpdate(
        score_key=transition.score_key,
        old_value=transition.old_value,
        new_value=transition.new_value,
    )


def _score_change_from_update(update: WorldScoreUpdate) -> WorldScoreChanged:
    return WorldScoreChanged(
        score_key=update.score_key,
        old_value=update.old_value,
        new_value=update.new_value,
    )


def build_era_shift_change_set(
    command: ShiftEraCommand,
    *,
    era_runtime: SupportsEraRuntimeState,
    authored_era_keys: Iterable[str],
    describe: DescriptionBuilder,
) -> WorldChangeSet | None:
    """Build an era-shift ChangeSet, or ``None`` for an idempotent no-op."""
    requested_era_key, requested_phase = validate_shift_era_command(
        command,
        era_runtime=era_runtime,
        authored_era_keys=authored_era_keys,
    )
    transition = transition_era_shift(
        old_era_key=era_runtime.era_key,
        requested_era_key=requested_era_key,
        old_civilization_phase=era_runtime.civilization_phase,
        requested_civilization_phase=requested_phase,
    )
    if transition is None:
        return None

    event = EraShifted(
        old_era_key=EraKey(transition.old_era_key),
        new_era_key=EraKey(transition.new_era_key),
        old_civilization_phase=transition.old_civilization_phase,
        new_civilization_phase=transition.new_civilization_phase,
        year=command.year,
        month=command.month,
        day=command.day,
        calendar_key=command.calendar_key,
        cause_key=command.cause_key,
        cause_event_id=command.cause_event_id,
    )
    record = era_shifted_to_record(
        event,
        description=describe(
            event.summary_key,
            era_shift_render_params(event),
            era_shift_fallback_description(event),
        ),
    )
    return WorldChangeSet(
        events=(record,),
        era_updates=(
            EraRuntimeUpdate(
                old_era_key=event.old_era_key,
                new_era_key=event.new_era_key,
                old_civilization_phase=event.old_civilization_phase,
                new_civilization_phase=event.new_civilization_phase,
            ),
        ),
        projection_hints=("era_timeline",),
    )


def build_civilization_phase_drift_change_set(
    command: DriftCivilizationPhaseCommand,
    *,
    era_runtime: SupportsEraRuntimeState,
    describe: DescriptionBuilder,
) -> WorldChangeSet | None:
    """Build a civilization-phase drift ChangeSet, or ``None`` for an idempotent no-op."""
    requested_phase = validate_drift_civilization_phase_command(command, era_runtime=era_runtime)
    phase_transition = transition_civilization_phase(era_runtime.civilization_phase, requested_phase)
    score_updates = tuple(
        _score_update_from_transition(transition)
        for transition in transition_world_scores(era_runtime.world_scores, command.score_deltas)
    )
    if phase_transition is None and not score_updates:
        return None

    old_phase = validate_civilization_phase(era_runtime.civilization_phase)
    new_phase = requested_phase if phase_transition is None else phase_transition.new_phase
    event = CivilizationPhaseDrifted(
        era_key=EraKey(str(era_runtime.era_key).strip()),
        old_civilization_phase=old_phase,
        new_civilization_phase=new_phase,
        score_changes=tuple(_score_change_from_update(update) for update in score_updates),
        year=command.year,
        month=command.month,
        day=command.day,
        calendar_key=command.calendar_key,
        reason_key=command.reason_key,
        cause_event_id=command.cause_event_id,
    )
    record = civilization_phase_drifted_to_record(
        event,
        description=describe(
            event.summary_key,
            civilization_phase_drift_render_params(event),
            civilization_phase_drift_fallback_description(event),
        ),
    )
    return WorldChangeSet(
        events=(record,),
        era_updates=(
            EraRuntimeUpdate(
                old_era_key=event.era_key,
                new_era_key=event.era_key,
                old_civilization_phase=event.old_civilization_phase,
                new_civilization_phase=event.new_civilization_phase,
                score_updates=score_updates,
            ),
        ),
        projection_hints=("era_timeline",),
    )

"""Reducers for prepared PR-K world-change sets."""

from __future__ import annotations

from collections.abc import MutableMapping as MutableMappingABC
from dataclasses import dataclass
from typing import Any, Callable, Iterable, MutableMapping, Protocol, cast

from fantasy_simulator.event_models import WorldEventRecord

from .changesets import (
    EraRuntimeUpdate,
    LocationOccupationUpdate,
    LocationRenameUpdate,
    RouteUpdate,
    TerrainCellUpdate,
    WorldChangeSet,
)
from .specifications import SupportsRouteStatus, route_by_id


EventRecorder = Callable[[WorldEventRecord], WorldEventRecord]


class EventRecorderPort(Protocol):
    """Port used when event recording must be transactionally restorable."""

    def record(self, record: WorldEventRecord) -> WorldEventRecord: ...

    def snapshot(self) -> Any: ...

    def restore(self, snapshot: Any) -> None: ...


EventRecorderInput = EventRecorder | EventRecorderPort


@dataclass(frozen=True)
class _ReducerRuntimeContext:
    routes: Iterable[SupportsRouteStatus]
    location_index: MutableMapping[str, Any] | None
    location_name_index: MutableMapping[str, Any] | None
    terrain_map: Any | None
    era_runtime: Any | None


@dataclass
class _AppliedRuntimeUpdates:
    route_updates: list[RouteUpdate]
    location_updates: list[LocationRenameUpdate]
    occupation_updates: list[LocationOccupationUpdate]
    terrain_updates: list[TerrainCellUpdate]
    era_updates: list[EraRuntimeUpdate]

    @classmethod
    def empty(cls) -> "_AppliedRuntimeUpdates":
        return cls(
            route_updates=[],
            location_updates=[],
            occupation_updates=[],
            terrain_updates=[],
            era_updates=[],
        )


def _apply_route_update(routes: Iterable[SupportsRouteStatus], update: RouteUpdate) -> None:
    route = route_by_id(routes, route_id=update.route_id)
    route.blocked = update.new_blocked


def _rollback_route_update(routes: Iterable[SupportsRouteStatus], update: RouteUpdate) -> None:
    route = route_by_id(routes, route_id=update.route_id)
    route.blocked = update.old_blocked


def _apply_location_rename_update(
    location_index: MutableMapping[str, Any],
    location_name_index: MutableMapping[str, Any],
    update: LocationRenameUpdate,
) -> None:
    location = location_index[str(update.location_id)]
    location_name_index.pop(update.old_name, None)
    location.canonical_name = update.new_name
    location.aliases = list(update.new_aliases)
    location_name_index[update.new_name] = location


def _rollback_location_rename_update(
    location_index: MutableMapping[str, Any],
    location_name_index: MutableMapping[str, Any],
    update: LocationRenameUpdate,
) -> None:
    location = location_index[str(update.location_id)]
    location_name_index.pop(update.new_name, None)
    location.canonical_name = update.old_name
    location.aliases = list(update.old_aliases)
    location_name_index[update.old_name] = location


def _apply_location_occupation_update(
    location_index: MutableMapping[str, Any],
    update: LocationOccupationUpdate,
) -> None:
    location = location_index[str(update.location_id)]
    location.controlling_faction_id = None if update.new_faction_id is None else str(update.new_faction_id)


def _rollback_location_occupation_update(
    location_index: MutableMapping[str, Any],
    update: LocationOccupationUpdate,
) -> None:
    location = location_index[str(update.location_id)]
    location.controlling_faction_id = None if update.old_faction_id is None else str(update.old_faction_id)


def _terrain_cell(terrain_map: Any, update: TerrainCellUpdate) -> Any:
    cell = terrain_map.get(update.x, update.y)
    if cell is None:
        raise KeyError(f"terrain cell does not exist: ({update.x}, {update.y})")
    return cell


def _apply_terrain_update(terrain_map: Any, update: TerrainCellUpdate) -> None:
    cell = _terrain_cell(terrain_map, update)
    cell.biome = update.new_biome
    cell.elevation = update.new_elevation
    cell.moisture = update.new_moisture
    cell.temperature = update.new_temperature


def _rollback_terrain_update(terrain_map: Any, update: TerrainCellUpdate) -> None:
    cell = _terrain_cell(terrain_map, update)
    cell.biome = update.old_biome
    cell.elevation = update.old_elevation
    cell.moisture = update.old_moisture
    cell.temperature = update.old_temperature


def _world_scores_mapping(era_runtime: Any, update: EraRuntimeUpdate) -> MutableMappingABC[str, int] | None:
    if not update.score_updates:
        return None
    world_scores = getattr(era_runtime, "world_scores", None)
    if not isinstance(world_scores, MutableMappingABC):
        raise ValueError("era_runtime.world_scores must be a mutable mapping for score updates")
    return world_scores


def _apply_era_runtime_update(era_runtime: Any, update: EraRuntimeUpdate) -> None:
    world_scores = _world_scores_mapping(era_runtime, update)
    era_runtime.era_key = str(update.new_era_key)
    era_runtime.civilization_phase = update.new_civilization_phase
    if world_scores is not None:
        for score_update in update.score_updates:
            world_scores[score_update.score_key] = score_update.new_value


def _rollback_era_runtime_update(era_runtime: Any, update: EraRuntimeUpdate) -> None:
    world_scores = _world_scores_mapping(era_runtime, update)
    era_runtime.era_key = str(update.old_era_key)
    era_runtime.civilization_phase = update.old_civilization_phase
    if world_scores is not None:
        for score_update in update.score_updates:
            world_scores[score_update.score_key] = score_update.old_value


def _event_recording_snapshot(
    change_set: WorldChangeSet,
    record_event: EventRecorderInput,
) -> Any | None:
    event_count = len(change_set.events)
    if event_count == 0:
        return None
    if _is_event_recorder_port(record_event):
        return cast(EventRecorderPort, record_event).snapshot()
    if event_count > 1:
        raise ValueError("multi-event changesets require a snapshot-capable event recorder")
    return None


def _is_event_recorder_port(record_event: EventRecorderInput) -> bool:
    return all(
        callable(getattr(record_event, method_name, None))
        for method_name in ("record", "snapshot", "restore")
    )


def _validate_runtime_requirements(change_set: WorldChangeSet, context: _ReducerRuntimeContext) -> None:
    if change_set.location_updates and (
        context.location_index is None or context.location_name_index is None
    ):
        raise ValueError("location indexes are required for location updates")
    if change_set.occupation_updates and context.location_index is None:
        raise ValueError("location index is required for occupation updates")
    if change_set.terrain_updates and context.terrain_map is None:
        raise ValueError("terrain_map is required for terrain updates")
    if change_set.era_updates and context.era_runtime is None:
        raise ValueError("era runtime is required for era updates")


def _validate_route_update_is_fresh(routes: Iterable[SupportsRouteStatus], update: RouteUpdate) -> None:
    route = route_by_id(routes, route_id=update.route_id)
    if route.blocked != update.old_blocked:
        raise ValueError(
            f"stale route update for {update.route_id}: blocked is {route.blocked}, "
            f"expected {update.old_blocked}"
        )


def _validate_location_rename_update_is_fresh(
    location_index: MutableMapping[str, Any],
    location_name_index: MutableMapping[str, Any],
    update: LocationRenameUpdate,
) -> None:
    location = location_index[str(update.location_id)]
    if location.canonical_name != update.old_name:
        raise ValueError(
            f"stale location rename update for {update.location_id}: canonical_name is "
            f"{location.canonical_name!r}, expected {update.old_name!r}"
        )
    if tuple(location.aliases) != update.old_aliases:
        raise ValueError(
            f"stale location rename update for {update.location_id}: aliases are "
            f"{tuple(location.aliases)!r}, expected {update.old_aliases!r}"
        )
    if location_name_index.get(update.old_name) is not location:
        raise ValueError(
            f"stale location rename update for {update.location_id}: name index is missing "
            f"{update.old_name!r}"
        )


def _validate_location_occupation_update_is_fresh(
    location_index: MutableMapping[str, Any],
    update: LocationOccupationUpdate,
) -> None:
    location = location_index[str(update.location_id)]
    expected_faction_id = None if update.old_faction_id is None else str(update.old_faction_id)
    if location.controlling_faction_id != expected_faction_id:
        raise ValueError(
            f"stale location occupation update for {update.location_id}: controlling_faction_id is "
            f"{location.controlling_faction_id!r}, expected {expected_faction_id!r}"
        )


def _validate_terrain_update_is_fresh(terrain_map: Any, update: TerrainCellUpdate) -> None:
    cell = _terrain_cell(terrain_map, update)
    stale_attributes = [
        attribute
        for attribute, expected_value in (
            ("biome", update.old_biome),
            ("elevation", update.old_elevation),
            ("moisture", update.old_moisture),
            ("temperature", update.old_temperature),
        )
        if getattr(cell, attribute) != expected_value
    ]
    if stale_attributes:
        attribute = stale_attributes[0]
        raise ValueError(
            f"stale terrain update for ({update.x}, {update.y}): {attribute} is "
            f"{getattr(cell, attribute)!r}, expected {getattr(update, f'old_{attribute}')!r}"
        )


def _validate_era_runtime_update_is_fresh(era_runtime: Any, update: EraRuntimeUpdate) -> None:
    if str(era_runtime.era_key) != str(update.old_era_key):
        raise ValueError(
            f"stale era update: era_key is {str(era_runtime.era_key)!r}, "
            f"expected {str(update.old_era_key)!r}"
        )
    if era_runtime.civilization_phase != update.old_civilization_phase:
        raise ValueError(
            f"stale era update: civilization_phase is {era_runtime.civilization_phase!r}, "
            f"expected {update.old_civilization_phase!r}"
        )
    world_scores = _world_scores_mapping(era_runtime, update)
    if world_scores is not None:
        for score_update in update.score_updates:
            actual_value = world_scores.get(score_update.score_key)
            if actual_value != score_update.old_value:
                raise ValueError(
                    f"stale era update: world_scores[{score_update.score_key!r}] is {actual_value!r}, "
                    f"expected {score_update.old_value!r}"
                )


def _validate_change_set_is_fresh(change_set: WorldChangeSet, context: _ReducerRuntimeContext) -> None:
    if context.location_index is not None and context.location_name_index is not None:
        for location_update in change_set.location_updates:
            _validate_location_rename_update_is_fresh(
                context.location_index,
                context.location_name_index,
                location_update,
            )
    if context.location_index is not None:
        for occupation_update in change_set.occupation_updates:
            _validate_location_occupation_update_is_fresh(context.location_index, occupation_update)
    for route_update in change_set.route_updates:
        _validate_route_update_is_fresh(context.routes, route_update)
    if context.terrain_map is not None:
        for terrain_update in change_set.terrain_updates:
            _validate_terrain_update_is_fresh(context.terrain_map, terrain_update)
    if context.era_runtime is not None:
        for era_update in change_set.era_updates:
            _validate_era_runtime_update_is_fresh(context.era_runtime, era_update)


def _apply_runtime_updates(
    change_set: WorldChangeSet,
    context: _ReducerRuntimeContext,
) -> _AppliedRuntimeUpdates:
    applied = _AppliedRuntimeUpdates.empty()
    if context.location_index is not None and context.location_name_index is not None:
        for location_update in change_set.location_updates:
            _apply_location_rename_update(
                context.location_index,
                context.location_name_index,
                location_update,
            )
            applied.location_updates.append(location_update)
    if context.location_index is not None:
        for occupation_update in change_set.occupation_updates:
            _apply_location_occupation_update(context.location_index, occupation_update)
            applied.occupation_updates.append(occupation_update)
    for route_update in change_set.route_updates:
        _apply_route_update(context.routes, route_update)
        applied.route_updates.append(route_update)
    if context.terrain_map is not None:
        for terrain_update in change_set.terrain_updates:
            _apply_terrain_update(context.terrain_map, terrain_update)
            applied.terrain_updates.append(terrain_update)
    if context.era_runtime is not None:
        for era_update in change_set.era_updates:
            _apply_era_runtime_update(context.era_runtime, era_update)
            applied.era_updates.append(era_update)
    return applied


def _rollback_runtime_updates(
    applied: _AppliedRuntimeUpdates,
    context: _ReducerRuntimeContext,
) -> None:
    if context.era_runtime is not None:
        for era_update in reversed(applied.era_updates):
            _rollback_era_runtime_update(context.era_runtime, era_update)
    if context.terrain_map is not None:
        for terrain_update in reversed(applied.terrain_updates):
            _rollback_terrain_update(context.terrain_map, terrain_update)
    for route_update in reversed(applied.route_updates):
        _rollback_route_update(context.routes, route_update)
    if context.location_index is not None:
        for occupation_update in reversed(applied.occupation_updates):
            _rollback_location_occupation_update(context.location_index, occupation_update)
    if context.location_index is not None and context.location_name_index is not None:
        for location_update in reversed(applied.location_updates):
            _rollback_location_rename_update(
                context.location_index,
                context.location_name_index,
                location_update,
            )


def _record_world_change_events(
    events: Iterable[WorldEventRecord],
    record_event: EventRecorderInput,
) -> tuple[WorldEventRecord, ...]:
    if _is_event_recorder_port(record_event):
        recorder_port = cast(EventRecorderPort, record_event)
        return tuple(recorder_port.record(record) for record in events)
    recorder = cast(EventRecorder, record_event)
    return tuple(recorder(record) for record in events)


def apply_world_change_set(
    change_set: WorldChangeSet,
    *,
    routes: Iterable[SupportsRouteStatus],
    record_event: EventRecorderInput,
    location_index: MutableMapping[str, Any] | None = None,
    location_name_index: MutableMapping[str, Any] | None = None,
    terrain_map: Any | None = None,
    era_runtime: Any | None = None,
) -> tuple[WorldEventRecord, ...]:
    """Apply a prepared ChangeSet and append its canonical events."""
    context = _ReducerRuntimeContext(
        routes=routes,
        location_index=location_index,
        location_name_index=location_name_index,
        terrain_map=terrain_map,
        era_runtime=era_runtime,
    )
    event_recording_snapshot = _event_recording_snapshot(change_set, record_event)
    _validate_runtime_requirements(change_set, context)
    _validate_change_set_is_fresh(change_set, context)
    applied_updates = _AppliedRuntimeUpdates.empty()
    try:
        applied_updates = _apply_runtime_updates(change_set, context)
        return _record_world_change_events(change_set.events, record_event)
    except Exception:
        if event_recording_snapshot is not None and _is_event_recorder_port(record_event):
            cast(EventRecorderPort, record_event).restore(event_recording_snapshot)
        _rollback_runtime_updates(applied_updates, context)
        raise

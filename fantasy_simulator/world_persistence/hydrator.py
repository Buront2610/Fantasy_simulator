"""Hydrator for ``World`` persistence payloads."""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Type

from ..content.setting_bundle import CalendarDefinition, bundle_from_dict_validated
from ..language.state import LanguageEvolutionRecord, LanguageRuntimeState, LocationNameHistoryRecord
from ..terrain import AtlasLayout
from ..world_event.record_updates import normalize_event_record_locations
from ..world_arc import WorldArc
from .terrain import (
    apply_sparse_terrain_event_overlay,
    restore_bundle_terrain_snapshot,
)
from ..world_topology.state import restore_serialized_topology


_UNSUPPORTED_ERA_RUNTIME_FIELDS = frozenset({
    "era_key",
    "civilization_phase",
    "world_scores",
    "era_runtime",
})


def _discard_unsupported_era_runtime_fields(data: Dict[str, Any]) -> None:
    """Drop experimental PR-K era runtime snapshots before hydration.

    In schema v9, canonical event records are the only durable source for
    era/civilization projections. These fields may appear in experimental
    payloads, but must not become observable runtime state.
    """
    for field_name in _UNSUPPORTED_ERA_RUNTIME_FIELDS:
        data.pop(field_name, None)


def _serialized_location_id_aliases(world: Any, serialized_grid: list[Any]) -> Dict[str, str]:
    """Map serialized location ids to active bundle ids when names still match."""
    aliases: Dict[str, str] = {}
    for loc_data in serialized_grid:
        if not isinstance(loc_data, dict):
            continue
        raw_id = loc_data.get("id")
        if not raw_id:
            continue
        raw_id_text = str(raw_id)
        canonical_name = str(loc_data.get("canonical_name") or loc_data.get("name") or "")
        normalized = world.normalize_location_id(raw_id_text, location_name=canonical_name)
        if normalized and normalized in world._location_id_index:
            aliases[raw_id_text] = normalized
    return aliases


def _normalize_serialized_route_endpoints(
    serialized_routes: Any,
    location_id_aliases: Mapping[str, str],
) -> list[Any]:
    """Rewrite stale serialized route endpoint ids before strict route-state overlay."""
    normalized_routes: list[Any] = []
    for route_data in list(serialized_routes or []):
        if not isinstance(route_data, dict):
            normalized_routes.append(route_data)
            continue
        normalized = dict(route_data)
        for key in ("from_site_id", "to_site_id"):
            value = normalized.get(key)
            if isinstance(value, str) and value in location_id_aliases:
                normalized[key] = location_id_aliases[value]
        normalized_routes.append(normalized)
    return normalized_routes


def _hydrate_world_bundle_and_grid(world: Any, data: Dict[str, Any], serialized_grid: list[Any]) -> bool:
    """Restore setting-bundle metadata and grid state, returning bundle-backed topology status."""
    if "setting_bundle" not in data:
        world._register_serialized_grid_locations(serialized_grid)
        return False

    world._set_setting_bundle_metadata(
        bundle_from_dict_validated(
            data["setting_bundle"],
            source="embedded world.setting_bundle",
        )
    )
    if world._serialized_grid_is_compatible_with_active_bundle(serialized_grid):
        world._build_default_map()
        world._overlay_serialized_grid_runtime_state(serialized_grid)
        return True
    world._register_serialized_grid_locations(serialized_grid)
    return False


def _hydrate_event_records(world: Any, data: Dict[str, Any], world_event_record_cls: Type[Any]) -> None:
    """Restore canonical event records and normalize location references."""
    world.event_records = [
        world_event_record_cls.from_dict(r) for r in data.get("event_records", [])
    ]
    world.event_records = normalize_event_record_locations(
        world.event_records,
        world.normalize_location_id,
    )


def _hydrate_world_arcs(world: Any, data: Dict[str, Any]) -> None:
    """Restore durable long-running world process state."""
    world.world_arcs = []
    for item in data.get("world_arcs", []):
        arc = WorldArc.from_dict(item)
        arc.location_ids = tuple(
            normalized
            for location_id in arc.location_ids
            for normalized in [world.normalize_location_id(location_id)]
            if normalized is not None
        )
        world.world_arcs.append(arc)


def _hydrate_rumors(world: Any, data: Dict[str, Any]) -> None:
    """Restore rumor state and normalize source locations."""
    from ..rumor import Rumor

    world.rumors = [
        Rumor.from_dict(r) for r in data.get("rumors", [])
    ]
    for rumor in world.rumors:
        rumor.source_location_id = world.normalize_location_id(rumor.source_location_id)

    world.rumor_archive = [
        Rumor.from_dict(r) for r in data.get("rumor_archive", [])
    ]
    for rumor in world.rumor_archive:
        rumor.source_location_id = world.normalize_location_id(rumor.source_location_id)


def _hydrate_adventures(world: Any, data: Dict[str, Any]) -> None:
    """Restore adventure runs and normalize endpoint locations."""
    from ..adventure import AdventureRun

    world.active_adventures = [
        AdventureRun.from_dict(run) for run in data.get("active_adventures", [])
    ]
    world.completed_adventures = [
        AdventureRun.from_dict(run) for run in data.get("completed_adventures", [])
    ]
    for run in world.active_adventures + world.completed_adventures:
        run.origin = world.normalize_location_id(run.origin) or run.origin
        run.destination = world.normalize_location_id(run.destination) or run.destination


def _hydrate_calendar_and_language(
    world: Any,
    data: Dict[str, Any],
    *,
    calendar_change_record_cls: Type[Any],
    clone_calendar: Callable[[Any], Any],
) -> None:
    """Restore calendar baseline/history and language runtime state."""
    world.calendar_baseline = CalendarDefinition.from_dict(
        data.get(
            "calendar_baseline",
            world.setting_bundle.world_definition.calendar.to_dict(),
        )
    )
    world.calendar_history = [
        calendar_change_record_cls.from_dict(item)
        for item in data.get("calendar_history", [])
    ]
    world.language_origin_year = int(data.get("language_origin_year", world.year))
    world.language_evolution_history = [
        LanguageEvolutionRecord.from_dict(item)
        for item in data.get("language_evolution_history", [])
    ]
    world.location_name_history = [
        LocationNameHistoryRecord.from_dict(item)
        for item in data.get("location_name_history", [])
    ]
    persisted_runtime_states = {
        key: LanguageRuntimeState.from_dict(value)
        for key, value in dict(data.get("language_runtime_states", {})).items()
    }
    world._language_runtime_states = {}
    world._language_engine = None
    if world.language_evolution_history:
        for record in world.language_evolution_history:
            world._apply_language_evolution_record(record)
    else:
        world._language_runtime_states = persisted_runtime_states

    if "calendar_baseline" not in data:
        world.calendar_baseline = clone_calendar(world.setting_bundle.world_definition.calendar)


def _hydrate_topology(world: Any, data: Dict[str, Any], *, bundle_backed_structure: bool) -> None:
    """Restore topology, sparse terrain overlays, route state, and atlas layout."""
    if bundle_backed_structure:
        world._build_terrain_from_grid()
        if "terrain_map" in data:
            world.terrain_map = restore_bundle_terrain_snapshot(
                data["terrain_map"],
                width=world.width,
                height=world.height,
            )
        elif world.terrain_map is not None:
            apply_sparse_terrain_event_overlay(world.terrain_map, world.event_records)
        route_endpoint_aliases = _serialized_location_id_aliases(world, list(data.get("grid", [])))
        serialized_routes = _normalize_serialized_route_endpoints(
            data.get("routes", []),
            route_endpoint_aliases,
        )
        world._overlay_serialized_route_state(serialized_routes)
        world._rebuild_route_index()
    elif "terrain_map" in data:
        world._apply_topology_state(
            restore_serialized_topology(
                terrain_map_data=data["terrain_map"],
                site_data=list(data.get("sites", [])),
                route_data=list(data.get("routes", [])),
                normalize_location_id=world.normalize_location_id,
                location_index=world._location_id_index,
            )
        )
    else:
        world._build_terrain_from_grid()

    if "atlas_layout" in data:
        world.atlas_layout = AtlasLayout.from_dict(data["atlas_layout"])
    else:
        world.atlas_layout = world._build_atlas_layout_from_current_state()


def _refresh_loaded_endonyms(world: Any, data: Dict[str, Any]) -> None:
    """Restore generated endonym invariants after load."""
    if "setting_bundle" in data:
        world._refresh_generated_endonyms()
        return
    for location in world.grid.values():
        generated_endonym = location.generated_endonym.strip()
        if generated_endonym:
            location.generated_endonym = generated_endonym
            location.aliases = [
                alias for alias in location.aliases if alias != generated_endonym
            ]
            continue
        endonym = world.location_endonym(location.id)
        location.generated_endonym = (
            endonym if endonym and endonym != location.canonical_name else ""
        )


def hydrate_world_state(
    world: Any,
    data: Dict[str, Any],
    *,
    memorial_record_cls: Type[Any],
    world_event_record_cls: Type[Any],
    calendar_change_record_cls: Type[Any],
    clone_calendar: Callable[[Any], Any],
) -> Any:
    """Hydrate a world instance from serialized state."""
    _discard_unsupported_era_runtime_fields(data)
    serialized_grid = list(data.get("grid", []))
    bundle_backed_structure = _hydrate_world_bundle_and_grid(world, data, serialized_grid)
    _hydrate_event_records(world, data, world_event_record_cls)
    _hydrate_world_arcs(world, data)
    _hydrate_rumors(world, data)
    _hydrate_adventures(world, data)
    world.memorials = {
        k: memorial_record_cls.from_dict(v) for k, v in data.get("memorials", {}).items()
    }
    _hydrate_calendar_and_language(
        world,
        data,
        calendar_change_record_cls=calendar_change_record_cls,
        clone_calendar=clone_calendar,
    )
    _hydrate_topology(world, data, bundle_backed_structure=bundle_backed_structure)
    _refresh_loaded_endonyms(world, data)
    if "location_name_history" not in data:
        world._seed_initial_location_name_history()
    world.normalize_after_load()
    return world

"""Persistence helpers for ``World`` serialization and hydration."""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Type

from .content.setting_bundle import CalendarDefinition, bundle_from_dict_validated
from .language.state import LanguageEvolutionRecord, LanguageRuntimeState
from .terrain import AtlasLayout
from .world_event_record_updates import normalize_event_record_locations
from .world_topology_state import restore_serialized_topology


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


def serialize_world_state(world: Any) -> Dict[str, Any]:
    """Build the serialized payload for a world instance."""
    lore_text = world._setting_bundle.world_definition.lore_text
    result: Dict[str, Any] = {
        "name": world.name,
        "lore": lore_text,
        "width": world.width,
        "height": world.height,
        "year": world.year,
        "grid": [loc.to_dict() for loc in world.grid.values()],
        "event_records": [r.to_dict() for r in world.event_records],
        "rumors": [r.to_dict() for r in world.rumors],
        "rumor_archive": [r.to_dict() for r in world.rumor_archive],
        "active_adventures": [run.to_dict() for run in world.active_adventures],
        "completed_adventures": [run.to_dict() for run in world.completed_adventures],
        "memorials": {k: v.to_dict() for k, v in world.memorials.items()},
        "calendar_baseline": world.calendar_baseline.to_dict(),
        "calendar_history": [entry.to_dict() for entry in world.calendar_history],
        "language_origin_year": world.language_origin_year,
        "language_evolution_history": [entry.to_dict() for entry in world.language_evolution_history],
        "language_runtime_states": {
            key: state.to_dict()
            for key, state in world._language_runtime_states.items()
        },
    }
    bundle_backed_topology = world._setting_bundle is not None and world._grid_matches_bundle_seeds()
    if world.terrain_map is not None and not bundle_backed_topology:
        result["terrain_map"] = world.terrain_map.to_dict()
    if world.sites and not bundle_backed_topology:
        result["sites"] = [s.to_dict() for s in world.sites]
    if world.routes:
        result["routes"] = [r.to_dict() for r in world.routes]
    if world.atlas_layout is not None:
        result["atlas_layout"] = world.atlas_layout.to_dict()
    if world._setting_bundle is not None:
        result["setting_bundle"] = world._setting_bundle.to_dict()
    return result


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
    from .adventure import AdventureRun
    from .rumor import Rumor

    serialized_grid = list(data.get("grid", []))
    bundle_backed_structure = False
    if "setting_bundle" in data:
        world._set_setting_bundle_metadata(
            bundle_from_dict_validated(
                data["setting_bundle"],
                source="embedded world.setting_bundle",
            )
        )
        if world._serialized_grid_is_compatible_with_active_bundle(serialized_grid):
            bundle_backed_structure = True
            world._build_default_map()
            world._overlay_serialized_grid_runtime_state(serialized_grid)
        else:
            world._register_serialized_grid_locations(serialized_grid)
    else:
        world._register_serialized_grid_locations(serialized_grid)

    world._restore_display_event_log_for_load(list(data.get("event_log", [])))
    world.event_records = [
        world_event_record_cls.from_dict(r) for r in data.get("event_records", [])
    ]
    world.event_records = normalize_event_record_locations(
        world.event_records,
        world.normalize_location_id,
    )

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

    world.active_adventures = [
        AdventureRun.from_dict(run) for run in data.get("active_adventures", [])
    ]
    world.completed_adventures = [
        AdventureRun.from_dict(run) for run in data.get("completed_adventures", [])
    ]
    for run in world.active_adventures + world.completed_adventures:
        run.origin = world.normalize_location_id(run.origin) or run.origin
        run.destination = world.normalize_location_id(run.destination) or run.destination

    world.memorials = {
        k: memorial_record_cls.from_dict(v) for k, v in data.get("memorials", {}).items()
    }
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

    if bundle_backed_structure:
        world._build_terrain_from_grid()
        route_endpoint_aliases = _serialized_location_id_aliases(world, serialized_grid)
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

    if "calendar_baseline" not in data:
        world.calendar_baseline = clone_calendar(world.setting_bundle.world_definition.calendar)

    if "setting_bundle" in data:
        world._refresh_generated_endonyms()
    else:
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
    world.normalize_after_load()
    return world

"""Persistence helpers for ``World`` serialization and hydration."""

from __future__ import annotations

from typing import Any, Callable, Dict, Mapping, Type

from .content.setting_bundle import CalendarDefinition, bundle_from_dict_validated
from .language.state import LanguageEvolutionRecord, LanguageRuntimeState
from .terrain import AtlasLayout, BIOME_TYPES, TerrainMap
from .world_event_record_updates import normalize_event_record_locations
from .world_topology_state import build_topology_from_locations, restore_serialized_topology


_TERRAIN_CELL_MUTATION_KIND = "terrain_cell_mutated"
_TERRAIN_MUTATION_ATTRIBUTES = ("biome", "elevation", "moisture", "temperature")


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


def _terrain_maps_equal(left: TerrainMap, right: TerrainMap) -> bool:
    """Return whether two terrain maps have the same full cell state."""
    if left.width != right.width or left.height != right.height:
        return False
    if set(left.cells) != set(right.cells):
        return False
    for coord, left_cell in left.cells.items():
        right_cell = right.cells[coord]
        if left_cell.to_dict() != right_cell.to_dict():
            return False
    return True


def _bundle_derived_terrain(world: Any) -> TerrainMap | None:
    """Return the terrain map currently derivable from the active bundle."""
    location_ids = set(world._location_id_index)
    return build_topology_from_locations(
        width=world.width,
        height=world.height,
        locations=world.grid.values(),
        route_specs=[
            seed.to_dict()
            for seed in world._setting_bundle.world_definition.route_seeds
            if seed.from_site_id in location_ids and seed.to_site_id in location_ids
        ],
        explicit_route_graph=True,
    ).terrain_map


def _clone_terrain_map(terrain_map: TerrainMap) -> TerrainMap:
    """Return a detached copy of a terrain map."""
    return TerrainMap.from_dict(terrain_map.to_dict())


def _terrain_record_coords(record: Any) -> tuple[int, int]:
    """Extract terrain-cell coordinates from a canonical mutation record."""
    params = record.render_params
    x = params.get("x")
    y = params.get("y")
    if type(x) is not int or type(y) is not int:
        raise ValueError("terrain_cell_mutated records must include integer x/y render params")
    return x, y


def _terrain_record_value(record: Any, prefix: str, attribute: str) -> Any:
    """Extract and validate a recorded terrain attribute value."""
    key = f"{prefix}_{attribute}"
    if key not in record.render_params:
        raise ValueError(f"terrain_cell_mutated records must include {key!r}")
    value = record.render_params[key]
    if attribute == "biome":
        if not isinstance(value, str) or value not in BIOME_TYPES:
            raise ValueError("terrain_cell_mutated biome must be a known terrain biome")
        return value
    if type(value) is not int or not 0 <= value <= 255:
        raise ValueError(f"terrain_cell_mutated {attribute} must be an integer between 0 and 255")
    return value


def _terrain_record_changed_attributes(record: Any) -> list[str]:
    """Return the validated changed-attribute list from a terrain record."""
    changed_attributes = record.render_params.get("changed_attributes")
    if not isinstance(changed_attributes, list) or not changed_attributes:
        raise ValueError("terrain_cell_mutated records must include non-empty changed_attributes")
    if any(attribute not in _TERRAIN_MUTATION_ATTRIBUTES for attribute in changed_attributes):
        raise ValueError("terrain_cell_mutated changed_attributes contains an unknown attribute")
    if len(set(changed_attributes)) != len(changed_attributes):
        raise ValueError("terrain_cell_mutated changed_attributes contains duplicates")
    return [str(attribute) for attribute in changed_attributes]


def _apply_terrain_mutation_record(terrain_map: TerrainMap, record: Any) -> None:
    """Overlay one canonical terrain-cell mutation record onto a terrain map."""
    if record.kind != _TERRAIN_CELL_MUTATION_KIND:
        return
    x, y = _terrain_record_coords(record)
    terrain_cell_id = record.render_params.get("terrain_cell_id")
    if terrain_cell_id != f"terrain:{x}:{y}":
        raise ValueError("terrain_cell_mutated terrain_cell_id must match x/y coordinates")
    if not terrain_map.in_bounds(x, y):
        raise ValueError(f"terrain_cell_mutated record is outside terrain bounds: ({x}, {y})")
    cell = terrain_map.get(x, y)
    if cell is None:
        raise ValueError(f"terrain_cell_mutated record targets missing terrain cell: ({x}, {y})")
    changed_attributes = _terrain_record_changed_attributes(record)
    expected_changed_attributes: list[str] = []
    for attribute in _TERRAIN_MUTATION_ATTRIBUTES:
        old_value = _terrain_record_value(record, "old", attribute)
        new_value = _terrain_record_value(record, "new", attribute)
        if getattr(cell, attribute) != old_value:
            raise ValueError(f"terrain_cell_mutated record is stale for {attribute!r}")
        if old_value != new_value:
            expected_changed_attributes.append(attribute)
    if set(changed_attributes) != set(expected_changed_attributes):
        raise ValueError("terrain_cell_mutated changed_attributes disagrees with old/new values")
    for attribute in _TERRAIN_MUTATION_ATTRIBUTES:
        setattr(cell, attribute, _terrain_record_value(record, "new", attribute))


def _apply_sparse_terrain_event_overlay(terrain_map: TerrainMap, records: list[Any]) -> None:
    """Replay canonical terrain-cell records as the sparse terrain overlay."""
    for record in records:
        _apply_terrain_mutation_record(terrain_map, record)


def _terrain_matches_sparse_event_overlay(world: Any, derived: TerrainMap | None) -> bool:
    """Return whether terrain can be restored from bundle terrain plus canonical records."""
    if world.terrain_map is None or derived is None:
        return False
    replayed = _clone_terrain_map(derived)
    try:
        _apply_sparse_terrain_event_overlay(replayed, list(world.event_records))
    except (AttributeError, TypeError, ValueError):
        return False
    return _terrain_maps_equal(world.terrain_map, replayed)


def _current_grid_can_overlay_bundle_structure(world: Any) -> bool:
    """Return whether current grid shape can be restored from bundle seeds plus runtime overlay."""
    if world._setting_bundle is None:
        return False

    expected_by_id = {
        seed.location_id: seed
        for seed in world._setting_bundle.world_definition.site_seeds
        if 0 <= seed.x < world.width and 0 <= seed.y < world.height
    }
    current_by_id: Dict[str, Any] = {}
    for location in world.grid.values():
        normalized_id = world.normalize_location_id(location.id, location_name=location.canonical_name)
        if normalized_id is None or normalized_id in current_by_id:
            return False
        current_by_id[normalized_id] = location
    if set(current_by_id) != set(expected_by_id):
        return False

    for location_id, seed in expected_by_id.items():
        location = current_by_id[location_id]
        if (
            location.region_type != seed.region_type
            or int(location.x) != int(seed.x)
            or int(location.y) != int(seed.y)
        ):
            return False
    return True


def _restore_bundle_terrain_snapshot(terrain_map_data: Any, *, width: int, height: int) -> TerrainMap:
    """Restore a bundle-backed terrain override and require a complete grid."""
    if not isinstance(terrain_map_data, dict):
        raise ValueError("Serialized terrain_map must be a dict")
    if terrain_map_data.get("width") != width or terrain_map_data.get("height") != height:
        raise ValueError("Serialized terrain_map dimensions disagree with world dimensions")
    raw_cells = terrain_map_data.get("cells")
    if not isinstance(raw_cells, list):
        raise ValueError("Serialized terrain_map cells must be a list")

    seen_coords: set[tuple[int, int]] = set()
    for cell_data in raw_cells:
        if not isinstance(cell_data, dict):
            raise ValueError("Serialized terrain_map cells must be dicts")
        x = cell_data.get("x")
        y = cell_data.get("y")
        if type(x) is not int or type(y) is not int:
            raise ValueError("Serialized terrain_map cell coordinates must be integers")
        if not 0 <= x < width or not 0 <= y < height:
            raise ValueError("Serialized terrain_map cell is outside world bounds")
        coord = (x, y)
        if coord in seen_coords:
            raise ValueError(f"Serialized terrain_map contains duplicate cell: {coord!r}")
        seen_coords.add(coord)

    expected_coords = {
        (x, y)
        for y in range(height)
        for x in range(width)
    }
    if seen_coords != expected_coords:
        raise ValueError("Serialized terrain_map must contain every world cell exactly once")
    return TerrainMap.from_dict(terrain_map_data)


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
    bundle_backed_topology = _current_grid_can_overlay_bundle_structure(world)
    bundle_terrain = _bundle_derived_terrain(world) if bundle_backed_topology else None
    bundle_terrain_is_sparse_replayable = bundle_backed_topology and _terrain_matches_sparse_event_overlay(
        world,
        bundle_terrain,
    )
    if world.terrain_map is not None and not bundle_terrain_is_sparse_replayable:
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
        if "terrain_map" in data:
            world.terrain_map = _restore_bundle_terrain_snapshot(
                data["terrain_map"],
                width=world.width,
                height=world.height,
            )
        elif world.terrain_map is not None:
            _apply_sparse_terrain_event_overlay(world.terrain_map, world.event_records)
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

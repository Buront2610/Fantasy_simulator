"""Terrain persistence helpers for ``World`` save/load."""

from __future__ import annotations

from typing import Any, Dict

from .terrain import BIOME_TYPES, TerrainMap
from .world_topology_state import build_topology_from_locations


_TERRAIN_CELL_MUTATION_KIND = "terrain_cell_mutated"
_TERRAIN_MUTATION_ATTRIBUTES = ("biome", "elevation", "moisture", "temperature")


def terrain_maps_equal(left: TerrainMap, right: TerrainMap) -> bool:
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


def bundle_derived_terrain(world: Any) -> TerrainMap | None:
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


def clone_terrain_map(terrain_map: TerrainMap) -> TerrainMap:
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


def apply_sparse_terrain_event_overlay(terrain_map: TerrainMap, records: list[Any]) -> None:
    """Replay canonical terrain-cell records as the sparse terrain overlay."""
    for record in records:
        _apply_terrain_mutation_record(terrain_map, record)


def _terrain_matches_sparse_event_overlay(world: Any, derived: TerrainMap | None) -> bool:
    """Return whether terrain can be restored from bundle terrain plus canonical records."""
    if world.terrain_map is None or derived is None:
        return False
    replayed = clone_terrain_map(derived)
    try:
        apply_sparse_terrain_event_overlay(replayed, list(world.event_records))
    except (AttributeError, TypeError, ValueError):
        return False
    return terrain_maps_equal(world.terrain_map, replayed)


def bundle_terrain_can_omit_snapshot(world: Any, derived: TerrainMap | None) -> bool:
    """Return whether bundle terrain can be saved without a full terrain snapshot."""
    if world.terrain_map is None or derived is None:
        return False
    if terrain_maps_equal(world.terrain_map, derived):
        return True
    has_sparse_records = any(
        getattr(record, "kind", None) == _TERRAIN_CELL_MUTATION_KIND
        for record in world.event_records
    )
    return has_sparse_records and _terrain_matches_sparse_event_overlay(world, derived)


def current_grid_can_overlay_bundle_structure(world: Any) -> bool:
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


def restore_bundle_terrain_snapshot(terrain_map_data: Any, *, width: int, height: int) -> TerrainMap:
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

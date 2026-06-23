"""Serializer for ``World`` persistence payloads."""

from __future__ import annotations

from typing import Any, Dict

from .terrain import (
    bundle_derived_terrain,
    bundle_terrain_can_omit_snapshot,
    current_grid_can_overlay_bundle_structure,
)


def _serialize_base_world_state(world: Any) -> Dict[str, Any]:
    """Build the payload fields that are always serialized."""
    lore_text = world._setting_bundle.world_definition.lore_text
    return {
        "name": world.name,
        "lore": lore_text,
        "width": world.width,
        "height": world.height,
        "year": world.year,
        "grid": [loc.to_dict() for loc in world.grid.values()],
        "event_records": [r.to_dict() for r in world.event_records],
        "world_arcs": [arc.to_dict() for arc in world.world_arcs],
        "rumors": [r.to_dict() for r in world.rumors],
        "rumor_archive": [r.to_dict() for r in world.rumor_archive],
        "active_adventures": [run.to_dict() for run in world.active_adventures],
        "completed_adventures": [run.to_dict() for run in world.completed_adventures],
        "memorials": {k: v.to_dict() for k, v in world.memorials.items()},
        "calendar_baseline": world.calendar_baseline.to_dict(),
        "calendar_history": [entry.to_dict() for entry in world.calendar_history],
        "language_origin_year": world.language_origin_year,
        "language_evolution_history": [entry.to_dict() for entry in world.language_evolution_history],
        "location_name_history": [entry.to_dict() for entry in world.location_name_history],
        "language_runtime_states": {
            key: state.to_dict()
            for key, state in world._language_runtime_states.items()
        },
    }


def _append_topology_payload(world: Any, result: Dict[str, Any]) -> None:
    """Append topology fields while preserving the v8 payload shape."""
    bundle_backed_topology = current_grid_can_overlay_bundle_structure(world)
    bundle_terrain = bundle_derived_terrain(world) if bundle_backed_topology else None
    bundle_terrain_is_snapshot_omittable = bundle_backed_topology and bundle_terrain_can_omit_snapshot(
        world,
        bundle_terrain,
    )
    if world.terrain_map is not None and not bundle_terrain_is_snapshot_omittable:
        result["terrain_map"] = world.terrain_map.to_dict()
    if world.sites and not bundle_backed_topology:
        result["sites"] = [s.to_dict() for s in world.sites]
    if world.routes:
        result["routes"] = [r.to_dict() for r in world.routes]
    if world.atlas_layout is not None:
        result["atlas_layout"] = world.atlas_layout.to_dict()
    if world._setting_bundle is not None:
        result["setting_bundle"] = world._setting_bundle.to_dict()


def serialize_world_state(world: Any) -> Dict[str, Any]:
    """Build the serialized payload for a world instance."""
    result = _serialize_base_world_state(world)
    _append_topology_payload(world, result)
    return result

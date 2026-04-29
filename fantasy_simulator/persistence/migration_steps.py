"""Version-by-version save-data migration steps."""

from __future__ import annotations

from typing import Any, Dict

from ..terrain import (
    assemble_atlas_layout_inputs,
    build_default_atlas_layout,
    build_terrain_payload_from_locations,
)
from .migration_context import (
    default_locations_for_data,
    location_state_defaults,
    location_name_to_id,
    resolve_location_id,
    site_tags_by_location_id,
)
from .migration_event_records import canonicalize_legacy_event_adapters


def migrate_v0_to_v1(data: Dict[str, Any]) -> Dict[str, Any]:
    data["schema_version"] = 1
    return data


def migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert legacy location name strings to location_ids."""
    for char_data in data.get("characters", []):
        if "location_id" in char_data:
            continue
        old_name = char_data.pop("location", "Aethoria Capital")
        char_data["location_id"] = resolve_location_id(data, old_name)

    world_data = data.get("world", {})
    for loc_data in world_data.get("grid", []):
        if "id" in loc_data:
            continue
        name = loc_data.get("canonical_name") or loc_data.get("name", "")
        loc_data["id"] = resolve_location_id(data, name)

    for bucket in ("active_adventures", "completed_adventures"):
        for adventure in world_data.get(bucket, []):
            if "origin" in adventure:
                origin = adventure["origin"]
                adventure["origin"] = resolve_location_id(data, origin)
            if "destination" in adventure:
                destination = adventure["destination"]
                adventure["destination"] = resolve_location_id(data, destination)

    data["schema_version"] = 2
    return data


def migrate_v2_to_v3(data: Dict[str, Any]) -> Dict[str, Any]:
    """Populate LocationState fields, Character spotlight flags, and missing default locations."""
    world_data = data.setdefault("world", {})
    grid = world_data.setdefault("grid", [])

    width = world_data.get("width", 5)
    height = world_data.get("height", 5)
    site_tags = site_tags_by_location_id(data)
    existing_ids = {
        loc_data.get("id") or location_name_to_id(data).get(
            loc_data.get("canonical_name") or loc_data.get("name", ""), ""
        )
        for loc_data in grid
    }
    for loc_id, name, desc, region_type, x, y in default_locations_for_data(data):
        if loc_id in existing_ids:
            continue
        if not (0 <= x < width and 0 <= y < height):
            continue
        defaults = location_state_defaults(
            loc_id,
            region_type,
            site_tags=site_tags.get(loc_id),
        )
        grid.append({
            "id": loc_id,
            "canonical_name": name,
            "name": name,
            "description": desc,
            "region_type": region_type,
            "x": x,
            "y": y,
            **defaults,
            "visited": False,
            "controlling_faction_id": None,
            "recent_event_ids": [],
            "aliases": [],
            "memorial_ids": [],
        })

    valid_location_ids = set()

    for loc_data in grid:
        loc_id = loc_data.get("id")
        if not loc_id:
            name = loc_data.get("canonical_name") or loc_data.get("name", "")
            loc_id = resolve_location_id(data, name)
            loc_data["id"] = loc_id
        canonical_name = loc_data.get("canonical_name") or loc_data.get("name", "")
        loc_data["canonical_name"] = canonical_name
        loc_data.setdefault("name", canonical_name)

        region_type = loc_data.get("region_type", "city")
        defaults = location_state_defaults(
            loc_id,
            region_type,
            site_tags=site_tags.get(loc_id),
        )
        for field_name, default_value in defaults.items():
            loc_data.setdefault(field_name, default_value)
        loc_data.setdefault("visited", False)
        loc_data.setdefault("controlling_faction_id", None)
        loc_data.setdefault("recent_event_ids", [])
        loc_data.setdefault("aliases", [])
        loc_data.setdefault("memorial_ids", [])
        valid_location_ids.add(loc_id)

    for char_data in data.get("characters", []):
        char_data.setdefault("favorite", False)
        char_data.setdefault("spotlighted", False)
        char_data.setdefault("playable", False)

    recent_event_ids_by_location = {loc_id: [] for loc_id in valid_location_ids}
    for index, record in enumerate(world_data.get("event_records", []), start=1):
        record_id = record.get("record_id")
        if not record_id:
            record_id = f"legacy_record_{index}"
            record["record_id"] = record_id
        location_id = record.get("location_id")
        if location_id is not None and location_id not in valid_location_ids:
            record["location_id"] = None
            continue
        if location_id is not None:
            recent_event_ids_by_location[location_id].append(record_id)

    for loc_data in grid:
        loc_id = loc_data["id"]
        loc_data["recent_event_ids"] = recent_event_ids_by_location[loc_id][-12:]

    data["schema_version"] = 3
    return data


def migrate_v3_to_v4(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add party adventure fields to AdventureRun data."""
    world_data = data.setdefault("world", {})
    for bucket in ("active_adventures", "completed_adventures"):
        for adv in world_data.get(bucket, []):
            char_id = adv.get("character_id", "")
            if "member_ids" not in adv or not adv["member_ids"]:
                adv["member_ids"] = [char_id] if char_id else []
            adv.setdefault("party_id", None)
            adv.setdefault("policy", "cautious")
            adv.setdefault("retreat_rule", "on_serious")
            adv.setdefault("supply_state", "full")
            adv.setdefault("danger_level", 50)
    data["schema_version"] = 4
    return data


def migrate_v4_to_v5(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add world memory fields."""
    world_data = data.setdefault("world", {})
    for loc_data in world_data.get("grid", []):
        loc_data.setdefault("live_traces", [])
    world_data.setdefault("memorials", {})
    data["schema_version"] = 5
    return data


def migrate_v5_to_v6(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add terrain_map, sites, and routes to the world."""
    world_data = data.setdefault("world", {})
    grid = world_data.get("grid", [])
    width = world_data.get("width", 5)
    height = world_data.get("height", 5)

    payload = build_terrain_payload_from_locations(
        width=width,
        height=height,
        locations=[
            (
                loc_data.get("id", ""),
                loc_data.get("canonical_name") or loc_data.get("name", ""),
                loc_data.get("description", ""),
                loc_data.get("region_type", "city"),
                loc_data.get("x", 0),
                loc_data.get("y", 0),
            )
            for loc_data in grid
        ],
    )
    world_data["terrain_map"] = payload["terrain_map"]
    world_data["sites"] = payload["sites"]
    world_data["routes"] = payload["routes"]
    data["schema_version"] = 6
    return data


def migrate_v6_to_v7(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add atlas_layout and per-site atlas coordinates."""
    world_data = data.setdefault("world", {})
    width = world_data.get("width", 5)
    height = world_data.get("height", 5)

    sites = world_data.get("sites", [])
    inputs = assemble_atlas_layout_inputs(
        width=width,
        height=height,
        sites=sites,
        routes=world_data.get("routes", []),
        terrain_cells=world_data.get("terrain_map", {}).get("cells", []),
    )
    world_data["atlas_layout"] = build_default_atlas_layout(inputs).to_dict()

    data["schema_version"] = 7
    return data


def migrate_v7_to_v8(data: Dict[str, Any]) -> Dict[str, Any]:
    """Canonicalize legacy event adapters into world.event_records."""
    canonicalize_legacy_event_adapters(data)
    data["schema_version"] = 8
    return data

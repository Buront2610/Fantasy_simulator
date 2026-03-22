"""
migrations.py - Schema migration for save data.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from world_data import (
    NAME_TO_LOCATION_ID,
    fallback_location_id,
    get_location_state_defaults,
)

CURRENT_VERSION = 3


def migrate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Apply all necessary migrations to bring data to CURRENT_VERSION."""
    version = data.get("schema_version", 0)
    if version > CURRENT_VERSION:
        raise ValueError(
            f"Save data has schema_version {version}, but this build only supports up to {CURRENT_VERSION}. "
            "Please upgrade the application."
        )

    migrations: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
        1: _migrate_v0_to_v1,
        2: _migrate_v1_to_v2,
        3: _migrate_v2_to_v3,
    }
    for target_version in range(version + 1, CURRENT_VERSION + 1):
        data = migrations[target_version](data)
    return data


def _migrate_v0_to_v1(data: Dict[str, Any]) -> Dict[str, Any]:
    data["schema_version"] = 1
    return data


def _migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert legacy location name strings to location_ids."""
    for char_data in data.get("characters", []):
        if "location_id" in char_data:
            continue
        old_name = char_data.pop("location", "Aethoria Capital")
        char_data["location_id"] = NAME_TO_LOCATION_ID.get(old_name, fallback_location_id(old_name))

    world_data = data.get("world", {})
    for loc_data in world_data.get("grid", []):
        if "id" in loc_data:
            continue
        name = loc_data.get("canonical_name") or loc_data.get("name", "")
        loc_data["id"] = NAME_TO_LOCATION_ID.get(name, fallback_location_id(name))

    for bucket in ("active_adventures", "completed_adventures"):
        for adventure in world_data.get(bucket, []):
            if "origin" in adventure:
                origin = adventure["origin"]
                adventure["origin"] = NAME_TO_LOCATION_ID.get(origin, fallback_location_id(origin))
            if "destination" in adventure:
                destination = adventure["destination"]
                adventure["destination"] = NAME_TO_LOCATION_ID.get(
                    destination,
                    fallback_location_id(destination),
                )

    data["schema_version"] = 2
    return data


def _migrate_v2_to_v3(data: Dict[str, Any]) -> Dict[str, Any]:
    """Populate LocationState fields and Character spotlight flags."""
    world_data = data.setdefault("world", {})
    grid = world_data.setdefault("grid", [])
    valid_location_ids = set()

    for loc_data in grid:
        loc_id = loc_data.get("id")
        if not loc_id:
            name = loc_data.get("canonical_name") or loc_data.get("name", "")
            loc_id = NAME_TO_LOCATION_ID.get(name, fallback_location_id(name))
            loc_data["id"] = loc_id
        canonical_name = loc_data.get("canonical_name") or loc_data.get("name", "")
        loc_data["canonical_name"] = canonical_name
        loc_data.setdefault("name", canonical_name)

        region_type = loc_data.get("region_type", "city")
        defaults = get_location_state_defaults(loc_id, region_type)
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

    for record in world_data.get("event_records", []):
        location_id = record.get("location_id")
        if location_id is not None and location_id not in valid_location_ids:
            record["location_id"] = None

    data["schema_version"] = 3
    return data

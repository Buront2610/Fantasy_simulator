"""
migrations.py - Schema migration for save data.
"""
from __future__ import annotations

from typing import Any, Dict

from world_data import NAME_TO_LOCATION_ID, fallback_location_id

CURRENT_VERSION = 2


def migrate(data: Dict[str, Any]) -> Dict[str, Any]:
    """Apply all necessary migrations to bring data to CURRENT_VERSION."""
    version = data.get("schema_version", 1)
    if version < 2:
        data = _migrate_v1_to_v2(data)
    data["schema_version"] = CURRENT_VERSION
    return data


def _migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """Convert location name strings to location_ids."""
    for char_data in data.get("characters", []):
        if "location" in char_data and "location_id" not in char_data:
            old_name = char_data.pop("location")
            char_data["location_id"] = NAME_TO_LOCATION_ID.get(old_name, "loc_aethoria_capital")

    for loc_data in data.get("world", {}).get("grid", []):
        if "id" not in loc_data:
            name = loc_data.get("name", "")
            loc_data["id"] = NAME_TO_LOCATION_ID.get(name, fallback_location_id(name))

    for adv in data.get("world", {}).get("active_adventures", []):
        if "origin" in adv:
            adv["origin"] = NAME_TO_LOCATION_ID.get(adv["origin"], adv["origin"])
        if "destination" in adv:
            adv["destination"] = NAME_TO_LOCATION_ID.get(adv["destination"], adv["destination"])
    for adv in data.get("world", {}).get("completed_adventures", []):
        if "origin" in adv:
            adv["origin"] = NAME_TO_LOCATION_ID.get(adv["origin"], adv["origin"])
        if "destination" in adv:
            adv["destination"] = NAME_TO_LOCATION_ID.get(adv["destination"], adv["destination"])

    data["schema_version"] = 2
    return data

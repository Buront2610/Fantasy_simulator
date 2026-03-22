"""
migrations.py - Save-file migration chain for the Fantasy Simulator.

Each ``migrate_vN_to_vM`` function transforms a raw save-data dict from
schema version N to version M in-place and returns the updated dict.

Usage::

    from migrations import apply_migrations
    data = apply_migrations(json.load(f))
"""

from __future__ import annotations

from typing import Any, Callable, Dict

CURRENT_VERSION: int = 2

# ---------------------------------------------------------------------------
# Individual migration steps
# ---------------------------------------------------------------------------


def migrate_v0_to_v1(data: Dict[str, Any]) -> Dict[str, Any]:
    """v0 → v1: stamp schema_version onto legacy saves that have none."""
    data["schema_version"] = 1
    return data


def migrate_v1_to_v2(data: Dict[str, Any]) -> Dict[str, Any]:
    """v1 → v2: Location → LocationState, character.location → location_id.

    Changes applied:
    * Each location in ``world.grid`` gains ``id``, ``canonical_name``, and
      the seven numeric state fields with region-appropriate defaults.
    * Each character in ``characters`` gains ``location_id`` derived from
      its ``location`` canonical name.
    """
    from location import LOCATION_DEFAULTS, make_location_id

    # --- Migrate world grid locations ---
    world_data = data.get("world", {})
    new_grid = []
    for loc_data in world_data.get("grid", []):
        canonical_name: str = loc_data.get("canonical_name") or loc_data.get("name", "Unknown")
        loc_id: str = loc_data.get("id") or make_location_id(canonical_name)
        region_type: str = loc_data.get("region_type", "plains")
        defaults = LOCATION_DEFAULTS.get(region_type, LOCATION_DEFAULTS["plains"])
        new_loc: Dict[str, Any] = {
            **loc_data,
            "id": loc_id,
            "canonical_name": canonical_name,
            "visited": loc_data.get("visited", False),
            "controlling_faction_id": loc_data.get("controlling_faction_id"),
            "aliases": loc_data.get("aliases", []),
            "memorial_ids": loc_data.get("memorial_ids", []),
            "recent_event_ids": loc_data.get("recent_event_ids", []),
        }
        for key, default_val in defaults.items():
            new_loc.setdefault(key, default_val)
        new_grid.append(new_loc)
    world_data["grid"] = new_grid
    data["world"] = world_data

    # --- Migrate character location field ---
    new_chars = []
    for char_data in data.get("characters", []):
        if "location_id" not in char_data:
            location_name: str = char_data.get("location", "Aethoria Capital")
            char_data = {**char_data, "location_id": make_location_id(location_name)}
        new_chars.append(char_data)
    data["characters"] = new_chars

    data["schema_version"] = 2
    return data


# ---------------------------------------------------------------------------
# Migration registry
# ---------------------------------------------------------------------------

MIGRATIONS: Dict[int, Callable[[Dict[str, Any]], Dict[str, Any]]] = {
    1: migrate_v0_to_v1,
    2: migrate_v1_to_v2,
}


def apply_migrations(data: Dict[str, Any]) -> Dict[str, Any]:
    """Apply all pending migrations to bring *data* up to CURRENT_VERSION.

    The function is idempotent: calling it on an already-current snapshot
    returns the data unchanged.
    """
    version: int = data.get("schema_version", 0)
    for target in range(version + 1, CURRENT_VERSION + 1):
        fn = MIGRATIONS.get(target)
        if fn is not None:
            data = fn(data)
    return data

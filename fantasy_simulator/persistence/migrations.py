"""
migrations.py - Schema migration for save data.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from ..content.world_data import (
    DEFAULT_LOCATIONS,
    NAME_TO_LOCATION_ID,
    fallback_location_id,
    get_location_state_defaults,
)

CURRENT_VERSION = 6


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
        4: _migrate_v3_to_v4,
        5: _migrate_v4_to_v5,
        6: _migrate_v5_to_v6,
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
    """Populate LocationState fields, Character spotlight flags, and fill missing default locations.

    Legacy saves may contain only a subset of the default world
    locations.  This migration fills in any missing default locations
    so that ``World.from_dict()`` (which no longer creates default
    map entries) receives a complete grid.
    """
    world_data = data.setdefault("world", {})
    grid = world_data.setdefault("grid", [])

    # Fill in missing default locations for partial legacy saves
    width = world_data.get("width", 5)
    height = world_data.get("height", 5)
    existing_ids = {
        loc_data.get("id") or NAME_TO_LOCATION_ID.get(
            loc_data.get("canonical_name") or loc_data.get("name", ""), ""
        )
        for loc_data in grid
    }
    for loc_id, name, desc, region_type, x, y in DEFAULT_LOCATIONS:
        if loc_id in existing_ids:
            continue
        if not (0 <= x < width and 0 <= y < height):
            continue
        defaults = get_location_state_defaults(loc_id, region_type)
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


def _migrate_v3_to_v4(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add party adventure fields to AdventureRun data (PR-E).

    Pre-PR-E adventures are solo runs; migrate them to the new schema with
    member_ids=[character_id] and cautious/on_serious defaults.
    """
    world_data = data.setdefault("world", {})
    for bucket in ("active_adventures", "completed_adventures"):
        for adv in world_data.get(bucket, []):
            char_id = adv.get("character_id", "")
            # member_ids: solo legacy → [leader]
            if "member_ids" not in adv or not adv["member_ids"]:
                adv["member_ids"] = [char_id] if char_id else []
            adv.setdefault("party_id", None)
            adv.setdefault("policy", "cautious")
            adv.setdefault("retreat_rule", "on_serious")
            adv.setdefault("supply_state", "full")
            adv.setdefault("danger_level", 50)
    data["schema_version"] = 4
    return data


def _migrate_v4_to_v5(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add world memory fields (PR-F): live_traces to locations, memorials dict to world.

    Pre-PR-F saves have no live trace history or memorial records.
    Locations get an empty ``live_traces`` list; the world gets an empty
    ``memorials`` dict.  Existing ``memorial_ids`` and ``aliases`` on
    locations are left untouched (they were already empty lists from v3).
    """
    world_data = data.setdefault("world", {})
    for loc_data in world_data.get("grid", []):
        loc_data.setdefault("live_traces", [])
    world_data.setdefault("memorials", {})
    data["schema_version"] = 5
    return data


#: Mapping from region_type to biome for terrain generation during migration.
_REGION_TYPE_TO_BIOME: Dict[str, str] = {
    "city": "plains",
    "village": "plains",
    "forest": "forest",
    "dungeon": "hills",
    "mountain": "mountain",
    "plains": "plains",
    "sea": "ocean",
}

#: Default importance per site type.
_SITE_IMPORTANCE: Dict[str, int] = {
    "city": 80,
    "village": 40,
    "forest": 20,
    "dungeon": 60,
    "mountain": 30,
    "plains": 20,
    "sea": 10,
}


def _migrate_v5_to_v6(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add terrain_map, sites, and routes to the world (PR-G1).

    Pre-PR-G saves have no terrain layer.  This migration generates
    terrain cells from existing location region_types, creates Site
    records linking locations to terrain coordinates, and auto-generates
    route edges between adjacent sites.
    """
    world_data = data.setdefault("world", {})
    grid = world_data.get("grid", [])
    width = world_data.get("width", 5)
    height = world_data.get("height", 5)

    # Build terrain cells for every grid coordinate
    terrain_cells = []
    for y in range(height):
        for x in range(width):
            terrain_cells.append({
                "x": x, "y": y,
                "biome": "plains",
                "elevation": 128,
                "moisture": 128,
                "temperature": 128,
            })

    # Map (x, y) -> terrain cell dict for biome overwriting
    cell_lookup: Dict[tuple, Dict[str, Any]] = {}
    for tc in terrain_cells:
        cell_lookup[(tc["x"], tc["y"])] = tc

    # Build sites from existing grid locations and set biomes
    sites = []
    site_coords: Dict[tuple, str] = {}
    for loc_data in grid:
        loc_id = loc_data.get("id", "")
        region_type = loc_data.get("region_type", "city")
        x = loc_data.get("x", 0)
        y = loc_data.get("y", 0)

        biome = _REGION_TYPE_TO_BIOME.get(region_type, "plains")
        importance = _SITE_IMPORTANCE.get(region_type, 50)

        tc = cell_lookup.get((x, y))
        if tc is not None:
            tc["biome"] = biome

        sites.append({
            "location_id": loc_id,
            "x": x,
            "y": y,
            "site_type": region_type,
            "importance": importance,
        })
        site_coords[(x, y)] = loc_id

    # Auto-generate routes between adjacent sites
    routes = []
    seen_pairs: set = set()
    route_counter = 0
    for (x, y), loc_id in site_coords.items():
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = x + dx, y + dy
            neighbor_id = site_coords.get((nx, ny))
            if neighbor_id is None:
                continue
            pair = tuple(sorted([loc_id, neighbor_id]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            route_counter += 1

            from_biome = cell_lookup.get((x, y), {}).get("biome", "plains")
            to_biome = cell_lookup.get((nx, ny), {}).get("biome", "plains")
            if "mountain" in (from_biome, to_biome):
                route_type = "mountain_pass"
            elif "ocean" in (from_biome, to_biome):
                route_type = "sea_lane"
            elif "swamp" in (from_biome, to_biome):
                route_type = "trail"
            else:
                route_type = "road"

            routes.append({
                "route_id": f"route_{route_counter:03d}",
                "from_site_id": loc_id,
                "to_site_id": neighbor_id,
                "route_type": route_type,
                "distance": 1,
                "blocked": False,
            })

    world_data["terrain_map"] = {
        "width": width,
        "height": height,
        "cells": terrain_cells,
    }
    world_data["sites"] = sites
    world_data["routes"] = routes
    data["schema_version"] = 6
    return data

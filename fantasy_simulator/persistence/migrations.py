"""
migrations.py - Schema migration for save data.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Dict

from ..content.setting_bundle import bundle_from_dict_validated
from ..content.world_data import (
    DEFAULT_LOCATIONS,
    NAME_TO_LOCATION_ID,
    fallback_location_id,
    get_location_state_defaults,
)
from ..terrain import (
    assemble_atlas_layout_inputs,
    build_default_atlas_layout,
    build_terrain_payload_from_locations,
)

CURRENT_VERSION = 8


def _embedded_setting_bundle(data: Dict[str, Any]):
    world_data = data.get("world", {})
    bundle_data = world_data.get("setting_bundle")
    if bundle_data is None:
        return None
    return bundle_from_dict_validated(bundle_data, source="embedded world.setting_bundle during migration")


def _location_name_to_id(data: Dict[str, Any]) -> Dict[str, str]:
    bundle = _embedded_setting_bundle(data)
    if bundle is None:
        return dict(NAME_TO_LOCATION_ID)
    return {
        seed.name: seed.location_id
        for seed in bundle.world_definition.site_seeds
    }


def _default_locations_for_data(data: Dict[str, Any]) -> list[tuple[str, str, str, str, int, int]]:
    bundle = _embedded_setting_bundle(data)
    if bundle is None:
        return list(DEFAULT_LOCATIONS)
    return [
        seed.as_world_data_entry()
        for seed in bundle.world_definition.site_seeds
    ]


def _site_tags_by_location_id(data: Dict[str, Any]) -> Dict[str, list[str]]:
    bundle = _embedded_setting_bundle(data)
    if bundle is None:
        return {}
    return {
        seed.location_id: list(seed.tags)
        for seed in bundle.world_definition.site_seeds
    }


def _resolve_location_id(data: Dict[str, Any], name: str) -> str:
    return _location_name_to_id(data).get(name, fallback_location_id(name))


def _calendar_key_for_data(data: Dict[str, Any]) -> str:
    bundle = _embedded_setting_bundle(data)
    if bundle is not None:
        return bundle.world_definition.calendar.calendar_key
    return ""


def _record_from_legacy_history_item(
    item: Dict[str, Any],
    *,
    index: int,
    calendar_key: str,
) -> Dict[str, Any]:
    affected = list(item.get("affected_characters", []))
    return {
        "record_id": f"legacy_history_{index:06d}",
        "kind": item.get("event_type", "generic"),
        "year": item.get("year", 0),
        "month": 1,
        "day": 1,
        "absolute_day": 0,
        "location_id": None,
        "primary_actor_id": affected[0] if affected else None,
        "secondary_actor_ids": affected[1:],
        "description": item.get("description", ""),
        "severity": 1,
        "visibility": "public",
        "calendar_key": calendar_key,
        "tags": [],
        "impacts": [],
        "legacy_event_result": dict(item),
        "legacy_event_log_entry": None,
    }


def _record_from_legacy_event_log_entry(
    entry: str,
    *,
    index: int,
    year: int,
    calendar_key: str,
) -> Dict[str, Any]:
    return {
        "record_id": f"legacy_event_log_{index:06d}",
        "kind": "legacy_event_log",
        "year": year,
        "month": 1,
        "day": 1,
        "absolute_day": 0,
        "location_id": None,
        "primary_actor_id": None,
        "secondary_actor_ids": [],
        "description": entry,
        "severity": 1,
        "visibility": "public",
        "calendar_key": calendar_key,
        "tags": ["legacy_event_log"],
        "impacts": [],
        "legacy_event_result": {
            "description": entry,
            "affected_characters": [],
            "stat_changes": {},
            "event_type": "legacy_event_log",
            "year": year,
            "metadata": {"legacy_event_log_entry": True},
        },
        "legacy_event_log_entry": entry,
    }


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
        7: _migrate_v6_to_v7,
        8: _migrate_v7_to_v8,
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
        char_data["location_id"] = _resolve_location_id(data, old_name)

    world_data = data.get("world", {})
    for loc_data in world_data.get("grid", []):
        if "id" in loc_data:
            continue
        name = loc_data.get("canonical_name") or loc_data.get("name", "")
        loc_data["id"] = _resolve_location_id(data, name)

    for bucket in ("active_adventures", "completed_adventures"):
        for adventure in world_data.get(bucket, []):
            if "origin" in adventure:
                origin = adventure["origin"]
                adventure["origin"] = _resolve_location_id(data, origin)
            if "destination" in adventure:
                destination = adventure["destination"]
                adventure["destination"] = _resolve_location_id(data, destination)

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
    site_tags_by_location_id = _site_tags_by_location_id(data)
    existing_ids = {
        loc_data.get("id") or _location_name_to_id(data).get(
            loc_data.get("canonical_name") or loc_data.get("name", ""), ""
        )
        for loc_data in grid
    }
    for loc_id, name, desc, region_type, x, y in _default_locations_for_data(data):
        if loc_id in existing_ids:
            continue
        if not (0 <= x < width and 0 <= y < height):
            continue
        defaults = get_location_state_defaults(
            loc_id,
            region_type,
            site_tags=site_tags_by_location_id.get(loc_id),
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
            loc_id = _resolve_location_id(data, name)
            loc_data["id"] = loc_id
        canonical_name = loc_data.get("canonical_name") or loc_data.get("name", "")
        loc_data["canonical_name"] = canonical_name
        loc_data.setdefault("name", canonical_name)

        region_type = loc_data.get("region_type", "city")
        defaults = get_location_state_defaults(
            loc_id,
            region_type,
            site_tags=site_tags_by_location_id.get(loc_id),
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


def _migrate_v6_to_v7(data: Dict[str, Any]) -> Dict[str, Any]:
    """Add atlas_layout and per-site atlas coordinates (PR-G2 items 7-8).

    Computes atlas_x / atlas_y for each site from the grid coordinates
    and creates a minimal atlas_layout structure.  Pre-v7 saves have
    no atlas geometry — this migration generates it deterministically.
    """
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


def _migrate_v7_to_v8(data: Dict[str, Any]) -> Dict[str, Any]:
    """Canonicalize legacy event adapters into ``world.event_records``."""
    world_data = data.setdefault("world", {})
    event_records = list(world_data.setdefault("event_records", []))
    history = list(data.get("history", []))
    event_log = list(world_data.get("event_log", []))
    calendar_key = _calendar_key_for_data(data)

    canonical_records = list(event_records)
    existing_history_payload_counts: Dict[str, int] = {}
    existing_legacy_log_counts: Dict[str, int] = {}
    for record in canonical_records:
        record_id = str(record.get("record_id", ""))
        if record_id.startswith("legacy_history_"):
            payload = record.get("legacy_event_result")
            if payload is not None:
                payload_key = json.dumps(payload, sort_keys=True)
                existing_history_payload_counts[payload_key] = existing_history_payload_counts.get(payload_key, 0) + 1
        elif record_id.startswith("legacy_event_log_"):
            entry = record.get("legacy_event_log_entry")
            if entry is not None:
                existing_legacy_log_counts[entry] = existing_legacy_log_counts.get(entry, 0) + 1
    history_index = sum(
        1 for record in canonical_records if str(record.get("record_id", "")).startswith("legacy_history_")
    )
    event_log_index = sum(
        1 for record in canonical_records if str(record.get("record_id", "")).startswith("legacy_event_log_")
    )

    for item in history:
        payload_key = json.dumps(item, sort_keys=True)
        if existing_history_payload_counts.get(payload_key, 0) > 0:
            existing_history_payload_counts[payload_key] -= 1
            continue
        history_index += 1
        canonical_records.append(
            _record_from_legacy_history_item(item, index=history_index, calendar_key=calendar_key)
        )

    year = int(world_data.get("year", 0))
    for entry in event_log:
        if existing_legacy_log_counts.get(entry, 0) > 0:
            existing_legacy_log_counts[entry] -= 1
            continue
        event_log_index += 1
        canonical_records.append(
            _record_from_legacy_event_log_entry(entry, index=event_log_index, year=year, calendar_key=calendar_key)
        )

    if canonical_records:
        world_data["event_records"] = canonical_records

    data["schema_version"] = 8
    return data

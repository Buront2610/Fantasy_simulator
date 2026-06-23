"""Shared place-profile semantics for map renderers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Tuple


@dataclass(frozen=True)
class PlaceVisualProfile:
    """Renderer-agnostic description of what kind of place a map cell is."""

    archetype: str = "generic"
    world_marker_primary: str = "o"
    world_marker_suffix: str = ""
    short_label_key: str = "map_profile_generic_short"
    summary_key: str = "map_profile_generic_summary"
    terrain_tags: Tuple[str, ...] = ()
    civic_tags: Tuple[str, ...] = ()
    atmosphere_tags: Tuple[str, ...] = ()
    landmark_tags: Tuple[str, ...] = ()
    local_layout_tags: Tuple[str, ...] = ()
    local_scene_keys: Tuple[str, ...] = ()


def build_place_visual_profile(cell: Any) -> PlaceVisualProfile:
    """Build a shared visual profile from renderer-facing cell state."""
    region_type = str(getattr(cell, "region_type", "") or "")
    terrain_tags = _terrain_tags(cell)
    civic_tags = _civic_tags(cell)
    atmosphere_tags = _atmosphere_tags(cell)
    landmark_tags = _landmark_tags(cell)
    if region_type == "city":
        return _city_profile(cell, terrain_tags, civic_tags, atmosphere_tags, landmark_tags)
    if region_type == "village":
        return _village_profile(cell, terrain_tags, civic_tags, atmosphere_tags, landmark_tags)
    if region_type == "dungeon":
        return _dungeon_profile(cell, terrain_tags, atmosphere_tags, landmark_tags)
    return _wild_profile(cell, terrain_tags, atmosphere_tags, landmark_tags)


def _terrain_tags(cell: Any) -> Tuple[str, ...]:
    tags: list[str] = []
    biome = str(getattr(cell, "terrain_biome", "") or "")
    if biome:
        tags.append(biome)
    if int(getattr(cell, "terrain_moisture", 128) or 128) >= 170:
        tags.append("wet")
    if int(getattr(cell, "terrain_elevation", 128) or 128) >= 170:
        tags.append("highland")
    if int(getattr(cell, "terrain_temperature", 128) or 128) < 86:
        tags.append("cold")
    return tuple(dict.fromkeys(tags))


def _civic_tags(cell: Any) -> Tuple[str, ...]:
    tags = [str(tag) for tag in getattr(cell, "local_feature_tags", ()) if str(tag)]
    if getattr(cell, "traffic_band", "") == "high":
        tags.append("busy_roads")
    if int(getattr(cell, "prosperity", 50) or 50) >= 70:
        tags.append("prosperous")
    return tuple(dict.fromkeys(tags))


def _atmosphere_tags(cell: Any) -> Tuple[str, ...]:
    tags: list[str] = []
    if getattr(cell, "danger_band", "") == "high":
        tags.append("dangerous")
    if getattr(cell, "rumor_heat_band", "") == "high":
        tags.append("rumor_heavy")
    if int(getattr(cell, "mood", 50) or 50) < 35:
        tags.append("grieving")
    if getattr(cell, "controlling_faction_id", ""):
        tags.append("controlled")
    return tuple(tags)


def _landmark_tags(cell: Any) -> Tuple[str, ...]:
    tags: list[str] = []
    if getattr(cell, "has_memorial", False):
        tags.append("memorial")
    if getattr(cell, "has_alias", False):
        tags.append("alias")
    if getattr(cell, "recent_death_site", False):
        tags.append("recent_death")
    if int(getattr(cell, "recent_world_change_count", 0) or 0) > 0:
        tags.append("world_change")
    return tuple(tags)


def _city_profile(
    cell: Any,
    terrain_tags: Tuple[str, ...],
    civic_tags: Tuple[str, ...],
    atmosphere_tags: Tuple[str, ...],
    landmark_tags: Tuple[str, ...],
) -> PlaceVisualProfile:
    if getattr(cell, "controlling_faction_id", "") and getattr(cell, "danger_band", "") == "high":
        return PlaceVisualProfile(
            archetype="occupied_fortress_city",
            world_marker_primary="C",
            world_marker_suffix="!",
            short_label_key="map_profile_occupied_city_short",
            summary_key="map_profile_occupied_city_summary",
            terrain_tags=terrain_tags,
            civic_tags=("walls", "barracks", "checkpoint", *civic_tags),
            atmosphere_tags=("tense", *atmosphere_tags),
            landmark_tags=landmark_tags,
            local_layout_tags=("wall_ring", "gate", "barracks", "checkpoint"),
            local_scene_keys=("local_map_scene_city_citadel", "local_map_scene_occupied_city"),
        )
    if int(getattr(cell, "mood", 50) or 50) < 35 or getattr(cell, "has_memorial", False):
        return PlaceVisualProfile(
            archetype="mourning_city",
            world_marker_primary="C",
            world_marker_suffix="m",
            short_label_key="map_profile_mourning_city_short",
            summary_key="map_profile_mourning_city_summary",
            terrain_tags=terrain_tags,
            civic_tags=("shrine", "quiet_homes", *civic_tags),
            atmosphere_tags=("grieving", *atmosphere_tags),
            landmark_tags=("memorial", *landmark_tags),
            local_layout_tags=("memorial_square", "closed_market", "temple_lane"),
            local_scene_keys=("local_map_scene_mourning_city",),
        )
    if "river" in terrain_tags or "wet" in terrain_tags:
        return PlaceVisualProfile(
            archetype="riverport_city",
            world_marker_primary="C",
            world_marker_suffix="~",
            short_label_key="map_profile_riverport_city_short",
            summary_key="map_profile_riverport_city_summary",
            terrain_tags=terrain_tags,
            civic_tags=("dock", "warehouse", "market", *civic_tags),
            atmosphere_tags=atmosphere_tags,
            landmark_tags=landmark_tags,
            local_layout_tags=("quay", "warehouses", "market_lane"),
            local_scene_keys=("local_map_scene_city_riverport",),
        )
    if getattr(cell, "traffic_band", "") == "high" and int(getattr(cell, "prosperity", 50) or 50) >= 70:
        return PlaceVisualProfile(
            archetype="market_city",
            world_marker_primary="C",
            world_marker_suffix="$",
            short_label_key="map_profile_market_city_short",
            summary_key="map_profile_market_city_summary",
            terrain_tags=terrain_tags,
            civic_tags=("market", "guild", "inn", *civic_tags),
            atmosphere_tags=("busy", *atmosphere_tags),
            landmark_tags=landmark_tags,
            local_layout_tags=("market_square", "guildhall", "wide_roads"),
            local_scene_keys=("local_map_scene_city_open_market",),
        )
    return PlaceVisualProfile(
        archetype="walled_city",
        world_marker_primary="C",
        short_label_key="map_profile_walled_city_short",
        summary_key="map_profile_walled_city_summary",
        terrain_tags=terrain_tags,
        civic_tags=("homes", "market", "shrine", "gate", *civic_tags),
        atmosphere_tags=atmosphere_tags,
        landmark_tags=landmark_tags,
        local_layout_tags=("wall_ring", "main_road", "plaza"),
        local_scene_keys=("local_map_scene_city_citadel",),
    )


def _village_profile(
    cell: Any,
    terrain_tags: Tuple[str, ...],
    civic_tags: Tuple[str, ...],
    atmosphere_tags: Tuple[str, ...],
    landmark_tags: Tuple[str, ...],
) -> PlaceVisualProfile:
    if int(getattr(cell, "mood", 50) or 50) < 35 or getattr(cell, "has_memorial", False):
        return PlaceVisualProfile(
            archetype="mourning_village",
            world_marker_primary="v",
            world_marker_suffix="m",
            short_label_key="map_profile_mourning_village_short",
            summary_key="map_profile_mourning_village_summary",
            terrain_tags=terrain_tags,
            civic_tags=("shrine", "closed_homes", *civic_tags),
            atmosphere_tags=("grieving", *atmosphere_tags),
            landmark_tags=("memorial", *landmark_tags),
            local_layout_tags=("memorial_lane", "shrine", "quiet_fields"),
            local_scene_keys=("local_map_scene_mourning_village",),
        )
    if "river" in terrain_tags or "wet" in terrain_tags:
        return PlaceVisualProfile(
            archetype="riverside_village",
            world_marker_primary="v",
            world_marker_suffix="~",
            short_label_key="map_profile_riverside_village_short",
            summary_key="map_profile_riverside_village_summary",
            terrain_tags=terrain_tags,
            civic_tags=("bridge", "mill", "fields", *civic_tags),
            atmosphere_tags=atmosphere_tags,
            landmark_tags=landmark_tags,
            local_layout_tags=("watermill", "bridge", "fields"),
            local_scene_keys=("local_map_scene_village_riverside",),
        )
    if "forest" in terrain_tags:
        return PlaceVisualProfile(
            archetype="woodland_village",
            world_marker_primary="v",
            world_marker_suffix="T",
            short_label_key="map_profile_woodland_village_short",
            summary_key="map_profile_woodland_village_summary",
            terrain_tags=terrain_tags,
            civic_tags=("shrine", "wood_homes", *civic_tags),
            atmosphere_tags=atmosphere_tags,
            landmark_tags=landmark_tags,
            local_layout_tags=("forest_trails", "shrine", "cottages"),
            local_scene_keys=("local_map_scene_village_woodland",),
        )
    if "highland" in terrain_tags:
        return PlaceVisualProfile(
            archetype="highland_hamlet",
            world_marker_primary="v",
            world_marker_suffix="^",
            short_label_key="map_profile_highland_hamlet_short",
            summary_key="map_profile_highland_hamlet_summary",
            terrain_tags=terrain_tags,
            civic_tags=("watch_camp", "stone_homes", *civic_tags),
            atmosphere_tags=atmosphere_tags,
            landmark_tags=landmark_tags,
            local_layout_tags=("switchback", "watch_camp", "terraces"),
            local_scene_keys=("local_map_scene_village_highland",),
        )
    return PlaceVisualProfile(
        archetype="field_village",
        world_marker_primary="v",
        world_marker_suffix='"',
        short_label_key="map_profile_field_village_short",
        summary_key="map_profile_field_village_summary",
        terrain_tags=terrain_tags,
        civic_tags=("fields", "barn", "homes", *civic_tags),
        atmosphere_tags=atmosphere_tags,
        landmark_tags=landmark_tags,
        local_layout_tags=("fields", "barns", "country_lane"),
        local_scene_keys=("local_map_scene_village_field",),
    )


def _dungeon_profile(
    cell: Any,
    terrain_tags: Tuple[str, ...],
    atmosphere_tags: Tuple[str, ...],
    landmark_tags: Tuple[str, ...],
) -> PlaceVisualProfile:
    if "river" in terrain_tags or "wet" in terrain_tags:
        return PlaceVisualProfile(
            archetype="flooded_dungeon",
            world_marker_primary="D",
            world_marker_suffix="~",
            short_label_key="map_profile_flooded_dungeon_short",
            summary_key="map_profile_flooded_dungeon_summary",
            terrain_tags=terrain_tags,
            atmosphere_tags=atmosphere_tags,
            landmark_tags=landmark_tags,
            local_layout_tags=("pools", "rubble", "sunk_rooms"),
            local_scene_keys=("local_map_scene_dungeon_flooded",),
        )
    if getattr(cell, "danger_band", "") == "high":
        return PlaceVisualProfile(
            archetype="danger_dungeon",
            world_marker_primary="D",
            world_marker_suffix="!",
            short_label_key="map_profile_danger_dungeon_short",
            summary_key="map_profile_danger_dungeon_summary",
            terrain_tags=terrain_tags,
            atmosphere_tags=("threatened", *atmosphere_tags),
            landmark_tags=landmark_tags,
            local_layout_tags=("threats", "deep_rooms", "cache"),
            local_scene_keys=("local_map_scene_dungeon_vault",),
        )
    if "highland" in terrain_tags:
        return PlaceVisualProfile(
            archetype="cavern_dungeon",
            world_marker_primary="D",
            world_marker_suffix="^",
            short_label_key="map_profile_cavern_dungeon_short",
            summary_key="map_profile_cavern_dungeon_summary",
            terrain_tags=terrain_tags,
            atmosphere_tags=atmosphere_tags,
            landmark_tags=landmark_tags,
            local_layout_tags=("rough_chambers", "rubble", "drop"),
            local_scene_keys=("local_map_scene_dungeon_cavern",),
        )
    return PlaceVisualProfile(
        archetype="buried_vault",
        world_marker_primary="D",
        short_label_key="map_profile_buried_vault_short",
        summary_key="map_profile_buried_vault_summary",
        terrain_tags=terrain_tags,
        atmosphere_tags=atmosphere_tags,
        landmark_tags=landmark_tags,
        local_layout_tags=("altar", "cache", "rooms"),
        local_scene_keys=("local_map_scene_dungeon_vault",),
    )


def _wild_profile(
    cell: Any,
    terrain_tags: Tuple[str, ...],
    atmosphere_tags: Tuple[str, ...],
    landmark_tags: Tuple[str, ...],
) -> PlaceVisualProfile:
    region_type = str(getattr(cell, "region_type", "") or "")
    if region_type == "forest":
        return PlaceVisualProfile(
            archetype="forest_paths",
            world_marker_primary="T",
            short_label_key="map_profile_forest_paths_short",
            summary_key="map_profile_forest_paths_summary",
            terrain_tags=terrain_tags,
            atmosphere_tags=atmosphere_tags,
            landmark_tags=landmark_tags,
            local_layout_tags=("trails", "tree_cover", "stones"),
            local_scene_keys=("local_map_scene_wild",),
        )
    if region_type == "mountain":
        return PlaceVisualProfile(
            archetype="mountain_pass",
            world_marker_primary="^",
            short_label_key="map_profile_mountain_pass_short",
            summary_key="map_profile_mountain_pass_summary",
            terrain_tags=terrain_tags,
            atmosphere_tags=atmosphere_tags,
            landmark_tags=landmark_tags,
            local_layout_tags=("pass", "lookout", "rocks"),
            local_scene_keys=("local_map_scene_wild",),
        )
    return PlaceVisualProfile(
        archetype="open_wilds",
        world_marker_primary="o",
        short_label_key="map_profile_open_wilds_short",
        summary_key="map_profile_open_wilds_summary",
        terrain_tags=terrain_tags,
        atmosphere_tags=atmosphere_tags,
        landmark_tags=landmark_tags,
        local_layout_tags=("trail", "brush"),
        local_scene_keys=("local_map_scene_wild",),
    )

"""Location-structure bookkeeping helpers for ``World``."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple


def register_location(
    *,
    grid: Dict[Tuple[int, int], Any],
    location_name_index: Dict[str, Any],
    location_id_index: Dict[str, Any],
    location: Any,
) -> None:
    """Register one location into coordinate, name, and ID indexes."""
    existing_at_coord = grid.get((location.x, location.y))
    existing_by_id = location_id_index.get(location.id)
    existing_by_name = location_name_index.get(location.canonical_name)
    if (
        existing_by_name is not None
        and existing_by_name is not location
        and existing_by_name is not existing_at_coord
        and existing_by_name is not existing_by_id
    ):
        raise ValueError(f"duplicate location canonical name: {location.canonical_name}")

    if existing_at_coord is not None and existing_at_coord is not location:
        location_name_index.pop(existing_at_coord.canonical_name, None)
        location_id_index.pop(existing_at_coord.id, None)

    if existing_by_id is not None and existing_by_id is not location:
        grid.pop((existing_by_id.x, existing_by_id.y), None)
        location_name_index.pop(existing_by_id.canonical_name, None)

    grid[(location.x, location.y)] = location
    location_name_index[location.canonical_name] = location
    location_id_index[location.id] = location


def clear_world_structure(world: Any) -> None:
    """Reset world structures derived from the active location grid."""
    world.grid.clear()
    world._location_id_index.clear()
    world._location_name_index.clear()
    world.terrain_map = None
    world.sites = []
    world.routes = []
    world._routes_dirty = True
    world._route_graph_explicit = False
    world._site_index = {}
    world._routes_by_site = {}
    world.atlas_layout = None


def copy_location_runtime_state(source: Any, target: Any) -> None:
    """Preserve mutable location state across structural rebuilds."""
    structural_aliases = list(target.aliases)
    structural_endonym = target.generated_endonym
    target.prosperity = source.prosperity
    target.safety = source.safety
    target.mood = source.mood
    target.danger = source.danger
    target.traffic = source.traffic
    target.rumor_heat = source.rumor_heat
    target.road_condition = source.road_condition
    target.visited = source.visited
    target.controlling_faction_id = source.controlling_faction_id
    target.recent_event_ids = list(source.recent_event_ids)
    target.aliases = list(dict.fromkeys(structural_aliases + list(source.aliases)))
    target.generated_endonym = structural_endonym
    target.memorial_ids = list(source.memorial_ids)
    target.live_traces = deepcopy(source.live_traces)


def preserved_locations_by_normalized_id(
    locations: Iterable[Any],
    *,
    normalize_location_id: Callable[[Optional[str], str], Optional[str]],
) -> Dict[str, Any]:
    """Index previous locations by normalized ID for runtime-state preservation."""
    preserved_by_id: Dict[str, Any] = {}
    for location in locations:
        normalized_id = normalize_location_id(location.id, location.canonical_name)
        if normalized_id is not None and normalized_id not in preserved_by_id:
            preserved_by_id[normalized_id] = location
    return preserved_by_id


def default_location_entries(
    site_seeds: Iterable[Any],
    *,
    width: int,
    height: int,
) -> List[Tuple[str, str, str, str, int, int]]:
    """Return in-bounds site seeds in the legacy tuple format."""
    return [
        seed.as_world_data_entry()
        for seed in site_seeds
        if 0 <= seed.x < width and 0 <= seed.y < height
    ]


def serialized_grid_is_compatible_with_site_seeds(
    grid_data: Iterable[Mapping[str, Any]],
    *,
    site_seeds: Iterable[Any],
    normalize_location_id: Callable[[Optional[str], str], Optional[str]],
) -> bool:
    """Return whether serialized locations can be mapped onto active site seeds."""
    grid_items = list(grid_data)
    if not grid_items:
        return True
    bundle_location_ids = {seed.location_id for seed in site_seeds}
    for loc_data in grid_items:
        canonical_name = loc_data.get("canonical_name") or loc_data.get("name", "")
        normalized_id = normalize_location_id(loc_data.get("id"), canonical_name)
        if normalized_id not in bundle_location_ids:
            return False
    return True


def site_seed_tags(site_seeds: Iterable[Any], location_id: str) -> List[str]:
    """Return semantic tags for a location from site seeds."""
    for seed in site_seeds:
        if seed.location_id == location_id:
            return list(seed.tags)
    return []


def grid_matches_site_seeds(
    *,
    site_seeds: Iterable[Any],
    grid_locations: Iterable[Any],
    width: int,
    height: int,
) -> bool:
    """Return whether the current grid exactly mirrors in-bounds site seeds."""
    bundle_locations = sorted(
        (
            seed.location_id,
            seed.name,
            seed.description,
            seed.region_type,
            int(seed.x),
            int(seed.y),
        )
        for seed in site_seeds
        if 0 <= seed.x < width and 0 <= seed.y < height
    )
    current_locations = sorted(
        (
            location.id,
            location.canonical_name,
            location.description,
            location.region_type,
            int(location.x),
            int(location.y),
        )
        for location in grid_locations
    )
    return bundle_locations == current_locations

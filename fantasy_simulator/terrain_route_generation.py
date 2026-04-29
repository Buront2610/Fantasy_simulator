"""Route generation helpers for terrain topology construction."""

from __future__ import annotations

from typing import Callable, Dict, List, Tuple

from .terrain_atlas_generation import (
    ATLAS_CANVAS_H,
    ATLAS_CANVAS_W,
    ATLAS_MARGIN_X,
    ATLAS_MARGIN_Y,
    AtlasLayoutInputs,
    assemble_atlas_layout_inputs,
    build_default_atlas_layout_data,
    project_atlas_coords,
)


__all__ = [
    "ATLAS_CANVAS_H",
    "ATLAS_CANVAS_W",
    "ATLAS_MARGIN_X",
    "ATLAS_MARGIN_Y",
    "AtlasLayoutInputs",
    "assemble_atlas_layout_inputs",
    "build_default_atlas_layout_data",
    "project_atlas_coords",
    "provisional_route_specs_from_grid_adjacency",
]


def provisional_route_specs_from_grid_adjacency(
    site_coords: Dict[Tuple[int, int], str],
    *,
    biome_at: Callable[[int, int], str],
) -> List[Dict[str, object]]:
    """Return legacy bridge route specs derived from 4-directional adjacency."""
    route_specs: List[Dict[str, object]] = []
    seen_pairs: set[Tuple[str, str]] = set()
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

            from_biome = biome_at(x, y)
            to_biome = biome_at(nx, ny)
            if "mountain" in (from_biome, to_biome):
                route_type = "mountain_pass"
            elif "ocean" in (from_biome, to_biome):
                route_type = "sea_lane"
            elif "swamp" in (from_biome, to_biome):
                route_type = "trail"
            else:
                route_type = "road"

            route_specs.append({
                "route_id": f"route_{route_counter:03d}",
                "from_site_id": loc_id,
                "to_site_id": neighbor_id,
                "route_type": route_type,
            })
    return route_specs

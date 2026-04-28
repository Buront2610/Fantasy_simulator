"""Route and atlas generation helpers for terrain topology construction."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple


ATLAS_CANVAS_W = 72
ATLAS_CANVAS_H = 30
ATLAS_MARGIN_X = 6
ATLAS_MARGIN_Y = 3


@dataclass(slots=True)
class AtlasLayoutInputs:
    """Normalized atlas-layout inputs derived from world/site state."""

    site_coords: List[Tuple[int, int]]
    route_coords: List[Tuple[Tuple[int, int], Tuple[int, int]]]
    mountain_coords: List[Tuple[int, int]]


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


def project_atlas_coords(
    grid_x: int,
    grid_y: int,
    *,
    width: int,
    height: int,
) -> Tuple[int, int]:
    """Project a grid coordinate onto the persistent atlas canvas."""
    avail_w = ATLAS_CANVAS_W - 2 * ATLAS_MARGIN_X
    avail_h = ATLAS_CANVAS_H - 2 * ATLAS_MARGIN_Y
    step_x = avail_w / max(width - 1, 1)
    step_y = avail_h / max(height - 1, 1)
    return (
        int(ATLAS_MARGIN_X + grid_x * step_x),
        int(ATLAS_MARGIN_Y + grid_y * step_y),
    )


def _coast_noise(x: int, y: int) -> float:
    """Smooth deterministic noise used for continent silhouettes."""
    return (
        0.25 * math.sin(x * 0.15 + 1.0) * math.cos(y * 0.2 + 2.0)
        + 0.15 * math.sin(x * 0.35 + 3.0) * math.sin(y * 0.25 + 1.5)
        + 0.10 * math.cos(x * 0.5 + y * 0.4 + 0.7)
    )


def _cluster_atlas_sites(
    sites: List[Tuple[int, int]],
    max_clusters: int = 4,
) -> List[List[Tuple[int, int]]]:
    """Partition atlas sites into stable spatial clusters."""
    if len(sites) <= 3:
        return [sites] if sites else []

    xs = [p[0] for p in sites]
    ys = [p[1] for p in sites]
    spread = max(max(xs) - min(xs), max(ys) - min(ys))
    if spread < 20:
        return [sites]

    k = min(max_clusters, max(2, len(sites) // 5))
    sorted_sites = sorted(sites)
    step = max(1, len(sorted_sites) // k)
    centroids = [sorted_sites[i * step % len(sorted_sites)] for i in range(k)]
    centroids = list(dict.fromkeys(centroids))
    if len(centroids) < 2:
        return [sites]

    for _ in range(10):
        clusters: List[List[Tuple[int, int]]] = [[] for _ in range(len(centroids))]
        for pt in sites:
            best_i = 0
            best_d = float("inf")
            for ci, centroid in enumerate(centroids):
                dist = (pt[0] - centroid[0]) ** 2 + (pt[1] - centroid[1]) ** 2
                if dist < best_d:
                    best_d = dist
                    best_i = ci
            clusters[best_i].append(pt)

        new_centroids: List[Tuple[int, int]] = []
        for idx, cluster in enumerate(clusters):
            if cluster:
                new_centroids.append((
                    int(sum(p[0] for p in cluster) / len(cluster)),
                    int(sum(p[1] for p in cluster) / len(cluster)),
                ))
            else:
                new_centroids.append(centroids[idx])
        if new_centroids == centroids:
            break
        centroids = new_centroids

    return [cluster for cluster in clusters if cluster]


def _atlas_line_points(
    x0: int,
    y0: int,
    x1: int,
    y1: int,
) -> List[Tuple[int, int]]:
    """Return integer points along a straight line on the atlas canvas."""
    points: List[Tuple[int, int]] = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x1 > x0 else -1
    sy = 1 if y1 > y0 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return points


def _stamp_atlas_cells(
    target: set[Tuple[int, int]],
    x: int,
    y: int,
    *,
    radius_x: int,
    radius_y: int,
) -> None:
    """Add a rectangular stamp around a canvas coordinate."""
    for dy in range(-radius_y, radius_y + 1):
        for dx in range(-radius_x, radius_x + 1):
            nx = x + dx
            ny = y + dy
            if 0 <= nx < ATLAS_CANVAS_W and 0 <= ny < ATLAS_CANVAS_H:
                target.add((nx, ny))


def _read_field(item: Any, field_name: str, default: Any = None) -> Any:
    """Read a field from either a mapping or an object."""
    if isinstance(item, dict):
        return item.get(field_name, default)
    return getattr(item, field_name, default)


def assemble_atlas_layout_inputs(
    *,
    width: int,
    height: int,
    sites: List[Any],
    routes: List[Any],
    terrain_cells: List[Any],
) -> AtlasLayoutInputs:
    """Collect normalized atlas-layout inputs from world or save data."""
    site_coords: List[Tuple[int, int]] = []
    site_by_id: Dict[str, Tuple[int, int]] = {}

    for site in sites:
        atlas_x = _read_field(site, "atlas_x", -1)
        atlas_y = _read_field(site, "atlas_y", -1)
        if atlas_x < 0 or atlas_y < 0:
            atlas_x, atlas_y = project_atlas_coords(
                int(_read_field(site, "x", 0)),
                int(_read_field(site, "y", 0)),
                width=width,
                height=height,
            )
            if isinstance(site, dict):
                site["atlas_x"] = atlas_x
                site["atlas_y"] = atlas_y
            else:
                setattr(site, "atlas_x", atlas_x)
                setattr(site, "atlas_y", atlas_y)
        coord = (int(atlas_x), int(atlas_y))
        site_coords.append(coord)
        location_id = _read_field(site, "location_id")
        if location_id:
            site_by_id[str(location_id)] = coord

    route_coords: List[Tuple[Tuple[int, int], Tuple[int, int]]] = []
    for route in routes:
        from_site = site_by_id.get(str(_read_field(route, "from_site_id", "")))
        to_site = site_by_id.get(str(_read_field(route, "to_site_id", "")))
        if from_site is None or to_site is None:
            continue
        route_coords.append((from_site, to_site))

    mountain_coords: List[Tuple[int, int]] = []
    for cell in terrain_cells:
        if _read_field(cell, "biome", "") != "mountain":
            continue
        mountain_coords.append(project_atlas_coords(
            int(_read_field(cell, "x", 0)),
            int(_read_field(cell, "y", 0)),
            width=width,
            height=height,
        ))

    return AtlasLayoutInputs(
        site_coords=site_coords,
        route_coords=route_coords,
        mountain_coords=mountain_coords,
    )


def _build_cluster_land(
    cluster: List[Tuple[int, int]],
    route_coords: List[Tuple[Tuple[int, int], Tuple[int, int]]],
) -> set[Tuple[int, int]]:
    """Create one continent-sized land mask for a site cluster."""
    land: set[Tuple[int, int]] = set()
    if not cluster:
        return land

    cx = sum(p[0] for p in cluster) / len(cluster)
    cy = sum(p[1] for p in cluster) / len(cluster)
    span_x = (max(p[0] for p in cluster) - min(p[0] for p in cluster)) / 2
    span_y = (max(p[1] for p in cluster) - min(p[1] for p in cluster)) / 2
    rx = max(6.0, span_x + 4.0)
    ry = max(4.0, span_y + 3.0)
    seed_off = int(cx * 7 + cy * 13)

    for py in range(ATLAS_CANVAS_H):
        for px in range(ATLAS_CANVAS_W):
            dx = (px - cx) / max(rx, 1.0)
            dy = (py - cy) / max(ry, 1.0)
            dist = math.sqrt(dx * dx + dy * dy)
            angle = math.atan2(dy, dx)
            angular_noise = (
                0.15 * math.sin(angle * 3 + 1.0 + seed_off)
                + 0.10 * math.sin(angle * 7 + 2.0 + seed_off)
                + 0.06 * math.sin(angle * 13 + 3.0 + seed_off)
            )
            shoreline_noise = _coast_noise(px + seed_off, py + seed_off)
            if dist < 0.85 + angular_noise + shoreline_noise:
                land.add((px, py))

    cluster_sites = set(cluster)
    for x, y in cluster:
        _stamp_atlas_cells(land, x, y, radius_x=4, radius_y=2)

    for start, end in route_coords:
        if start not in cluster_sites or end not in cluster_sites:
            continue
        for px, py in _atlas_line_points(start[0], start[1], end[0], end[1]):
            _stamp_atlas_cells(land, px, py, radius_x=1, radius_y=1)

    return land


def _connected_components(cells: set[Tuple[int, int]]) -> List[set[Tuple[int, int]]]:
    """Return 4-directional connected components for a cell set."""
    remaining = set(cells)
    components: List[set[Tuple[int, int]]] = []
    while remaining:
        start = remaining.pop()
        component = {start}
        queue = [start]
        while queue:
            x, y = queue.pop()
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if (nx, ny) in remaining:
                    remaining.remove((nx, ny))
                    component.add((nx, ny))
                    queue.append((nx, ny))
        components.append(component)
    return components


def build_default_atlas_layout_data(
    inputs: Optional[AtlasLayoutInputs] = None,
    *,
    site_coords: Optional[List[Tuple[int, int]]] = None,
    route_coords: Optional[List[Tuple[Tuple[int, int], Tuple[int, int]]]] = None,
    mountain_coords: Optional[List[Tuple[int, int]]] = None,
) -> Dict[str, Any]:
    """Create serialized atlas-layout fields for the current world."""
    normalized = inputs or AtlasLayoutInputs(
        site_coords=site_coords or [],
        route_coords=route_coords or [],
        mountain_coords=mountain_coords or [],
    )

    continent_regions: List[set[Tuple[int, int]]] = []
    for cluster in _cluster_atlas_sites(normalized.site_coords):
        cluster_land = _build_cluster_land(cluster, normalized.route_coords)
        if cluster_land:
            continent_regions.append(cluster_land)

    land: set[Tuple[int, int]] = set().union(*continent_regions) if continent_regions else set()
    mountains: set[Tuple[int, int]] = set()
    for x, y in normalized.mountain_coords:
        if x < 0 or y < 0:
            continue
        _stamp_atlas_cells(land, x, y, radius_x=3, radius_y=2)
        _stamp_atlas_cells(mountains, x, y, radius_x=1, radius_y=0)

    continent_components = _connected_components(land)
    sea_cells = {
        (x, y)
        for y in range(ATLAS_CANVAS_H)
        for x in range(ATLAS_CANVAS_W)
        if (x, y) not in land
    }
    sea_components = _connected_components(sea_cells)
    mountain_components = _connected_components(mountains)

    return {
        "canvas_w": ATLAS_CANVAS_W,
        "canvas_h": ATLAS_CANVAS_H,
        "continents": [
            {
                "name": "Main Continent" if idx == 0 else f"Continent {idx + 1}",
                "cells": sorted(component),
            }
            for idx, component in enumerate(
                sorted(continent_components, key=lambda component: (-len(component), sorted(component)[0]))
            )
        ],
        "seas": [
            {
                "name": "Great Ocean" if idx == 0 else f"Sea {idx + 1}",
                "cells": sorted(component),
            }
            for idx, component in enumerate(
                sorted(sea_components, key=lambda component: (-len(component), sorted(component)[0]))
            )
        ],
        "mountain_ranges": [
            {
                "name": "World Spine" if idx == 0 else f"Range {idx + 1}",
                "cells": sorted(component),
            }
            for idx, component in enumerate(
                sorted(mountain_components, key=lambda component: (-len(component), sorted(component)[0]))
            )
        ],
    }

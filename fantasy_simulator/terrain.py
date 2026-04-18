"""
terrain.py - Terrain, Site, and RouteEdge data models for PR-G1.

This module introduces the terrain/site separation required by PR-G.
Terrain cells represent the physical landscape (elevation, biome),
while Sites represent named locations (cities, dungeons) placed on
top of the terrain layer.  RouteEdges describe navigable connections
between sites.

The existing ``LocationState`` remains the authoritative game-state
holder for each site.  ``Site`` is the *placement* record that ties
a LocationState to a terrain coordinate, and ``TerrainCell`` is the
pure landscape description for that coordinate.
"""

from __future__ import annotations

import math
from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple


def _bool_payload(payload: Any, *, field_name: str) -> bool:
    if not isinstance(payload, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return payload


# ------------------------------------------------------------------
# Terrain types and biome definitions
# ------------------------------------------------------------------

#: Canonical terrain biome identifiers.
BIOME_TYPES: List[str] = [
    "ocean",
    "coast",
    "plains",
    "forest",
    "hills",
    "mountain",
    "swamp",
    "desert",
    "tundra",
    "river",
]

#: ASCII glyphs for terrain biomes (colour-independent).
BIOME_GLYPHS: Dict[str, str] = {
    "ocean": "~",
    "coast": ".",
    "plains": ",",
    "forest": "T",
    "hills": "n",
    "mountain": "^",
    "swamp": "%",
    "desert": ":",
    "tundra": "*",
    "river": "=",
}

#: Default movement cost multiplier per biome.
BIOME_MOVE_COST: Dict[str, float] = {
    "ocean": 999.0,
    "coast": 1.5,
    "plains": 1.0,
    "forest": 1.4,
    "hills": 1.6,
    "mountain": 2.5,
    "swamp": 2.0,
    "desert": 1.8,
    "tundra": 2.0,
    "river": 1.2,
}


# ------------------------------------------------------------------
# TerrainCell
# ------------------------------------------------------------------

@dataclass(slots=True)
class TerrainCell:
    """A single cell in the terrain grid.

    Terrain cells describe the physical landscape at a coordinate.
    They do *not* hold game state (prosperity, mood, etc.) — that
    stays in ``LocationState`` via the ``Site`` bridge.

    Attributes:
        x: Horizontal grid coordinate.
        y: Vertical grid coordinate.
        biome: One of ``BIOME_TYPES``.
        elevation: Height value 0-255 (sea level ~100).
        moisture: Moisture value 0-255.
        temperature: Temperature value 0-255.
    """

    x: int
    y: int
    biome: str = "plains"
    elevation: int = 128
    moisture: int = 128
    temperature: int = 128

    @property
    def glyph(self) -> str:
        """ASCII glyph for this cell's biome."""
        return BIOME_GLYPHS.get(self.biome, "?")

    @property
    def move_cost(self) -> float:
        """Movement cost multiplier for this cell's biome."""
        return BIOME_MOVE_COST.get(self.biome, 1.0)

    @property
    def is_passable(self) -> bool:
        """Whether land-based travel can cross this cell."""
        return self.biome != "ocean"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "x": self.x,
            "y": self.y,
            "biome": self.biome,
            "elevation": self.elevation,
            "moisture": self.moisture,
            "temperature": self.temperature,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TerrainCell":
        return cls(
            x=data["x"],
            y=data["y"],
            biome=data.get("biome", "plains"),
            elevation=data.get("elevation", 128),
            moisture=data.get("moisture", 128),
            temperature=data.get("temperature", 128),
        )


# ------------------------------------------------------------------
# Site
# ------------------------------------------------------------------

@dataclass(slots=True)
class Site:
    """A named location placed on the terrain grid.

    A Site links a ``location_id`` (which maps to a ``LocationState``
    in the World) to a terrain coordinate.  The ``site_type`` may
    differ from the terrain biome — e.g. a city on a plains cell.

    Attributes:
        location_id: Matches ``LocationState.id``.
        x: Terrain grid x coordinate where this site sits.
        y: Terrain grid y coordinate where this site sits.
        site_type: Logical type (city, village, dungeon, etc.).
        importance: 0-100 scale for label prioritisation on maps.
        atlas_x: Pre-computed atlas canvas x coordinate (-1 = unset).
        atlas_y: Pre-computed atlas canvas y coordinate (-1 = unset).
    """

    location_id: str
    x: int
    y: int
    site_type: str = "city"
    importance: int = 50
    atlas_x: int = -1
    atlas_y: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location_id": self.location_id,
            "x": self.x,
            "y": self.y,
            "site_type": self.site_type,
            "importance": self.importance,
            "atlas_x": self.atlas_x,
            "atlas_y": self.atlas_y,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Site":
        return cls(
            location_id=data["location_id"],
            x=data["x"],
            y=data["y"],
            site_type=data.get("site_type", "city"),
            importance=data.get("importance", 50),
            atlas_x=data.get("atlas_x", -1),
            atlas_y=data.get("atlas_y", -1),
        )


# ------------------------------------------------------------------
# RouteEdge
# ------------------------------------------------------------------

#: Canonical route types.
ROUTE_TYPES: List[str] = [
    "road",
    "trail",
    "sea_lane",
    "mountain_pass",
    "river_crossing",
]

#: Base travel cost multiplier per route type.
ROUTE_BASE_COST: Dict[str, float] = {
    "road": 1.0,
    "trail": 1.5,
    "sea_lane": 1.2,
    "mountain_pass": 2.0,
    "river_crossing": 1.3,
}


@dataclass(slots=True)
class RouteEdge:
    """A navigable connection between two sites.

    Routes are bidirectional by default.  They sit on the site
    overlay layer, not on terrain — although terrain biome and
    elevation may influence route cost or passability in the future.

    Attributes:
        route_id: Unique identifier for this route.
        from_site_id: ``location_id`` of the origin site.
        to_site_id: ``location_id`` of the destination site.
        route_type: One of ``ROUTE_TYPES``.
        distance: Abstract distance units (default 1).
        blocked: Whether the route is currently impassable.
    """

    route_id: str
    from_site_id: str
    to_site_id: str
    route_type: str = "road"
    distance: int = 1
    blocked: bool = False

    @property
    def base_cost(self) -> float:
        """Travel cost multiplier for this route type."""
        return ROUTE_BASE_COST.get(self.route_type, 1.0)

    def connects(self, site_id: str) -> bool:
        """Return True if this route touches the given site."""
        return self.from_site_id == site_id or self.to_site_id == site_id

    def other_end(self, site_id: str) -> Optional[str]:
        """Return the site at the other end, or None if not connected."""
        if self.from_site_id == site_id:
            return self.to_site_id
        if self.to_site_id == site_id:
            return self.from_site_id
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "from_site_id": self.from_site_id,
            "to_site_id": self.to_site_id,
            "route_type": self.route_type,
            "distance": self.distance,
            "blocked": self.blocked,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RouteEdge":
        return cls(
            route_id=data["route_id"],
            from_site_id=data["from_site_id"],
            to_site_id=data["to_site_id"],
            route_type=data.get("route_type", "road"),
            distance=data.get("distance", 1),
            blocked=_bool_payload(data.get("blocked", False), field_name="blocked"),
        )


# ------------------------------------------------------------------
# TerrainMap - container for the terrain grid
# ------------------------------------------------------------------

@dataclass(slots=True)
class TerrainMap:
    """Container for the full terrain grid.

    Holds a ``width x height`` grid of ``TerrainCell`` objects keyed
    by ``(x, y)`` coordinates.  This is the *terrain layer* that
    Sites are placed upon.
    """

    width: int
    height: int
    cells: Dict[Tuple[int, int], TerrainCell] = field(default_factory=dict)

    def get(self, x: int, y: int) -> Optional[TerrainCell]:
        """Return the cell at (x, y), or None if out of bounds."""
        return self.cells.get((x, y))

    def set_cell(self, cell: TerrainCell) -> None:
        """Place or replace a cell in the grid.

        Raises ``ValueError`` if the cell's coordinates are outside
        the declared ``width x height`` bounds.
        """
        if not self.in_bounds(cell.x, cell.y):
            raise ValueError(
                f"TerrainCell ({cell.x}, {cell.y}) is outside "
                f"terrain bounds ({self.width}x{self.height})"
            )
        self.cells[(cell.x, cell.y)] = cell

    def in_bounds(self, x: int, y: int) -> bool:
        """Check whether (x, y) is within the grid."""
        return 0 <= x < self.width and 0 <= y < self.height

    def neighbors(self, x: int, y: int) -> List[TerrainCell]:
        """Return 4-directional neighbor cells that exist."""
        result: List[TerrainCell] = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            cell = self.cells.get((x + dx, y + dy))
            if cell is not None:
                result.append(cell)
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "width": self.width,
            "height": self.height,
            "cells": [cell.to_dict() for cell in self.cells.values()],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TerrainMap":
        tmap = cls(
            width=data["width"],
            height=data["height"],
        )
        for cell_data in data.get("cells", []):
            cell = TerrainCell.from_dict(cell_data)
            tmap.set_cell(cell)
        return tmap


# ------------------------------------------------------------------
# AtlasLayout — persistent macro geography layer (PR-G2 item 7)
# ------------------------------------------------------------------

@dataclass(slots=True)
class AtlasLayout:
    """Persistent macro geography for the atlas-scale map.

    Stores continent outlines, sea area names, and major mountain
    ranges as named regions so the atlas renderer can draw a stable
    map without regenerating the geography on every render.

    ``continents``
        Each entry is ``{"name": str, "cells": [(x, y), ...]}``.
    ``seas``
        Named ocean / sea areas: ``{"name": str, "cells": [(x, y), ...]}``.
    ``mountain_ranges``
        Named ranges: ``{"name": str, "cells": [(x, y), ...]}``.
    ``canvas_w`` / ``canvas_h``
        Atlas canvas dimensions the layout was generated for.
    """

    canvas_w: int = 72
    canvas_h: int = 30
    continents: List[Dict[str, Any]] = field(default_factory=list)
    seas: List[Dict[str, Any]] = field(default_factory=list)
    mountain_ranges: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        def _normalize_regions(regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            normalized: List[Dict[str, Any]] = []
            for region in regions:
                cells = []
                for cell in region.get("cells", []):
                    if isinstance(cell, (list, tuple)) and len(cell) == 2:
                        cells.append([int(cell[0]), int(cell[1])])
                normalized.append({
                    "name": region.get("name", ""),
                    "cells": cells,
                })
            return normalized

        return {
            "canvas_w": self.canvas_w,
            "canvas_h": self.canvas_h,
            "continents": _normalize_regions(self.continents),
            "seas": _normalize_regions(self.seas),
            "mountain_ranges": _normalize_regions(self.mountain_ranges),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AtlasLayout":
        return cls(
            canvas_w=data.get("canvas_w", 72),
            canvas_h=data.get("canvas_h", 30),
            continents=deepcopy(data.get("continents", [])),
            seas=deepcopy(data.get("seas", [])),
            mountain_ranges=deepcopy(data.get("mountain_ranges", [])),
        )


# ------------------------------------------------------------------
# Atlas helpers
# ------------------------------------------------------------------

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


def build_default_atlas_layout(
    inputs: Optional[AtlasLayoutInputs] = None,
    *,
    site_coords: Optional[List[Tuple[int, int]]] = None,
    route_coords: Optional[List[Tuple[Tuple[int, int], Tuple[int, int]]]] = None,
    mountain_coords: Optional[List[Tuple[int, int]]] = None,
) -> AtlasLayout:
    """Create the default persistent atlas layout for the current world."""
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

    return AtlasLayout(
        canvas_w=ATLAS_CANVAS_W,
        canvas_h=ATLAS_CANVAS_H,
        continents=[
            {
                "name": "Main Continent" if idx == 0 else f"Continent {idx + 1}",
                "cells": sorted(component),
            }
            for idx, component in enumerate(
                sorted(continent_components, key=lambda component: (-len(component), sorted(component)[0]))
            )
        ],
        seas=[
            {
                "name": "Great Ocean" if idx == 0 else f"Sea {idx + 1}",
                "cells": sorted(component),
            }
            for idx, component in enumerate(
                sorted(sea_components, key=lambda component: (-len(component), sorted(component)[0]))
            )
        ],
        mountain_ranges=[
            {
                "name": "World Spine" if idx == 0 else f"Range {idx + 1}",
                "cells": sorted(component),
            }
            for idx, component in enumerate(
                sorted(mountain_components, key=lambda component: (-len(component), sorted(component)[0]))
            )
        ],
    )


@lru_cache(maxsize=64)
def _cached_atlas_layout_template(
    site_coords: Tuple[Tuple[int, int], ...],
    route_coords: Tuple[Tuple[Tuple[int, int], Tuple[int, int]], ...],
    mountain_coords: Tuple[Tuple[int, int], ...],
) -> AtlasLayout:
    return build_default_atlas_layout(
        AtlasLayoutInputs(
            site_coords=list(site_coords),
            route_coords=list(route_coords),
            mountain_coords=list(mountain_coords),
        )
    )


def build_cached_world_structure(
    *,
    width: int,
    height: int,
    locations: Optional[List[Tuple[str, str, str, str, int, int]]] = None,
    route_specs: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[TerrainMap, List[Site], List[RouteEdge], AtlasLayout]:
    """Build world structure while caching only the atlas geometry projection."""
    terrain_map, sites, routes = build_default_terrain(
        width=width,
        height=height,
        locations=locations,
        route_specs=route_specs,
    )
    inputs = assemble_atlas_layout_inputs(
        width=width,
        height=height,
        sites=sites,
        routes=routes,
        terrain_cells=list(terrain_map.cells.values()),
    )
    atlas_layout = _cached_atlas_layout_template(
        tuple(inputs.site_coords),
        tuple(inputs.route_coords),
        tuple(inputs.mountain_coords),
    )
    return (
        terrain_map,
        sites,
        routes,
        deepcopy(atlas_layout),
    )


# ------------------------------------------------------------------
# Default terrain generation for the legacy 5x5 world
# ------------------------------------------------------------------

#: Mapping from the existing ``region_type`` to the biome that best
#: approximates the same terrain feel.  Used when upgrading a legacy
#: 5×5 world to the new terrain + site model.
REGION_TYPE_TO_BIOME: Dict[str, str] = {
    "city": "plains",
    "village": "plains",
    "forest": "forest",
    "dungeon": "hills",
    "mountain": "mountain",
    "plains": "plains",
    "sea": "ocean",
}

#: Importance defaults per site type (higher = more prominent on map).
SITE_IMPORTANCE: Dict[str, int] = {
    "city": 80,
    "village": 40,
    "forest": 20,
    "dungeon": 60,
    "mountain": 30,
    "plains": 20,
    "sea": 10,
}


def build_default_terrain(
    width: int = 5,
    height: int = 5,
    locations: Optional[List] = None,
    route_specs: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[TerrainMap, List[Site], List[RouteEdge]]:
    """Generate terrain, sites, and routes from a location list.

    Only locations whose ``(x, y)`` fall within ``0 <= x < width`` and
    ``0 <= y < height`` are included.  Out-of-bounds entries are
    silently skipped.

    When ``locations`` is *None*, ``DEFAULT_LOCATIONS`` is used, but
    the bounds filter still applies — so a 3×3 world with the default
    25-entry list will only contain the locations that fit.

    When ``route_specs`` is provided, those explicit route definitions
    become the canonical site graph. Otherwise adjacent sites
    (4-directional) are connected by auto-generated provisional routes
    (see *PR-G note* below).

    .. note:: PR-G provisional routes

       Routes generated here are **provisional legacy bridges** derived
       from 4-directional grid adjacency.  They do not represent a
       canonical world topology.  Future PRs should replace them with
       explicit route definitions when worldgen or custom map editing
       is introduced.

    Returns:
        (terrain_map, sites, routes)
    """
    if locations is None:
        from .content.world_data import DEFAULT_LOCATIONS
        locations = DEFAULT_LOCATIONS

    tmap = TerrainMap(width=width, height=height)

    # Initialise all in-bounds cells with plains
    for y in range(height):
        for x in range(width):
            tmap.set_cell(TerrainCell(x=x, y=y, biome="plains"))

    # Build sites and set terrain biomes — skip out-of-bounds locations
    sites: List[Site] = []
    site_coords: Dict[Tuple[int, int], str] = {}
    for entry in locations:
        loc_id, _name, _desc, region_type, x, y = entry
        if not tmap.in_bounds(x, y):
            continue
        biome = REGION_TYPE_TO_BIOME.get(region_type, "plains")
        importance = SITE_IMPORTANCE.get(region_type, 50)

        cell = tmap.get(x, y)
        if cell is not None:
            cell.biome = biome

        sites.append(Site(
            location_id=loc_id,
            x=x,
            y=y,
            site_type=region_type,
            importance=importance,
        ))
        site_coords[(x, y)] = loc_id

    routes: List[RouteEdge] = []
    if route_specs is not None:
        valid_site_ids = {site.location_id for site in sites}
        for spec in route_specs:
            from_site_id = str(spec["from_site_id"])
            to_site_id = str(spec["to_site_id"])
            if from_site_id not in valid_site_ids or to_site_id not in valid_site_ids:
                continue
            routes.append(RouteEdge(
                route_id=str(spec["route_id"]),
                from_site_id=from_site_id,
                to_site_id=to_site_id,
                route_type=str(spec.get("route_type", "road")),
                distance=int(spec.get("distance", 1)),
                blocked=_bool_payload(spec.get("blocked", False), field_name="blocked"),
            ))
    else:
        # Auto-generate provisional routes between adjacent sites.
        # These are legacy bridges based on grid adjacency; see docstring.
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

                from_biome = (tmap.get(x, y) or TerrainCell(x=x, y=y)).biome
                to_biome = (tmap.get(nx, ny) or TerrainCell(x=nx, y=ny)).biome
                if "mountain" in (from_biome, to_biome):
                    route_type = "mountain_pass"
                elif "ocean" in (from_biome, to_biome):
                    route_type = "sea_lane"
                elif "swamp" in (from_biome, to_biome):
                    route_type = "trail"
                else:
                    route_type = "road"

                routes.append(RouteEdge(
                    route_id=f"route_{route_counter:03d}",
                    from_site_id=loc_id,
                    to_site_id=neighbor_id,
                    route_type=route_type,
                ))

    # --- Compute atlas coordinates for each site ---
    # These are deterministic projections from grid coords to atlas canvas
    # and are persisted so the atlas is stable across renders.
    for site in sites:
        site.atlas_x, site.atlas_y = project_atlas_coords(
            site.x,
            site.y,
            width=width,
            height=height,
        )

    return tmap, sites, routes


def build_terrain_payload_from_locations(
    width: int,
    height: int,
    locations: List,
    route_specs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Return serialized terrain/site/route payloads for a location list."""
    terrain_map, sites, routes = build_default_terrain(
        width=width,
        height=height,
        locations=locations,
        route_specs=route_specs,
    )
    return {
        "terrain_map": terrain_map.to_dict(),
        "sites": [site.to_dict() for site in sites],
        "routes": [route.to_dict() for route in routes],
    }

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

from copy import deepcopy
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional, Tuple

from .terrain_payloads import (
    atlas_layout_payload,
    normalize_route_payload,
    route_payload,
    site_payload,
    terrain_cell_payload,
    terrain_map_payload,
    terrain_structure_payload,
)
from .terrain_route_generation import (
    ATLAS_CANVAS_H,
    ATLAS_CANVAS_W,
    ATLAS_MARGIN_X,
    ATLAS_MARGIN_Y,
    AtlasLayoutInputs,
    assemble_atlas_layout_inputs,
    build_default_atlas_layout_data,
    project_atlas_coords,
    provisional_route_specs_from_grid_adjacency,
)

_ATLAS_PUBLIC_CONSTANTS = (ATLAS_CANVAS_W, ATLAS_CANVAS_H, ATLAS_MARGIN_X, ATLAS_MARGIN_Y)


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
        return terrain_cell_payload(self)

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
        return site_payload(self)

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
    _on_change: Optional[Callable[[], None]] = field(default=None, repr=False, compare=False)

    def __setattr__(self, name: str, value: Any) -> None:
        callback = None
        old_value = None
        had_old_value = False
        if name in {"route_id", "from_site_id", "to_site_id", "route_type", "distance", "blocked"}:
            try:
                old_value = object.__getattribute__(self, name)
                had_old_value = True
            except AttributeError:
                had_old_value = False
            try:
                callback = object.__getattribute__(self, "_on_change")
            except AttributeError:
                callback = None
        object.__setattr__(self, name, value)
        if (
            name in {"route_id", "from_site_id", "to_site_id", "route_type", "distance", "blocked"}
            and callback is not None
            and (not had_old_value or old_value != value)
        ):
            callback()

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
        return route_payload(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RouteEdge":
        payload = normalize_route_payload(data)
        return cls(
            route_id=payload["route_id"],
            from_site_id=payload["from_site_id"],
            to_site_id=payload["to_site_id"],
            route_type=payload["route_type"],
            distance=payload["distance"],
            blocked=payload["blocked"],
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
        return terrain_map_payload(self.width, self.height, self.cells.values())

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
        return atlas_layout_payload(
            canvas_w=self.canvas_w,
            canvas_h=self.canvas_h,
            continents=self.continents,
            seas=self.seas,
            mountain_ranges=self.mountain_ranges,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AtlasLayout":
        return cls(
            canvas_w=data.get("canvas_w", 72),
            canvas_h=data.get("canvas_h", 30),
            continents=deepcopy(data.get("continents", [])),
            seas=deepcopy(data.get("seas", [])),
            mountain_ranges=deepcopy(data.get("mountain_ranges", [])),
        )


def build_default_atlas_layout(
    inputs: Optional[AtlasLayoutInputs] = None,
    *,
    site_coords: Optional[List[Tuple[int, int]]] = None,
    route_coords: Optional[List[Tuple[Tuple[int, int], Tuple[int, int]]]] = None,
    mountain_coords: Optional[List[Tuple[int, int]]] = None,
) -> AtlasLayout:
    """Create the default persistent atlas layout for the current world."""
    return AtlasLayout.from_dict(
        build_default_atlas_layout_data(
            inputs,
            site_coords=site_coords,
            route_coords=route_coords,
            mountain_coords=mountain_coords,
        )
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

    Explicit ``route_specs`` must reference in-bounds sites present in the
    supplied location set; malformed or dangling route definitions fail fast.

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
            payload = normalize_route_payload(spec)
            if payload["from_site_id"] not in valid_site_ids or payload["to_site_id"] not in valid_site_ids:
                raise ValueError(f"route {payload['route_id']} references an unknown site")
            routes.append(RouteEdge.from_dict(payload))
    else:
        routes = [
            RouteEdge.from_dict(spec)
            for spec in provisional_route_specs_from_grid_adjacency(
                site_coords,
                biome_at=lambda x, y: (tmap.get(x, y) or TerrainCell(x=x, y=y)).biome,
            )
        ]

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
    return terrain_structure_payload(terrain_map, sites, routes)

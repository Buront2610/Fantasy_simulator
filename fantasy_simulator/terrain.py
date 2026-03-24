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

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


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

@dataclass
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

@dataclass
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
    """

    location_id: str
    x: int
    y: int
    site_type: str = "city"
    importance: int = 50

    def to_dict(self) -> Dict[str, Any]:
        return {
            "location_id": self.location_id,
            "x": self.x,
            "y": self.y,
            "site_type": self.site_type,
            "importance": self.importance,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Site":
        return cls(
            location_id=data["location_id"],
            x=data["x"],
            y=data["y"],
            site_type=data.get("site_type", "city"),
            importance=data.get("importance", 50),
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


@dataclass
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
            blocked=data.get("blocked", False),
        )


# ------------------------------------------------------------------
# TerrainMap - container for the terrain grid
# ------------------------------------------------------------------

@dataclass
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
# Default terrain generation for the legacy 5x5 world
# ------------------------------------------------------------------

#: Mapping from the existing ``region_type`` to the biome that best
#: approximates the same terrain feel.  Used when upgrading a legacy
#: 5×5 world to the new terrain + site model.
_REGION_TYPE_TO_BIOME: Dict[str, str] = {
    "city": "plains",
    "village": "plains",
    "forest": "forest",
    "dungeon": "hills",
    "mountain": "mountain",
    "plains": "plains",
    "sea": "ocean",
}

#: Importance defaults per site type (higher = more prominent on map).
_SITE_IMPORTANCE: Dict[str, int] = {
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
) -> Tuple[TerrainMap, List[Site], List[RouteEdge]]:
    """Generate terrain, sites, and routes from a location list.

    Only locations whose ``(x, y)`` fall within ``0 <= x < width`` and
    ``0 <= y < height`` are included.  Out-of-bounds entries are
    silently skipped.

    When ``locations`` is *None*, ``DEFAULT_LOCATIONS`` is used, but
    the bounds filter still applies — so a 3×3 world with the default
    25-entry list will only contain the locations that fit.

    Adjacent sites (4-directional) are connected by auto-generated
    provisional routes (see *PR-G note* below).

    .. note:: PR-G provisional routes

       Routes generated here are **provisional legacy bridges** derived
       from 4-directional grid adjacency.  They do not represent a
       canonical world topology.  Future PRs should replace them with
       explicit route definitions when worldgen or custom map editing
       is introduced.

    Returns:
        (terrain_map, sites, routes)
    """
    from .content.world_data import DEFAULT_LOCATIONS

    if locations is None:
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
        biome = _REGION_TYPE_TO_BIOME.get(region_type, "plains")
        importance = _SITE_IMPORTANCE.get(region_type, 50)

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

    # Auto-generate provisional routes between adjacent sites.
    # These are legacy bridges based on grid adjacency; see docstring.
    routes: List[RouteEdge] = []
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

            # Determine route type from terrain
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

    return tmap, sites, routes

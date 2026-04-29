"""Terrain, site, route, and atlas layout data models."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from .terrain_payloads import (
    atlas_layout_payload,
    normalize_route_payload,
    route_payload,
    site_payload,
    terrain_cell_payload,
    terrain_map_payload,
)

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

ROUTE_TYPES: List[str] = [
    "road",
    "trail",
    "sea_lane",
    "mountain_pass",
    "river_crossing",
]

ROUTE_BASE_COST: Dict[str, float] = {
    "road": 1.0,
    "trail": 1.5,
    "sea_lane": 1.2,
    "mountain_pass": 2.0,
    "river_crossing": 1.3,
}


@dataclass(slots=True)
class TerrainCell:
    """A single physical landscape cell."""

    x: int
    y: int
    biome: str = "plains"
    elevation: int = 128
    moisture: int = 128
    temperature: int = 128

    @property
    def glyph(self) -> str:
        return BIOME_GLYPHS.get(self.biome, "?")

    @property
    def move_cost(self) -> float:
        return BIOME_MOVE_COST.get(self.biome, 1.0)

    @property
    def is_passable(self) -> bool:
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


@dataclass(slots=True)
class Site:
    """A named location placed on the terrain grid."""

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


@dataclass(slots=True)
class RouteEdge:
    """A navigable bidirectional connection between two sites."""

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
        return ROUTE_BASE_COST.get(self.route_type, 1.0)

    def connects(self, site_id: str) -> bool:
        return self.from_site_id == site_id or self.to_site_id == site_id

    def other_end(self, site_id: str) -> Optional[str]:
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


@dataclass(slots=True)
class TerrainMap:
    """Container for the full terrain grid."""

    width: int
    height: int
    cells: Dict[Tuple[int, int], TerrainCell] = field(default_factory=dict)

    def get(self, x: int, y: int) -> Optional[TerrainCell]:
        return self.cells.get((x, y))

    def set_cell(self, cell: TerrainCell) -> None:
        if not self.in_bounds(cell.x, cell.y):
            raise ValueError(
                f"TerrainCell ({cell.x}, {cell.y}) is outside "
                f"terrain bounds ({self.width}x{self.height})"
            )
        self.cells[(cell.x, cell.y)] = cell

    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def neighbors(self, x: int, y: int) -> List[TerrainCell]:
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


@dataclass(slots=True)
class AtlasLayout:
    """Persistent macro geography for the atlas-scale map."""

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

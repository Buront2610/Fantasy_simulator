"""Input normalization for persistent terrain atlas layouts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple


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

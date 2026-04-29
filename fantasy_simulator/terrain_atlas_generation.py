"""Atlas projection and landmass generation helpers for terrain topology."""

from __future__ import annotations

from .terrain_atlas_inputs import (
    ATLAS_CANVAS_H,
    ATLAS_CANVAS_W,
    ATLAS_MARGIN_X,
    ATLAS_MARGIN_Y,
    AtlasLayoutInputs,
    _read_field,
    assemble_atlas_layout_inputs,
    project_atlas_coords,
)
from .terrain_atlas_landmass import (
    _atlas_line_points,
    _build_cluster_land,
    _cluster_atlas_sites,
    _coast_noise,
    _connected_components,
    _named_components,
    _stamp_atlas_cells,
    build_default_atlas_layout_data,
)


__all__ = [
    "ATLAS_CANVAS_H",
    "ATLAS_CANVAS_W",
    "ATLAS_MARGIN_X",
    "ATLAS_MARGIN_Y",
    "AtlasLayoutInputs",
    "_atlas_line_points",
    "_build_cluster_land",
    "_cluster_atlas_sites",
    "_coast_noise",
    "_connected_components",
    "_named_components",
    "_read_field",
    "_stamp_atlas_cells",
    "assemble_atlas_layout_inputs",
    "build_default_atlas_layout_data",
    "project_atlas_coords",
]

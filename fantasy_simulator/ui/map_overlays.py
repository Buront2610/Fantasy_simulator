"""Shared overlay marker helpers for map observation renderers."""

from __future__ import annotations

from typing import List

from .map_view_models import MapCellInfo


def _overlay_suffix(cell: MapCellInfo) -> str:
    """Compact overlay markers for a site cell."""
    parts: List[str] = []
    if cell.danger_band == "high":
        parts.append("!")
    if cell.traffic_band == "high":
        parts.append("$")
    if cell.rumor_heat_band == "high":
        parts.append("?")
    if cell.has_memorial:
        parts.append("m")
    if cell.has_alias:
        parts.append("a")
    if cell.recent_death_site:
        parts.append("+")
    if cell.recent_world_change_count:
        parts.append("w")
    return "".join(parts)

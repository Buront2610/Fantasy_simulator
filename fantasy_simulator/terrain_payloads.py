"""Payload validation and serialization helpers for terrain models."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def bool_payload(payload: Any, *, field_name: str) -> bool:
    if not isinstance(payload, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return payload


def string_payload(payload: Any, *, field_name: str) -> str:
    if not isinstance(payload, str) or not payload:
        raise ValueError(f"{field_name} must be a non-empty string")
    return payload


def int_payload(payload: Any, *, field_name: str, minimum: Optional[int] = None) -> int:
    if isinstance(payload, bool) or not isinstance(payload, int):
        raise ValueError(f"{field_name} must be an integer")
    if minimum is not None and payload < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return payload


def normalize_route_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize serialized route payload fields."""
    return {
        "route_id": string_payload(data["route_id"], field_name="route_id"),
        "from_site_id": string_payload(data["from_site_id"], field_name="from_site_id"),
        "to_site_id": string_payload(data["to_site_id"], field_name="to_site_id"),
        "route_type": string_payload(data.get("route_type", "road"), field_name="route_type"),
        "distance": int_payload(data.get("distance", 1), field_name="distance", minimum=1),
        "blocked": bool_payload(data.get("blocked", False), field_name="blocked"),
    }


def terrain_cell_payload(cell: Any) -> Dict[str, Any]:
    return {
        "x": cell.x,
        "y": cell.y,
        "biome": cell.biome,
        "elevation": cell.elevation,
        "moisture": cell.moisture,
        "temperature": cell.temperature,
    }


def site_payload(site: Any) -> Dict[str, Any]:
    return {
        "location_id": site.location_id,
        "x": site.x,
        "y": site.y,
        "site_type": site.site_type,
        "importance": site.importance,
        "atlas_x": site.atlas_x,
        "atlas_y": site.atlas_y,
    }


def route_payload(route: Any) -> Dict[str, Any]:
    return {
        "route_id": route.route_id,
        "from_site_id": route.from_site_id,
        "to_site_id": route.to_site_id,
        "route_type": route.route_type,
        "distance": route.distance,
        "blocked": route.blocked,
    }


def terrain_map_payload(width: int, height: int, cells: Iterable[Any]) -> Dict[str, Any]:
    return {
        "width": width,
        "height": height,
        "cells": [terrain_cell_payload(cell) for cell in cells],
    }


def normalize_atlas_regions(regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
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


def atlas_layout_payload(
    *,
    canvas_w: int,
    canvas_h: int,
    continents: List[Dict[str, Any]],
    seas: List[Dict[str, Any]],
    mountain_ranges: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "canvas_w": canvas_w,
        "canvas_h": canvas_h,
        "continents": normalize_atlas_regions(continents),
        "seas": normalize_atlas_regions(seas),
        "mountain_ranges": normalize_atlas_regions(mountain_ranges),
    }


def terrain_structure_payload(terrain_map: Any, sites: Iterable[Any], routes: Iterable[Any]) -> Dict[str, Any]:
    """Return serialized terrain/site/route payloads."""
    return {
        "terrain_map": terrain_map.to_dict(),
        "sites": [site.to_dict() for site in sites],
        "routes": [route.to_dict() for route in routes],
    }

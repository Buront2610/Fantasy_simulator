"""Loading and validation for serializable setting bundles."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping

from .setting_bundle_schema import (
    RouteSeedDefinition,
    SettingBundle,
)
from .setting_bundle_source import DEFAULT_AETHORIA_BUNDLE_PATH, default_aethoria_bundle_data
from .setting_bundle_validation import validate_setting_bundle


def _backfill_route_seeds_if_missing(
    bundle: SettingBundle,
    *,
    route_seeds_were_present: bool,
) -> None:
    """Populate canonical route seeds for legacy bundles that only ship site seeds."""
    world = bundle.world_definition
    if route_seeds_were_present or not world.site_seeds:
        return

    from ..terrain import build_default_terrain

    width = max(seed.x for seed in world.site_seeds) + 1
    height = max(seed.y for seed in world.site_seeds) + 1
    _terrain_map, _sites, routes = build_default_terrain(
        width=width,
        height=height,
        locations=[seed.as_world_data_entry() for seed in world.site_seeds],
    )
    world.route_seeds = [
        RouteSeedDefinition(
            route_id=route.route_id,
            from_site_id=route.from_site_id,
            to_site_id=route.to_site_id,
            route_type=route.route_type,
            distance=route.distance,
            blocked=route.blocked,
        )
        for route in routes
    ]


def bundle_from_dict_validated(data: Dict[str, Any], *, source: str) -> SettingBundle:
    """Construct a SettingBundle and enforce bundle invariants."""
    try:
        bundle = SettingBundle.from_dict(data)
    except KeyError as exc:
        missing = exc.args[0]
        raise ValueError(f"Setting bundle {source} is missing required field: {missing}") from exc
    world_definition_data = data.get("world_definition", {})
    route_seeds_were_present = (
        isinstance(world_definition_data, Mapping)
        and "route_seeds" in world_definition_data
    )
    _backfill_route_seeds_if_missing(
        bundle,
        route_seeds_were_present=route_seeds_were_present,
    )
    validate_setting_bundle(bundle, source=source)
    return bundle


def default_aethoria_bundle(
    *,
    display_name: str | None = None,
    lore_text: str | None = None,
) -> SettingBundle:
    """Return the default bundled Aethoria setting as a mutable copy."""

    bundle = bundle_from_dict_validated(default_aethoria_bundle_data(), source=str(DEFAULT_AETHORIA_BUNDLE_PATH))
    if display_name is not None:
        bundle.world_definition.display_name = display_name
    if lore_text is not None:
        bundle.world_definition.lore_text = lore_text
    return bundle


def load_setting_bundle(path: str | Path) -> SettingBundle:
    """Load a setting bundle from a JSON file."""

    bundle_path = Path(path)
    try:
        data = json.loads(bundle_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Setting bundle not found: {bundle_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid setting bundle JSON in {bundle_path}: {exc.msg}") from exc
    return bundle_from_dict_validated(data, source=str(bundle_path))

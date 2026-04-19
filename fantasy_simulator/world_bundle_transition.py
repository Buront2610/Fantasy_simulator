"""Bundle transition helpers for ``World``."""

from __future__ import annotations

from typing import Any, Callable, Tuple

from .content.setting_bundle import SettingBundle, validate_setting_bundle
from .rule_override_resolution import (
    resolve_event_impact_rule_overrides,
    resolve_propagation_rule_overrides,
)
from .world_language import language_signature, prune_runtime_states
from .world_location_references import LocationReferenceResolver


def set_setting_bundle_metadata(
    world: Any,
    bundle: SettingBundle,
    *,
    clone_bundle: Callable[[SettingBundle], SettingBundle],
    clone_calendar: Callable[[Any], Any],
) -> None:
    """Replace bundle-backed metadata without rebuilding world structure."""
    previous_calendar = None
    if hasattr(world, "_setting_bundle") and world._setting_bundle is not None:
        previous_calendar = world._setting_bundle.world_definition.calendar.to_dict()
    world._setting_bundle = clone_bundle(bundle)
    world._location_reference_resolver = LocationReferenceResolver.from_site_seeds(
        world._setting_bundle.world_definition.site_seeds
    )
    world._language_engine = None
    world._language_runtime_states = prune_runtime_states(
        world._setting_bundle.world_definition,
        getattr(world, "_language_runtime_states", {}),
    )
    if hasattr(world, "lore"):
        world.lore = world._setting_bundle.world_definition.lore_text
    if hasattr(world, "calendar_baseline"):
        next_calendar = world._setting_bundle.world_definition.calendar
        if previous_calendar is None or previous_calendar != next_calendar.to_dict():
            world.calendar_baseline = clone_calendar(next_calendar)
            if hasattr(world, "calendar_history"):
                world.calendar_history = []
    world.event_impact_rules = resolve_event_impact_rule_overrides(
        world._setting_bundle.world_definition.event_impact_rules
    )
    world.propagation_rules = resolve_propagation_rule_overrides(
        world._setting_bundle.world_definition.propagation_rules
    )


def topology_signature(bundle: SettingBundle) -> Tuple[Tuple[Any, ...], Tuple[Any, ...]]:
    """Return a stable topology signature for a bundle."""
    world = bundle.world_definition
    site_signature = tuple(
        (seed.location_id, seed.region_type, seed.x, seed.y)
        for seed in world.site_seeds
    )
    route_signature = tuple(
        (
            seed.route_id,
            seed.from_site_id,
            seed.to_site_id,
            seed.route_type,
            int(seed.distance),
            bool(seed.blocked),
        )
        for seed in world.route_seeds
    )
    return site_signature, route_signature


def apply_setting_bundle(
    world: Any,
    bundle: SettingBundle,
    *,
    clone_bundle: Callable,
    clone_calendar: Callable,
) -> None:
    """Apply a bundle while keeping derived world structures consistent."""
    validate_setting_bundle(bundle, source="World.setting_bundle")
    previous_bundle = getattr(world, "_setting_bundle", None)
    previous_language_signature = language_signature(world._setting_bundle.world_definition)
    previous_locations = list(getattr(world, "grid", {}).values())
    previous_generated_endonyms = {
        location.id: world.location_endonym(location.id) or ""
        for location in previous_locations
    }
    set_setting_bundle_metadata(
        world,
        bundle,
        clone_bundle=clone_bundle,
        clone_calendar=clone_calendar,
    )
    next_language_signature = language_signature(world._setting_bundle.world_definition)
    if previous_language_signature != next_language_signature:
        world.language_origin_year = world.year
        world.language_evolution_history = []
        world._language_runtime_states = {}
        world._language_engine = None
    if hasattr(world, "grid"):
        topology_changed = (
            previous_bundle is None
            or topology_signature(previous_bundle) != topology_signature(bundle)
        )
        if topology_changed:
            world._build_default_map(previous_locations=previous_locations)
            world._normalize_references_after_bundle_change()
        else:
            world._refresh_locations_from_site_seeds()
        if previous_language_signature != next_language_signature:
            world._refresh_generated_endonyms(
                stale_endonyms_by_location_id=previous_generated_endonyms,
            )

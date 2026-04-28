"""Shared helpers for save-data migrations."""

from __future__ import annotations

from typing import Any, Callable, Dict

from ..content.setting_bundle import bundle_from_dict_validated

_DEFAULT_LOCATIONS: list[tuple[str, str, str, str, int, int]] = []
_NAME_TO_LOCATION_ID: Dict[str, str] = {}
_FALLBACK_LOCATION_ID: Callable[[str], str] = lambda name: name
_LOCATION_STATE_DEFAULTS: Callable[..., Dict[str, Any]] = lambda *_args, **_kwargs: {}


def configure_legacy_world_data(
    *,
    default_locations: list[tuple[str, str, str, str, int, int]],
    name_to_location_id: Dict[str, str],
    fallback_location_id: Callable[[str], str],
    location_state_defaults: Callable[..., Dict[str, Any]],
) -> None:
    """Inject legacy world-data projections from the allowed migrations facade."""
    global _DEFAULT_LOCATIONS, _NAME_TO_LOCATION_ID, _FALLBACK_LOCATION_ID, _LOCATION_STATE_DEFAULTS
    _DEFAULT_LOCATIONS = list(default_locations)
    _NAME_TO_LOCATION_ID = dict(name_to_location_id)
    _FALLBACK_LOCATION_ID = fallback_location_id
    _LOCATION_STATE_DEFAULTS = location_state_defaults


def embedded_setting_bundle(data: Dict[str, Any]):
    world_data = data.get("world", {})
    bundle_data = world_data.get("setting_bundle")
    if bundle_data is None:
        return None
    return bundle_from_dict_validated(bundle_data, source="embedded world.setting_bundle during migration")


def location_name_to_id(data: Dict[str, Any]) -> Dict[str, str]:
    bundle = embedded_setting_bundle(data)
    if bundle is None:
        return dict(_NAME_TO_LOCATION_ID)
    return {
        seed.name: seed.location_id
        for seed in bundle.world_definition.site_seeds
    }


def default_locations_for_data(data: Dict[str, Any]) -> list[tuple[str, str, str, str, int, int]]:
    bundle = embedded_setting_bundle(data)
    if bundle is None:
        return list(_DEFAULT_LOCATIONS)
    return [
        seed.as_world_data_entry()
        for seed in bundle.world_definition.site_seeds
    ]


def site_tags_by_location_id(data: Dict[str, Any]) -> Dict[str, list[str]]:
    bundle = embedded_setting_bundle(data)
    if bundle is None:
        return {}
    return {
        seed.location_id: list(seed.tags)
        for seed in bundle.world_definition.site_seeds
    }


def resolve_location_id(data: Dict[str, Any], name: str) -> str:
    return location_name_to_id(data).get(name, _FALLBACK_LOCATION_ID(name))


def location_state_defaults(loc_id: str, region_type: str, *, site_tags: list[str] | None = None) -> Dict[str, Any]:
    return _LOCATION_STATE_DEFAULTS(loc_id, region_type, site_tags=site_tags)


def calendar_key_for_data(data: Dict[str, Any]) -> str:
    bundle = embedded_setting_bundle(data)
    if bundle is not None:
        return bundle.world_definition.calendar.calendar_key
    return ""

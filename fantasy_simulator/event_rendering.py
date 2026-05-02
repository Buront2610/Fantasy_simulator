"""Locale-aware rendering helpers for canonical world event records."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Optional

from .content.setting_bundle_inspection import setting_entry_key
from .event_models import WorldEventRecord
from .i18n import get_locale, tr_for_locale


Translator = Callable[..., str]


def _translator_for_locale(locale: Optional[str]) -> Translator:
    if locale is None:
        return lambda key, **kwargs: tr_for_locale(get_locale(), key, **kwargs)
    return lambda key, **kwargs: tr_for_locale(locale, key, **kwargs)


def _location_display_name(location_id: Any, world: object = None) -> Optional[str]:
    if not isinstance(location_id, str) or not location_id:
        return None
    if world is None:
        return None

    get_location_by_id = getattr(world, "get_location_by_id", None)
    if callable(get_location_by_id):
        location = get_location_by_id(location_id)
        canonical_name = getattr(location, "canonical_name", None)
        if isinstance(canonical_name, str) and canonical_name:
            return canonical_name

    location_name = getattr(world, "location_name", None)
    if callable(location_name):
        try:
            resolved = location_name(location_id)
        except (KeyError, TypeError, ValueError):
            return None
        if isinstance(resolved, str) and resolved:
            return resolved
    return None


def _faction_display_name(faction_id: str, world: object = None) -> Optional[str]:
    if world is None:
        return None
    bundle = getattr(world, "_setting_bundle", None)
    if bundle is None:
        bundle = getattr(world, "setting_bundle", None)
    world_definition = getattr(bundle, "world_definition", None)
    faction_entries = getattr(world_definition, "faction_entries", None)
    if not callable(faction_entries):
        return None

    faction_key = setting_entry_key(faction_id)
    for entry in faction_entries():
        display_name = getattr(entry, "display_name", "")
        if faction_id == display_name or faction_key == getattr(entry, "key", ""):
            return display_name
    return None


def _display_faction(value: Any, *, world: object = None, translate: Translator) -> str:
    if value is None or value == "":
        return translate("event_change_no_faction")
    faction_id = str(value)
    return _faction_display_name(faction_id, world) or faction_id


def _render_params(record: WorldEventRecord, *, world: object = None, translate: Translator) -> dict[str, Any]:
    params = deepcopy(record.render_params)

    if "location" not in params:
        location_name = _location_display_name(params.get("location_id") or record.location_id, world)
        if location_name is not None:
            params["location"] = location_name

    if "from_location" not in params:
        from_location_name = _location_display_name(params.get("from_location_id"), world)
        if from_location_name is not None:
            params["from_location"] = from_location_name
    if "to_location" not in params:
        to_location_name = _location_display_name(params.get("to_location_id"), world)
        if to_location_name is not None:
            params["to_location"] = to_location_name

    if record.summary_key == "events.location_faction_changed.summary":
        if "old_faction_id" in params:
            params["old_faction"] = _display_faction(
                params["old_faction_id"],
                world=world,
                translate=translate,
            )
        if "new_faction_id" in params:
            params["new_faction"] = _display_faction(
                params["new_faction_id"],
                world=world,
                translate=translate,
            )
    return params


def render_event_record(
    record: WorldEventRecord,
    locale: Optional[str] = None,
    world: object = None,
    translate: Optional[Translator] = None,
    strict: bool = False,
) -> str:
    """Render a world event record summary for display.

    ``world`` is optional display context for resolving stable location and
    faction ids to current setting names.  It is never required for saved-record
    compatibility.
    """
    if not record.summary_key:
        return record.description

    resolved_translate = translate or _translator_for_locale(locale)
    try:
        rendered = resolved_translate(record.summary_key, **_render_params(
            record,
            world=world,
            translate=resolved_translate,
        ))
    except (KeyError, IndexError, TypeError, ValueError):
        if strict:
            raise
        return record.description

    if rendered == record.summary_key:
        if strict:
            raise KeyError(record.summary_key)
        return record.description
    return rendered

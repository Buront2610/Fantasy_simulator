"""Locale-aware rendering helpers for canonical world event records."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Optional, Protocol

from .content.setting_bundle_inspection import setting_entry_key
from .event_models import WorldEventRecord
from .i18n import get_locale, tr_for_locale


Translator = Callable[..., str]


class EventRenderContext(Protocol):
    """World-facing API used to resolve event-render display labels."""

    def get_location_by_id(self, location_id: str) -> Any: ...

    def location_name(self, location_id: str) -> str: ...


def _translator_for_locale(locale: Optional[str]) -> Translator:
    if locale is None:
        return lambda key, **kwargs: tr_for_locale(get_locale(), key, **kwargs)
    return lambda key, **kwargs: tr_for_locale(locale, key, **kwargs)


def _location_display_name(location_id: Any, world: EventRenderContext | None = None) -> Optional[str]:
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


def _faction_display_name(faction_id: str, world: EventRenderContext | None = None) -> Optional[str]:
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


def _display_faction(value: Any, *, world: EventRenderContext | None = None, translate: Translator) -> str:
    if value is None or value == "":
        return translate("event_change_no_faction")
    faction_id = str(value)
    return _faction_display_name(faction_id, world) or faction_id


def _display_biome(value: Any, *, translate: Translator) -> str:
    biome_id = str(value)
    key = f"terrain_biome_{biome_id}"
    rendered = translate(key)
    return biome_id if rendered == key else rendered


def _terrain_change_summary(params: dict[str, Any], *, translate: Translator) -> str:
    parts: list[str] = []
    if params.get("old_biome") != params.get("new_biome"):
        parts.append(
            translate(
                "event_terrain_change_biome",
                old_biome=params.get("old_biome", ""),
                new_biome=params.get("new_biome", ""),
            )
        )
    if params.get("old_elevation") != params.get("new_elevation"):
        parts.append(
            translate(
                "event_terrain_change_elevation",
                old_elevation=params.get("old_elevation", ""),
                new_elevation=params.get("new_elevation", ""),
            )
        )
    if params.get("old_moisture") != params.get("new_moisture"):
        parts.append(
            translate(
                "event_terrain_change_moisture",
                old_moisture=params.get("old_moisture", ""),
                new_moisture=params.get("new_moisture", ""),
            )
        )
    if params.get("old_temperature") != params.get("new_temperature"):
        parts.append(
            translate(
                "event_terrain_change_temperature",
                old_temperature=params.get("old_temperature", ""),
                new_temperature=params.get("new_temperature", ""),
            )
        )
    if not parts:
        return translate("event_terrain_change_noop")
    return translate("event_terrain_change_separator").join(parts)


def _render_params(
    record: WorldEventRecord,
    *,
    world: EventRenderContext | None = None,
    translate: Translator,
) -> dict[str, Any]:
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
    if record.summary_key == "events.terrain_cell_mutated.summary":
        if "old_biome" in params:
            params["old_biome"] = _display_biome(params["old_biome"], translate=translate)
        if "new_biome" in params:
            params["new_biome"] = _display_biome(params["new_biome"], translate=translate)
        if "change_summary" not in params:
            params["change_summary"] = _terrain_change_summary(params, translate=translate)
    if record.summary_key == "events.battle_result.summary" and "injury" not in params:
        injury_status = params.get("loser_injury_status")
        loser = params.get("loser")
        if isinstance(injury_status, str) and injury_status != "none" and isinstance(loser, str):
            params["injury"] = " " + translate(f"battle_injury_{injury_status}", name=loser)
        else:
            params["injury"] = ""
    return params


def render_event_record(
    record: WorldEventRecord,
    locale: Optional[str] = None,
    world: EventRenderContext | None = None,
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

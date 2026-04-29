"""Locale-aware rendering helpers for canonical world event records."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Optional

from .event_models import WorldEventRecord
from .i18n import get_locale, set_locale, tr


def _display_faction(value: Any) -> str:
    if value is None or value == "":
        return tr("event_change_no_faction")
    return str(value)


def _render_params_for_locale(record: WorldEventRecord) -> dict[str, Any]:
    params = deepcopy(record.render_params)
    if record.summary_key == "events.location_faction_changed.summary":
        if "old_faction_id" in params:
            params["old_faction"] = _display_faction(params["old_faction_id"])
        if "new_faction_id" in params:
            params["new_faction"] = _display_faction(params["new_faction_id"])
    return params


def render_event_record(
    record: WorldEventRecord,
    locale: Optional[str] = None,
    world: object = None,
) -> str:
    """Render a world event record summary for display.

    ``world`` is accepted for future context-aware rendering, but this helper
    currently only uses stable data persisted on the record itself.
    """
    _ = world
    if not record.summary_key:
        return record.description

    previous_locale = get_locale()
    if locale is not None:
        set_locale(locale)
    try:
        rendered = tr(record.summary_key, **_render_params_for_locale(record))
    except (KeyError, IndexError, TypeError, ValueError):
        return record.description
    finally:
        if locale is not None:
            set_locale(previous_locale)

    if rendered == record.summary_key:
        return record.description
    return rendered

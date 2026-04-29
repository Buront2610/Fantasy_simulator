"""Locale-aware rendering helpers for canonical world event records."""

from __future__ import annotations

from typing import Optional

from .event_models import WorldEventRecord
from .i18n import get_locale, set_locale, tr


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
        rendered = tr(record.summary_key, **record.render_params)
    except (KeyError, IndexError, TypeError, ValueError):
        return record.description
    finally:
        if locale is not None:
            set_locale(previous_locale)

    if rendered == record.summary_key:
        return record.description
    return rendered

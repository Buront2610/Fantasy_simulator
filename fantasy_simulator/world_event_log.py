"""Compatibility event-log projection helpers.

This module isolates formatting/projection logic from ``World`` so that
stateful world orchestration and compatibility rendering are separated.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional

from .event_models import WorldEventRecord

Translator = Callable[..., str]


def format_event_log_entry(
    event_text: str,
    *,
    translate: Translator,
    year: int,
    month: Optional[int] = None,
    day: Optional[int] = None,
) -> str:
    """Format one compatibility event-log line.

    Contract:
    - ``year`` must be an ``int``.
    - If ``day`` is specified without ``month``, the value is ignored for compatibility.
    """
    if month is not None and day is not None:
        prefix = translate("event_log_prefix_day", year=year, month=month, day=day)
    elif month is not None:
        prefix = translate("event_log_prefix_month", year=year, month=month)
    else:
        prefix = translate("event_log_prefix", year=year)
    return f"{prefix} {event_text}"


def project_compatibility_event_log(
    records: Iterable[WorldEventRecord],
    *,
    max_event_log: int,
    translate: Translator,
) -> List[str]:
    """Project compatibility log lines from canonical records."""
    recent = list(records)[-max_event_log:]
    return [
        record.legacy_event_log_entry
        if record.legacy_event_log_entry is not None
        else format_event_log_entry(
            record.description,
            translate=translate,
            year=record.year,
            month=record.month,
            day=record.day,
        )
        for record in recent
    ]

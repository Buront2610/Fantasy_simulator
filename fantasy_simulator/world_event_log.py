"""Compatibility event-log projection helpers.

This module isolates formatting/projection logic from ``World`` so that
stateful world orchestration and compatibility rendering are separated.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional

from .event_models import WorldEventRecord

Translator = Callable[..., str]


class ReadOnlyEventLog(list[str]):
    """List-like read-only view for compatibility event-log access."""

    def _readonly(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("event_log is a read-only view; use log_event() or record_event()")

    append = _readonly
    clear = _readonly
    extend = _readonly
    insert = _readonly
    pop = _readonly
    remove = _readonly
    reverse = _readonly
    sort = _readonly

    def __delitem__(self, _index: Any) -> None:
        self._readonly()

    def __iadd__(self, _other: Any) -> "ReadOnlyEventLog":
        self._readonly()
        return self

    def __imul__(self, _other: Any) -> "ReadOnlyEventLog":
        self._readonly()
        return self

    def __setitem__(self, _index: Any, _value: Any) -> None:
        self._readonly()


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


def trim_event_log_entries(entries: Iterable[str], *, max_event_log: int) -> List[str]:
    """Return at most the newest ``max_event_log`` display entries."""
    return list(entries)[-max_event_log:]


def append_display_event_log_entry(
    entries: Iterable[str],
    event_text: str,
    *,
    translate: Translator,
    year: int,
    max_event_log: int,
    month: Optional[int] = None,
    day: Optional[int] = None,
) -> List[str]:
    """Append one display-only compatibility line and trim the buffer."""
    updated = list(entries)
    updated.append(
        format_event_log_entry(
            event_text,
            translate=translate,
            year=year,
            month=month,
            day=day,
        )
    )
    return trim_event_log_entries(updated, max_event_log=max_event_log)


def rebuild_display_event_log(
    entries: Iterable[str],
    records: Iterable[WorldEventRecord],
    *,
    max_event_log: int,
) -> List[str]:
    """Drop stale display-only lines once canonical history exists."""
    if list(records):
        return []
    return trim_event_log_entries(entries, max_event_log=max_event_log)


def compatibility_event_log_view(
    display_entries: Iterable[str],
    records: Iterable[WorldEventRecord],
    *,
    max_event_log: int,
    translate: Translator,
) -> ReadOnlyEventLog:
    """Return the current read-only compatibility log view."""
    canonical_records = list(records)
    if canonical_records:
        return ReadOnlyEventLog(
            project_compatibility_event_log(
                canonical_records,
                max_event_log=max_event_log,
                translate=translate,
            )
        )
    return ReadOnlyEventLog(trim_event_log_entries(display_entries, max_event_log=max_event_log))

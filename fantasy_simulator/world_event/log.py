"""Event-log projection helpers.

This module isolates formatting/projection logic from ``World`` so that
stateful world orchestration and event rendering are separated.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Callable, Iterable, Iterator, List, Optional, overload

from .models import WorldEventRecord
from .rendering import EventRenderContext, render_event_record

Translator = Callable[..., str]


class ReadOnlyEventLog(Sequence[str]):
    """List-like read-only view for projected event-log access."""

    def __init__(self, entries: Iterable[str]) -> None:
        self._entries = tuple(entries)

    @overload
    def __getitem__(self, index: int) -> str: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[str, ...]: ...

    def __getitem__(self, index: int | slice) -> str | tuple[str, ...]:
        return self._entries[index]

    def __iter__(self) -> Iterator[str]:
        return iter(self._entries)

    def __len__(self) -> int:
        return len(self._entries)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ReadOnlyEventLog):
            return self._entries == other._entries
        if isinstance(other, (list, tuple)):
            return list(self._entries) == list(other)
        return NotImplemented

    def __repr__(self) -> str:
        return repr(list(self._entries))

    def _readonly(self, *_args: Any, **_kwargs: Any) -> None:
        raise TypeError("event_log is a read-only view; use record_event()")

    def append(self, _value: str) -> None:
        self._readonly()

    def clear(self) -> None:
        self._readonly()

    def extend(self, _values: Iterable[str]) -> None:
        self._readonly()

    def insert(self, _index: int, _value: str) -> None:
        self._readonly()

    def pop(self, _index: int = -1) -> str:
        self._readonly()
        raise AssertionError("unreachable")

    def remove(self, _value: str) -> None:
        self._readonly()

    def reverse(self) -> None:
        self._readonly()

    def sort(self, *_args: Any, **_kwargs: Any) -> None:
        self._readonly()


def format_event_log_entry(
    event_text: str,
    *,
    translate: Translator,
    year: int,
    month: Optional[int] = None,
    day: Optional[int] = None,
) -> str:
    """Format one projected event-log line.

    Contract:
    - ``year`` must be an ``int``.
    - If ``day`` is specified without ``month``, the value is ignored.
    """
    if month is not None and day is not None:
        prefix = translate("event_log_prefix_day", year=year, month=month, day=day)
    elif month is not None:
        prefix = translate("event_log_prefix_month", year=year, month=month)
    else:
        prefix = translate("event_log_prefix", year=year)
    return f"{prefix} {event_text}"


def project_event_log_lines(
    records: Iterable[WorldEventRecord],
    *,
    max_event_log: int,
    translate: Translator,
    world: EventRenderContext | None = None,
) -> List[str]:
    """Project log lines from canonical records."""
    if max_event_log <= 0:
        return []
    recent = list(records)[-max_event_log:]
    return [
        format_event_log_entry(
            render_event_record(record, world=world, translate=translate),
            translate=translate,
            year=record.year,
            month=record.month,
            day=record.day,
        )
        for record in recent
    ]


def event_log_view(
    records: Iterable[WorldEventRecord],
    *,
    max_event_log: int,
    translate: Translator,
    world: EventRenderContext | None = None,
) -> ReadOnlyEventLog:
    """Return the current read-only event log view."""
    return ReadOnlyEventLog(
        project_event_log_lines(
            records,
            max_event_log=max_event_log,
            translate=translate,
            world=world,
        )
    )

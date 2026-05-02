"""Facade helpers for compatibility event-log methods exposed by ``World``."""

from __future__ import annotations

from typing import Iterable, List, Optional, cast

from .i18n import tr
from .world_protocols import MutableEventLogWorld
from .world_event_log import (
    EventRenderContext,
    ReadOnlyEventLog,
    append_display_event_log_entry,
    compatibility_event_log_view,
    rebuild_display_event_log,
    trim_event_log_entries,
)


def event_log_view(world: MutableEventLogWorld) -> ReadOnlyEventLog:
    """Return the current read-only compatibility event-log view."""
    return compatibility_event_log_view(
        world._display_event_log,
        world.event_records,
        max_event_log=world.MAX_EVENT_LOG,
        translate=tr,
        world=cast(EventRenderContext, world),
    )


def set_event_log_entries(world: MutableEventLogWorld, value: Iterable[str]) -> None:
    """Replace display-only event-log entries, preserving the trimming contract."""
    if world.event_records:
        raise RuntimeError(
            "event_log assignment cannot replace display-only lines after canonical event_records exist"
        )
    world._display_event_log = trim_event_log_entries(value, max_event_log=world.MAX_EVENT_LOG)


def restore_display_event_log_for_load(world: MutableEventLogWorld, value: Iterable[str]) -> None:
    """Restore legacy display-only event-log entries during save hydration."""
    world._display_event_log = trim_event_log_entries(value, max_event_log=world.MAX_EVENT_LOG)


def append_event_log_entry(
    world: MutableEventLogWorld,
    event_text: str,
    *,
    month: Optional[int] = None,
    day: Optional[int] = None,
) -> None:
    """Append one display-only compatibility event-log entry."""
    if world.event_records:
        raise RuntimeError("log_event() cannot append display-only lines after canonical event_records exist")
    world._display_event_log = append_display_event_log_entry(
        world._display_event_log,
        event_text,
        translate=tr,
        year=world.year,
        max_event_log=world.MAX_EVENT_LOG,
        month=month,
        day=day,
    )


def rebuild_compatibility_event_log(world: MutableEventLogWorld) -> None:
    """Drop stale display-only lines once canonical history exists."""
    world._display_event_log = rebuild_display_event_log(
        world._display_event_log,
        world.event_records,
        max_event_log=world.MAX_EVENT_LOG,
    )


def compatibility_event_log(world: MutableEventLogWorld, *, last_n: Optional[int] = None) -> List[str]:
    """Return the legacy event-log adapter, projecting from records if needed."""
    log = list(event_log_view(world))
    if last_n is not None:
        return log[-last_n:]
    return list(log)


def clear_display_event_log(world: MutableEventLogWorld) -> None:
    """Clear display-only compatibility lines after canonical history changes."""
    world._display_event_log = []

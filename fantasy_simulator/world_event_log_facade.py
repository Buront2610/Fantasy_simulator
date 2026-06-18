"""Facade helpers for event-log methods exposed by ``World``."""

from __future__ import annotations

from typing import List, Optional, cast

from .i18n import tr
from .world_protocols import MutableEventLogWorld
from .world_event_log import (
    EventRenderContext,
    ReadOnlyEventLog,
    event_log_view as projected_event_log_view,
)


def event_log_view(world: MutableEventLogWorld) -> ReadOnlyEventLog:
    """Return the current read-only event-log view."""
    return projected_event_log_view(
        world.event_records,
        max_event_log=world.MAX_EVENT_LOG,
        translate=tr,
        world=cast(EventRenderContext, world),
    )


def event_log_lines(world: MutableEventLogWorld, *, last_n: Optional[int] = None) -> List[str]:
    """Return projected event-log lines from canonical records."""
    log = list(event_log_view(world))
    if last_n is not None:
        return log[-last_n:]
    return list(log)

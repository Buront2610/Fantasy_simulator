"""Event-log API methods mixed into ``World``."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from . import log_facade as event_log_facade

if TYPE_CHECKING:
    from ..event_models import WorldEventRecord


class WorldEventLogMixin:
    """Read-only event-log API projected from canonical records."""

    MAX_EVENT_LOG = 2000

    if TYPE_CHECKING:
        year: int
        event_records: Sequence[WorldEventRecord]

    @property
    def event_log(self) -> Sequence[str]:
        """Read-only event log projected from canonical ``event_records``."""
        return event_log_facade.event_log_view(self)

"""Event-log API methods mixed into ``World``."""

from __future__ import annotations

from typing import List, Optional

from . import world_event_log_facade as event_log_facade


class WorldEventLogMixin:
    """Compatibility API surface for display-only event log helpers."""

    MAX_EVENT_LOG = 2000

    @property
    def event_log(self) -> List[str]:
        """Compatibility event log view.

        Once canonical ``event_records`` exist, the compatibility log is
        projected on demand so we do not retain a second long-lived copy of the
        same history in memory. The returned value is a read-only view so direct
        list mutation cannot silently diverge from canonical history.
        """
        return event_log_facade.event_log_view(self)

    @event_log.setter
    def event_log(self, value: List[str]) -> None:
        event_log_facade.set_event_log_entries(self, value)

    def log_event(
        self,
        event_text: str,
        *,
        month: Optional[int] = None,
        day: Optional[int] = None,
    ) -> None:
        """Append a formatted compatibility display line for legacy CLI consumers.

        Contract (important):
        - This is a display-only runtime adapter and does **not** create
          canonical ``event_records`` entries.
        - New saves persist canonical ``event_records`` only.
        - Therefore, callers must use ``record_event()`` for durable history.

        When *month*/*day* are provided, the prefix includes intra-year date
        information so that the player-visible log reflects finer causality.
        """
        event_log_facade.append_event_log_entry(
            self,
            event_text,
            month=month,
            day=day,
        )

    def rebuild_compatibility_event_log(self) -> None:
        """Drop stale display-only lines when canonical history exists."""
        event_log_facade.rebuild_compatibility_event_log(self)

    def get_compatibility_event_log(self, last_n: Optional[int] = None) -> List[str]:
        """Return the legacy event-log adapter, projecting from records if needed."""
        return event_log_facade.compatibility_event_log(self, last_n=last_n)

"""Structured event-history API methods mixed into ``World``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from . import world_event_log_facade as event_log_facade
from .event_models import WorldEventRecord
from .world_event_history import (
    latest_absolute_day_before_or_on as latest_event_absolute_day_before_or_on,
    record_world_event,
)
from .world_event_queries import (
    events_by_actor,
    events_by_kind,
    events_by_location,
    events_by_month,
    events_by_year,
)
from .world_event_state import apply_event_impact_to_location
from .world_location_state import clamp_state as _clamp_state

if TYPE_CHECKING:
    from .character import Character
    from .world_event_index import EventHistoryIndex
    from .world_location_state import LocationState


class WorldEventMixin:
    """Compatibility API surface for structured world events."""

    MAX_EVENT_LOG = 2000
    MAX_EVENT_RECORDS = 5000
    WATCHED_ACTOR_TAG_PREFIX: str

    if TYPE_CHECKING:
        event_records: List[WorldEventRecord]
        year: int
        _display_event_log: List[str]
        _event_index: EventHistoryIndex
        _location_id_index: Dict[str, LocationState]
        grid: Dict[Tuple[int, int], LocationState]
        event_impact_rules: Dict[str, Dict[str, int]]

        def get_character_by_id(self, char_id: str) -> Optional[Character]: ...

    def latest_absolute_day_before_or_on(self, year: int, month: int) -> int:
        """Return the latest known absolute day on or before a given report period."""
        return latest_event_absolute_day_before_or_on(self.event_records, year=year, month=month)

    def record_event(self, record: WorldEventRecord) -> WorldEventRecord:
        """Store a structured event record in the canonical world history.

        Returns the canonical stored record (may be a normalized copy).
        """
        record = WorldEventRecord.from_dict(record.to_dict())
        stored_record = record_world_event(
            record=record,
            event_records=self.event_records,
            event_index=self._event_index,
            location_index=self._location_id_index,
            grid=self.grid,
            max_event_records=self.MAX_EVENT_RECORDS,
            get_character_by_id=self.get_character_by_id,
            watched_actor_tag_prefix=self.WATCHED_ACTOR_TAG_PREFIX,
        )
        event_log_facade.clear_display_event_log(self)
        return stored_record

    def apply_event_impact(self, kind: str, location_id: Optional[str]) -> List[Dict[str, Any]]:
        """Update location state quantities based on an event kind (design §5.5).

        Returns a list of impact dicts recording the state changes applied,
        each containing ``target_type``, ``target_id``, ``attribute``,
        ``old_value``, ``new_value``, and ``delta``.
        """
        return apply_event_impact_to_location(
            kind=kind,
            location_id=location_id,
            location_index=self._location_id_index,
            clamp_state=_clamp_state,
            impact_rules=self.event_impact_rules,
        )

    def get_events_by_location(self, location_id: str) -> List[WorldEventRecord]:
        """Return all event records for a specific location."""
        return events_by_location(self._event_index, self.event_records, location_id)

    def get_events_by_actor(self, char_id: str) -> List[WorldEventRecord]:
        """Return all event records involving a specific character."""
        return events_by_actor(self._event_index, self.event_records, char_id)

    def get_events_by_year(self, year: int) -> List[WorldEventRecord]:
        """Return all event records for a specific year."""
        return events_by_year(self._event_index, self.event_records, year)

    def get_events_by_month(self, year: int, month: int) -> List[WorldEventRecord]:
        """Return all event records for a specific in-world month."""
        return events_by_month(self._event_index, self.event_records, year, month)

    def get_events_by_kind(self, kind: str) -> List[WorldEventRecord]:
        """Return all event records for a specific canonical event kind."""
        return events_by_kind(self._event_index, self.event_records, kind)

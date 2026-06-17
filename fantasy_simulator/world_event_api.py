"""Structured event-history API methods mixed into ``World``."""

from __future__ import annotations

from collections.abc import MutableMapping as MutableMappingABC
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from . import world_event_log_facade as event_log_facade
from .event_models import WorldEventRecord
from .world_event_history import (
    latest_absolute_day_before_or_on as latest_event_absolute_day_before_or_on,
    record_world_event,
)
from .world_event_queries import (
    event_causes,
    event_by_id,
    events_caused_by,
    events_by_actor,
    events_by_kind,
    events_by_location,
    events_by_month,
    events_by_year,
)
from .world_event_state import apply_event_impact_to_location
from .world_event_record_updates import event_record_with_semantic_render_params
from .world_location_state import clamp_state as _clamp_state

if TYPE_CHECKING:
    from .character import Character
    from .world_event_index import EventHistoryIndex
    from .world_location_state import LocationState


@dataclass(frozen=True)
class WorldEventRecorderSnapshot:
    """Snapshot of mutable event-history state used by transactional application services."""

    event_records: List[WorldEventRecord]
    recent_event_ids: Tuple[Tuple[Any, List[str]], ...]
    display_event_log: List[str] | None
    event_index_state: Dict[str, Any] | None


class WorldEventRecorderPort:
    """Explicit event recorder port for atomic world-change reducers."""

    def __init__(self, owner: Any) -> None:
        self._owner = owner

    def record(self, record: WorldEventRecord) -> WorldEventRecord:
        return self._owner.record_event(record)

    def snapshot(self) -> WorldEventRecorderSnapshot:
        locations_by_identity: Dict[int, Any] = {}
        for source_name in ("_location_id_index", "grid"):
            source = getattr(self._owner, source_name, None)
            if not isinstance(source, MutableMappingABC):
                continue
            for location in source.values():
                if hasattr(location, "recent_event_ids"):
                    locations_by_identity[id(location)] = location

        display_event_log = getattr(self._owner, "_display_event_log", None)
        event_index = getattr(self._owner, "_event_index", None)
        event_index_state = None
        if event_index is not None:
            event_index_state = {
                "signature": getattr(event_index, "signature", ()),
                "record_ids": set(getattr(event_index, "record_ids", set())),
                "by_id": dict(getattr(event_index, "by_id", {})),
                "by_location": {
                    key: list(value) for key, value in getattr(event_index, "by_location", {}).items()
                },
                "by_actor": {
                    key: list(value) for key, value in getattr(event_index, "by_actor", {}).items()
                },
                "by_year": {
                    key: list(value) for key, value in getattr(event_index, "by_year", {}).items()
                },
                "by_month": {
                    key: list(value) for key, value in getattr(event_index, "by_month", {}).items()
                },
                "by_kind": {
                    key: list(value) for key, value in getattr(event_index, "by_kind", {}).items()
                },
            }

        return WorldEventRecorderSnapshot(
            event_records=list(self._owner.event_records),
            recent_event_ids=tuple(
                (location, list(location.recent_event_ids))
                for location in locations_by_identity.values()
            ),
            display_event_log=None if not isinstance(display_event_log, list) else list(display_event_log),
            event_index_state=event_index_state,
        )

    def restore(self, snapshot: WorldEventRecorderSnapshot) -> None:
        self._owner.event_records[:] = snapshot.event_records

        for location, recent_event_ids in snapshot.recent_event_ids:
            location.recent_event_ids = list(recent_event_ids)

        if snapshot.display_event_log is not None:
            display_event_log = getattr(self._owner, "_display_event_log", None)
            if isinstance(display_event_log, list):
                display_event_log[:] = snapshot.display_event_log
            else:
                self._owner._display_event_log = list(snapshot.display_event_log)

        event_index = getattr(self._owner, "_event_index", None)
        if event_index is None or snapshot.event_index_state is None:
            if event_index is not None and hasattr(event_index, "invalidate"):
                event_index.invalidate()
            return
        event_index.signature = snapshot.event_index_state["signature"]
        event_index.record_ids = set(snapshot.event_index_state["record_ids"])
        event_index.by_id = dict(snapshot.event_index_state.get("by_id", {}))
        event_index.by_location = {
            key: list(value) for key, value in snapshot.event_index_state["by_location"].items()
        }
        event_index.by_actor = {
            key: list(value) for key, value in snapshot.event_index_state["by_actor"].items()
        }
        event_index.by_year = {
            key: list(value) for key, value in snapshot.event_index_state["by_year"].items()
        }
        event_index.by_month = {
            key: list(value) for key, value in snapshot.event_index_state["by_month"].items()
        }
        event_index.by_kind = {
            key: list(value) for key, value in snapshot.event_index_state["by_kind"].items()
        }


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
        record = event_record_with_semantic_render_params(WorldEventRecord.from_dict(record.to_dict()))
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

    def world_change_event_recorder(self) -> WorldEventRecorderPort:
        """Return an explicit transactional recorder port for world-change reducers."""
        return WorldEventRecorderPort(self)

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

    def get_event_by_id(self, record_id: str) -> WorldEventRecord | None:
        """Return one event record by canonical record id."""
        return event_by_id(self._event_index, self.event_records, record_id)

    def get_event_causes(self, record_id: str) -> List[WorldEventRecord]:
        """Return direct cause records for a canonical event."""
        return event_causes(self._event_index, self.event_records, record_id)

    def get_events_caused_by(self, cause_event_id: str) -> List[WorldEventRecord]:
        """Return direct effect records citing a canonical event id."""
        return events_caused_by(self.event_records, cause_event_id)

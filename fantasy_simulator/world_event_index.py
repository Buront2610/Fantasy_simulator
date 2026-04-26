"""Derived indexes for canonical world event records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

from .event_models import WorldEventRecord


def _event_signature(records: List[WorldEventRecord]) -> Tuple[Any, ...]:
    """Return a mutation-sensitive signature for direct compatibility edits."""
    return tuple(
        (
            record.record_id,
            record.kind,
            record.year,
            record.month,
            record.location_id or "",
            record.primary_actor_id or "",
            tuple(record.secondary_actor_ids),
        )
        for record in records
    )


@dataclass
class EventHistoryIndex:
    """Non-persistent lookup tables derived from ``World.event_records``."""

    signature: Tuple[Any, ...] = ()
    record_ids: Set[str] = field(default_factory=set)
    by_location: Dict[str, List[WorldEventRecord]] = field(default_factory=dict)
    by_actor: Dict[str, List[WorldEventRecord]] = field(default_factory=dict)
    by_year: Dict[int, List[WorldEventRecord]] = field(default_factory=dict)
    by_month: Dict[Tuple[int, int], List[WorldEventRecord]] = field(default_factory=dict)
    by_kind: Dict[str, List[WorldEventRecord]] = field(default_factory=dict)

    def invalidate(self) -> None:
        self.signature = ()

    def ensure_current(self, records: List[WorldEventRecord]) -> None:
        signature = _event_signature(records)
        if signature == self.signature:
            return

        by_location: Dict[str, List[WorldEventRecord]] = {}
        by_actor: Dict[str, List[WorldEventRecord]] = {}
        by_year: Dict[int, List[WorldEventRecord]] = {}
        by_month: Dict[Tuple[int, int], List[WorldEventRecord]] = {}
        by_kind: Dict[str, List[WorldEventRecord]] = {}
        record_ids: Set[str] = set()

        for record in records:
            record_ids.add(record.record_id)
            if record.location_id:
                by_location.setdefault(record.location_id, []).append(record)
            indexed_actor_ids: Set[str] = set()
            if record.primary_actor_id:
                by_actor.setdefault(record.primary_actor_id, []).append(record)
                indexed_actor_ids.add(record.primary_actor_id)
            for actor_id in record.secondary_actor_ids:
                if actor_id in indexed_actor_ids:
                    continue
                by_actor.setdefault(actor_id, []).append(record)
                indexed_actor_ids.add(actor_id)
            by_year.setdefault(record.year, []).append(record)
            by_month.setdefault((record.year, record.month), []).append(record)
            by_kind.setdefault(record.kind, []).append(record)

        self.record_ids = record_ids
        self.by_location = by_location
        self.by_actor = by_actor
        self.by_year = by_year
        self.by_month = by_month
        self.by_kind = by_kind
        self.signature = signature

    def by_location_id(self, records: List[WorldEventRecord], location_id: str) -> List[WorldEventRecord]:
        self.ensure_current(records)
        return list(self.by_location.get(location_id, []))

    def by_actor_id(self, records: List[WorldEventRecord], actor_id: str) -> List[WorldEventRecord]:
        self.ensure_current(records)
        return list(self.by_actor.get(actor_id, []))

    def by_year_value(self, records: List[WorldEventRecord], year: int) -> List[WorldEventRecord]:
        self.ensure_current(records)
        return list(self.by_year.get(year, []))

    def by_month_value(self, records: List[WorldEventRecord], year: int, month: int) -> List[WorldEventRecord]:
        self.ensure_current(records)
        return list(self.by_month.get((year, month), []))

    def by_kind_value(self, records: List[WorldEventRecord], kind: str) -> List[WorldEventRecord]:
        self.ensure_current(records)
        return list(self.by_kind.get(kind, []))

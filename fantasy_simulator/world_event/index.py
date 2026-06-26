"""Derived indexes for canonical world event records."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

from .models import LOCATION_TAG_PREFIX, WorldEventRecord


def _freeze_payload(value: Any) -> Any:
    """Return a hashable representation of JSON-like record metadata."""
    if isinstance(value, dict):
        return tuple((key, _freeze_payload(item)) for key, item in sorted(value.items(), key=lambda pair: str(pair[0])))
    if isinstance(value, list):
        return tuple(_freeze_payload(item) for item in value)
    return value


def location_ids_for_record(record: WorldEventRecord) -> List[str]:
    """Return all location ids directly attached to a record."""
    location_ids: List[str] = []

    def add_location_id(value: Any) -> None:
        if isinstance(value, str) and value and value not in location_ids:
            location_ids.append(value)

    add_location_id(record.location_id)
    for tag in record.tags:
        if tag.startswith(LOCATION_TAG_PREFIX):
            add_location_id(tag[len(LOCATION_TAG_PREFIX):])

    for key in ("location_id", "from_location_id", "to_location_id"):
        add_location_id(record.render_params.get(key))

    endpoint_location_ids = record.render_params.get("endpoint_location_ids")
    if isinstance(endpoint_location_ids, list):
        for location_id in endpoint_location_ids:
            add_location_id(location_id)

    for impact in record.impacts:
        if impact.get("target_type") == "location":
            add_location_id(impact.get("target_id"))

    return location_ids


def _event_signature(records: List[WorldEventRecord]) -> Tuple[Any, ...]:
    """Return a mutation-sensitive signature for direct compatibility edits."""
    return tuple(_record_signature(record) for record in records)


def _record_signature(record: WorldEventRecord) -> Tuple[Any, ...]:
    return (
        record.record_id,
        record.kind,
        record.year,
        record.month,
        record.location_id or "",
        record.primary_actor_id or "",
        tuple(record.secondary_actor_ids),
        tuple(record.tags),
        _freeze_payload(record.render_params),
        _freeze_payload(record.impacts),
    )


def _pruned_record_lists(
    records_by_key: Dict[Any, List[WorldEventRecord]],
    surviving_ids: Set[str],
) -> Dict[Any, List[WorldEventRecord]]:
    return {
        key: surviving_records
        for key, records in records_by_key.items()
        for surviving_records in [[record for record in records if record.record_id in surviving_ids]]
        if surviving_records
    }


@dataclass
class EventHistoryIndex:
    """Non-persistent lookup tables derived from ``World.event_records``."""

    signature: Tuple[Any, ...] = ()
    record_ids: Set[str] = field(default_factory=set)
    by_id: Dict[str, WorldEventRecord] = field(default_factory=dict)
    by_location: Dict[str, List[WorldEventRecord]] = field(default_factory=dict)
    by_actor: Dict[str, List[WorldEventRecord]] = field(default_factory=dict)
    by_year: Dict[int, List[WorldEventRecord]] = field(default_factory=dict)
    by_month: Dict[Tuple[int, int], List[WorldEventRecord]] = field(default_factory=dict)
    by_kind: Dict[str, List[WorldEventRecord]] = field(default_factory=dict)

    def invalidate(self) -> None:
        self.signature = ()

    def ensure_record_ids_current(self, records: List[WorldEventRecord]) -> None:
        """Keep only the duplicate-detection set current for canonical writes.

        Canonical append needs existing record IDs before it mutates the event
        store.  It does not need the heavier location/actor/year/kind lookup
        tables; those remain a read-side concern and are rebuilt by
        ``ensure_current`` when queried.
        """
        if len(self.record_ids) == len(records) and not self.signature:
            return
        record_ids = {record.record_id for record in records}
        if record_ids == self.record_ids:
            return
        self.record_ids = record_ids
        self.invalidate()

    def ensure_current(self, records: List[WorldEventRecord]) -> None:
        signature = _event_signature(records)
        if signature == self.signature:
            return

        by_location: Dict[str, List[WorldEventRecord]] = {}
        by_actor: Dict[str, List[WorldEventRecord]] = {}
        by_year: Dict[int, List[WorldEventRecord]] = {}
        by_month: Dict[Tuple[int, int], List[WorldEventRecord]] = {}
        by_kind: Dict[str, List[WorldEventRecord]] = {}
        by_id: Dict[str, WorldEventRecord] = {}
        record_ids: Set[str] = set()

        for record in records:
            record_ids.add(record.record_id)
            by_id[record.record_id] = record
            for location_id in location_ids_for_record(record):
                by_location.setdefault(location_id, []).append(record)
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
        self.by_id = by_id
        self.by_location = by_location
        self.by_actor = by_actor
        self.by_year = by_year
        self.by_month = by_month
        self.by_kind = by_kind
        self.signature = signature

    def append_current(self, records: List[WorldEventRecord], record: WorldEventRecord) -> None:
        """Update an already-current index after a canonical append."""
        if record not in records:
            self.invalidate()
            return
        if len(self.signature) + 1 == len(records):
            self._add_record(record)
            self.signature = (*self.signature, _record_signature(record))
            return

        self._add_record(record)
        self._prune_to_surviving_records(records)
        self.signature = _event_signature(records)

    def _add_record(self, record: WorldEventRecord) -> None:
        self.record_ids.add(record.record_id)
        self.by_id[record.record_id] = record
        for location_id in location_ids_for_record(record):
            self.by_location.setdefault(location_id, []).append(record)
        indexed_actor_ids: Set[str] = set()
        if record.primary_actor_id:
            self.by_actor.setdefault(record.primary_actor_id, []).append(record)
            indexed_actor_ids.add(record.primary_actor_id)
        for actor_id in record.secondary_actor_ids:
            if actor_id in indexed_actor_ids:
                continue
            self.by_actor.setdefault(actor_id, []).append(record)
            indexed_actor_ids.add(actor_id)
        self.by_year.setdefault(record.year, []).append(record)
        self.by_month.setdefault((record.year, record.month), []).append(record)
        self.by_kind.setdefault(record.kind, []).append(record)

    def _prune_to_surviving_records(self, records: List[WorldEventRecord]) -> None:
        surviving_ids = {record.record_id for record in records}
        self.record_ids.intersection_update(surviving_ids)
        self.by_id = {
            record_id: record
            for record_id, record in self.by_id.items()
            if record_id in surviving_ids
        }
        self.by_location = _pruned_record_lists(self.by_location, surviving_ids)
        self.by_actor = _pruned_record_lists(self.by_actor, surviving_ids)
        self.by_year = _pruned_record_lists(self.by_year, surviving_ids)
        self.by_month = _pruned_record_lists(self.by_month, surviving_ids)
        self.by_kind = _pruned_record_lists(self.by_kind, surviving_ids)

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

    def by_record_id(self, records: List[WorldEventRecord], record_id: str) -> WorldEventRecord | None:
        self.ensure_current(records)
        return self.by_id.get(record_id)

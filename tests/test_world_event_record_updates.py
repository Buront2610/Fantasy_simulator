"""Copy-normalization helpers for world event records."""

from __future__ import annotations

from dataclasses import dataclass, field

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.world_event_record_updates import (
    event_record_with_added_tags,
    event_record_with_location_id,
    normalize_event_record_locations,
)
from fantasy_simulator.world_load_normalizer import rebuild_recent_event_ids


@dataclass
class _Location:
    recent_event_ids: list[str] = field(default_factory=list)


def test_event_record_with_location_id_returns_copy() -> None:
    record = WorldEventRecord(
        record_id="evt_1",
        location_id="legacy_capital",
        tags=["important"],
    )

    updated = event_record_with_location_id(record, "loc_aethoria_capital")

    assert updated is not record
    assert record.location_id == "legacy_capital"
    assert updated.location_id == "loc_aethoria_capital"
    assert updated.tags == ["important"]


def test_normalize_event_record_locations_returns_copied_records() -> None:
    records = [
        WorldEventRecord(record_id="evt_1", location_id="legacy_capital"),
        WorldEventRecord(record_id="evt_2", location_id=None),
    ]

    normalized = normalize_event_record_locations(
        records,
        lambda location_id: {"legacy_capital": "loc_aethoria_capital"}.get(location_id, location_id),
    )

    assert [record.location_id for record in records] == ["legacy_capital", None]
    assert [record.location_id for record in normalized] == ["loc_aethoria_capital", None]
    assert all(updated is not original for updated, original in zip(normalized, records))


def test_event_record_with_added_tags_returns_copy_with_unique_tags() -> None:
    record = WorldEventRecord(record_id="evt_1", tags=["existing"])

    updated = event_record_with_added_tags(record, ["watched:char_1", "existing"])

    assert updated is not record
    assert record.tags == ["existing"]
    assert updated.tags == ["existing", "watched:char_1"]


def test_rebuild_recent_event_ids_clears_invalid_locations_by_replacing_records() -> None:
    locations = [_Location()]
    event_records = [
        WorldEventRecord(record_id="evt_valid", location_id="loc_known"),
        WorldEventRecord(record_id="evt_stale", location_id="loc_missing"),
    ]
    stale_record = event_records[1]

    rebuild_recent_event_ids(
        locations=locations,
        location_index={"loc_known": locations[0]},
        event_records=event_records,
    )

    assert locations[0].recent_event_ids == ["evt_valid"]
    assert stale_record.location_id == "loc_missing"
    assert event_records[1] is not stale_record
    assert event_records[1].location_id is None

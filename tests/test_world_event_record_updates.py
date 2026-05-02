"""Copy-normalization helpers for world event records."""

from __future__ import annotations

from dataclasses import dataclass, field

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.world_event_record_updates import (
    event_record_with_added_tags,
    event_record_with_location_id,
    event_record_with_normalized_location_references,
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


def test_event_record_location_reference_normalization_updates_metadata() -> None:
    record = WorldEventRecord(
        record_id="evt_route",
        location_id="old_origin",
        render_params={
            "location_id": "old_origin",
            "from_location_id": "old_origin",
            "to_location_id": "old_destination",
            "endpoint_location_ids": ["old_origin", "old_destination", "missing"],
        },
        tags=["world_change", "location:old_origin", "location:old_destination", "location:missing"],
        impacts=[
            {"target_type": "location", "target_id": "old_origin", "attribute": "safety"},
            {"target_type": "route", "target_id": "route_1", "attribute": "blocked"},
        ],
    )

    normalized = event_record_with_normalized_location_references(
        record,
        lambda location_id: {
            "old_origin": "loc_origin",
            "old_destination": "loc_destination",
        }.get(location_id or ""),
    )

    assert normalized is not record
    assert normalized.location_id == "loc_origin"
    assert normalized.render_params["location_id"] == "loc_origin"
    assert normalized.render_params["from_location_id"] == "loc_origin"
    assert normalized.render_params["to_location_id"] == "loc_destination"
    assert normalized.render_params["endpoint_location_ids"] == ["loc_origin", "loc_destination"]
    assert normalized.tags == ["world_change", "location:loc_origin", "location:loc_destination"]
    assert normalized.impacts[0]["target_id"] == "loc_origin"
    assert normalized.impacts[1]["target_id"] == "route_1"


def test_location_impact_is_removed_when_target_normalizes_to_none() -> None:
    record = WorldEventRecord(
        record_id="evt_missing_impact",
        impacts=[
            {"target_type": "location", "target_id": "missing", "attribute": "danger"},
            {"target_type": "route", "target_id": "route_1", "attribute": "blocked"},
        ],
    )

    normalized = event_record_with_normalized_location_references(record, lambda _location_id: None)

    assert normalized.impacts == [{"target_type": "route", "target_id": "route_1", "attribute": "blocked"}]
    assert record.impacts[0]["target_id"] == "missing"


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


def test_rebuild_recent_event_ids_includes_route_endpoint_metadata() -> None:
    origin = _Location()
    destination = _Location()
    event_records = [
        WorldEventRecord(
            record_id="evt_route_blocked",
            kind="route_blocked",
            location_id="loc_origin",
            render_params={
                "from_location_id": "loc_origin",
                "to_location_id": "loc_destination",
                "endpoint_location_ids": ["loc_origin", "loc_destination"],
            },
            tags=["location:loc_origin", "location:loc_destination"],
        )
    ]

    rebuild_recent_event_ids(
        locations=[origin, destination],
        location_index={"loc_origin": origin, "loc_destination": destination},
        event_records=event_records,
    )

    assert origin.recent_event_ids == ["evt_route_blocked"]
    assert destination.recent_event_ids == ["evt_route_blocked"]


def test_rebuild_recent_event_ids_normalizes_all_location_references() -> None:
    known = _Location()
    event_records = [
        WorldEventRecord(
            record_id="evt_mixed_locations",
            location_id="loc_known",
            render_params={
                "location_id": "loc_missing",
                "from_location_id": "loc_known",
                "to_location_id": "loc_missing",
                "endpoint_location_ids": ["loc_known", "loc_missing"],
            },
            tags=["location:loc_known", "location:loc_missing"],
            impacts=[
                {"target_type": "location", "target_id": "loc_missing", "attribute": "danger"},
                {"target_type": "route", "target_id": "route_1", "attribute": "blocked"},
            ],
        )
    ]

    rebuild_recent_event_ids(
        locations=[known],
        location_index={"loc_known": known},
        event_records=event_records,
    )

    normalized = event_records[0]
    assert known.recent_event_ids == ["evt_mixed_locations"]
    assert normalized.location_id == "loc_known"
    assert normalized.render_params["location_id"] is None
    assert normalized.render_params["from_location_id"] == "loc_known"
    assert normalized.render_params["to_location_id"] is None
    assert normalized.render_params["endpoint_location_ids"] == ["loc_known"]
    assert normalized.tags == ["location:loc_known"]
    assert normalized.impacts == [{"target_type": "route", "target_id": "route_1", "attribute": "blocked"}]

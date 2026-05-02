from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.world_event_index import EventHistoryIndex
from fantasy_simulator.world_event_queries import (
    events_by_actor,
    events_by_kind,
    events_by_location,
    events_by_month,
    events_by_year,
)


def test_event_query_helpers_return_index_snapshots() -> None:
    event_index = EventHistoryIndex()
    records = [
        WorldEventRecord(
            record_id="r1",
            kind="battle",
            year=1001,
            month=2,
            location_id="loc_one",
            primary_actor_id="char_one",
        ),
        WorldEventRecord(
            record_id="r2",
            kind="journey",
            year=1001,
            month=3,
            location_id="loc_two",
            primary_actor_id="char_two",
            secondary_actor_ids=["char_one"],
        ),
    ]

    assert events_by_location(event_index, records, "loc_one") == [records[0]]
    assert events_by_actor(event_index, records, "char_one") == records
    assert events_by_year(event_index, records, 1001) == records
    assert events_by_month(event_index, records, 1001, 3) == [records[1]]
    assert events_by_kind(event_index, records, "battle") == [records[0]]


def test_location_queries_include_record_location_metadata() -> None:
    event_index = EventHistoryIndex()
    records = [
        WorldEventRecord(
            record_id="route_blocked",
            kind="route_blocked",
            year=1001,
            month=2,
            location_id="loc_alpha",
            render_params={
                "from_location_id": "loc_alpha",
                "to_location_id": "loc_bravo",
                "endpoint_location_ids": ["loc_alpha", "loc_bravo"],
            },
            tags=["location:loc_alpha", "location:loc_bravo"],
        ),
    ]

    assert events_by_location(event_index, records, "loc_alpha") == records
    assert events_by_location(event_index, records, "loc_bravo") == records


def test_location_query_index_rebuilds_after_metadata_mutation() -> None:
    event_index = EventHistoryIndex()
    record = WorldEventRecord(
        record_id="route_blocked",
        kind="route_blocked",
        year=1001,
        month=2,
        location_id="loc_alpha",
        render_params={"to_location_id": "loc_bravo"},
    )
    records = [record]
    assert events_by_location(event_index, records, "loc_bravo") == records

    record.render_params["to_location_id"] = "loc_charlie"

    assert events_by_location(event_index, records, "loc_bravo") == []
    assert events_by_location(event_index, records, "loc_charlie") == records

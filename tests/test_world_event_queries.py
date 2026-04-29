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

from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.world import World
from fantasy_simulator.world_event_state import (
    apply_event_impact_to_location,
    append_canonical_event_record,
)


def test_apply_event_impact_to_location_updates_known_location() -> None:
    world = World()
    loc = world.get_location_by_id("loc_thornwood")
    before_safety = loc.safety

    impacts = apply_event_impact_to_location(
        kind="battle",
        location_id="loc_thornwood",
        location_index=world._location_id_index,
        clamp_state=lambda value: max(0, min(100, int(value))),
    )

    assert impacts
    assert loc.safety < before_safety
    assert any(item["attribute"] == "safety" for item in impacts)


def test_apply_event_impact_to_location_ignores_unknown_location() -> None:
    world = World()

    impacts = apply_event_impact_to_location(
        kind="battle",
        location_id="missing",
        location_index=world._location_id_index,
        clamp_state=lambda value: max(0, min(100, int(value))),
    )

    assert impacts == []


def test_append_canonical_event_record_prunes_records_and_indexes() -> None:
    world = World()
    max_records = 2

    r1 = WorldEventRecord(record_id="r1", kind="battle", year=1000, location_id="loc_thornwood")
    r2 = WorldEventRecord(record_id="r2", kind="battle", year=1000, location_id="loc_thornwood")
    r3 = WorldEventRecord(record_id="r3", kind="battle", year=1000, location_id="loc_thornwood")

    append_canonical_event_record(
        record=r1,
        event_records=world.event_records,
        location_index=world._location_id_index,
        grid=world.grid,
        max_event_records=max_records,
    )
    append_canonical_event_record(
        record=r2,
        event_records=world.event_records,
        location_index=world._location_id_index,
        grid=world.grid,
        max_event_records=max_records,
    )
    append_canonical_event_record(
        record=r3,
        event_records=world.event_records,
        location_index=world._location_id_index,
        grid=world.grid,
        max_event_records=max_records,
    )

    assert [record.record_id for record in world.event_records] == ["r2", "r3"]
    recent_ids = world.get_location_by_id("loc_thornwood").recent_event_ids
    assert recent_ids == ["r2", "r3"]


def test_append_canonical_event_record_normalizes_invalid_location_id() -> None:
    world = World()
    record = WorldEventRecord(record_id="r1", kind="battle", year=1000, location_id="invalid")

    append_canonical_event_record(
        record=record,
        event_records=world.event_records,
        location_index=world._location_id_index,
        grid=world.grid,
        max_event_records=world.MAX_EVENT_RECORDS,
    )

    assert record.location_id is None

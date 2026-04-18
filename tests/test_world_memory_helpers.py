from __future__ import annotations

from fantasy_simulator.world import MemorialRecord, World
from fantasy_simulator.world_memory import (
    add_alias,
    add_live_trace,
    link_memorial_record,
    memorials_for_location,
)


def test_add_live_trace_helper_trims_to_cap() -> None:
    world = World()
    for i in range(World.MAX_LIVE_TRACES + 2):
        add_live_trace(
            location_index=world._location_id_index,
            location_id="loc_aethoria_capital",
            year=1000 + i,
            char_name=f"char_{i}",
            text=f"text_{i}",
            max_live_traces=World.MAX_LIVE_TRACES,
        )

    location = world.get_location_by_id("loc_aethoria_capital")
    assert location is not None
    assert len(location.live_traces) == World.MAX_LIVE_TRACES
    assert location.live_traces[-1]["char_name"] == f"char_{World.MAX_LIVE_TRACES + 1}"


def test_link_memorial_record_and_lookup_helper_skip_stale_ids() -> None:
    world = World()
    record = MemorialRecord(
        memorial_id="m1",
        character_id="c1",
        character_name="Aldric",
        location_id="loc_aethoria_capital",
        year=1005,
        cause="battle_fatal",
        epitaph="Epitaph",
    )

    link_memorial_record(
        memorials=world.memorials,
        location_index=world._location_id_index,
        record=record,
    )
    location = world.get_location_by_id("loc_aethoria_capital")
    assert location is not None
    location.memorial_ids.append("stale")

    results = memorials_for_location(
        location_index=world._location_id_index,
        memorials=world.memorials,
        location_id="loc_aethoria_capital",
    )

    assert [item.memorial_id for item in results] == ["m1"]


def test_add_alias_helper_respects_uniqueness_and_cap() -> None:
    world = World()
    for alias in ["A", "A", "B", "C", "D"]:
        add_alias(
            location_index=world._location_id_index,
            location_id="loc_aethoria_capital",
            alias=alias,
            max_aliases=3,
        )

    location = world.get_location_by_id("loc_aethoria_capital")
    assert location is not None
    assert location.aliases == ["A", "B", "C"]

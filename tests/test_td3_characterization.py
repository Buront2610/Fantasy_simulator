from __future__ import annotations

from fantasy_simulator.event_models import EventResult, WorldEventRecord
from fantasy_simulator.simulation.engine import Simulator
from fantasy_simulator.world import World


def test_world_record_event_updates_recent_ids_and_compat_event_log() -> None:
    world = World()
    record = WorldEventRecord(
        record_id="r1",
        kind="battle",
        year=1000,
        month=2,
        day=3,
        location_id="loc_thornwood",
        description="Battle at Thornwood",
    )

    world.record_event(record)

    loc = world.get_location_by_id("loc_thornwood")
    assert loc.recent_event_ids[-1] == "r1"
    compat_log = world.get_compatibility_event_log(last_n=1)
    assert compat_log and "Battle at Thornwood" in compat_log[0]


def test_simulator_record_world_event_keeps_world_record_and_compat_paths() -> None:
    world = World()
    sim = Simulator(world, seed=42)

    rec = sim._record_world_event(  # noqa: SLF001 - characterization seam
        "Discovery happened",
        kind="discovery",
        location_id="loc_thornwood",
        primary_actor_id="char_x",
    )

    assert rec in world.event_records
    assert any("Discovery happened" in line for line in world.get_compatibility_event_log())


def test_simulator_record_event_from_event_result_preserves_projection() -> None:
    world = World()
    sim = Simulator(world, seed=42)
    result = EventResult(
        description="Met someone",
        affected_characters=["a", "b"],
        event_type="meeting",
        year=world.year,
    )

    sim._record_event(result, location_id="loc_thornwood")  # noqa: SLF001 - characterization seam

    stored = world.event_records[-1]
    projected = stored.to_event_result()
    assert projected.description == result.description
    assert projected.event_type == result.event_type
    assert projected.affected_characters == result.affected_characters

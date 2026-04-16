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


def test_invalid_location_event_roundtrip_through_report_and_save_load() -> None:
    world = World()
    sim = Simulator(world, seed=42)

    rec = sim._record_world_event(  # noqa: SLF001 - characterization seam
        "Invalid location event",
        kind="meeting",
        location_id="loc_invalid",
    )

    assert rec.location_id is None
    assert world.event_records[-1].location_id is None
    assert any("Invalid location event" in line for line in world.get_compatibility_event_log())

    monthly = sim.get_monthly_report(world.year, sim.current_month)
    yearly = sim.get_yearly_report(world.year)
    assert "Total events: 1" in monthly
    assert "Total events recorded: 1" in yearly

    restored = Simulator.from_dict(sim.to_dict())
    assert restored.world.event_records[-1].location_id is None
    assert any("Invalid location event" in line for line in restored.world.get_compatibility_event_log())


def test_seeded_td3_external_outputs_are_reproducible() -> None:
    def _snapshot(seed: int) -> tuple[str, list[str], str, str]:
        world = World()
        sim = Simulator(world, seed=seed)
        kinds = ["meeting", "journey", "discovery", "battle"]
        for index in range(12):
            roll = sim.rng.randint(1000, 9999)
            kind = kinds[sim.rng.randint(0, len(kinds) - 1)]
            location_id = "loc_thornwood" if index % 2 == 0 else "loc_silverkeep"
            sim._record_world_event(  # noqa: SLF001 - acceptance harness seam
                f"seeded-{roll}-{kind}",
                kind=kind,
                location_id=location_id,
                month=1,
            )
        return (
            sim.get_summary(),
            sim.get_event_log(last_n=20),
            sim.get_monthly_report(sim.world.year, 1),
            sim.get_yearly_report(sim.world.year),
        )

    snap1 = _snapshot(seed=20260415)
    snap2 = _snapshot(seed=20260415)
    snap3 = _snapshot(seed=20260416)

    assert snap1 == snap2
    assert snap1 != snap3


def test_save_payload_uses_canonical_event_records_without_legacy_duplication() -> None:
    world = World()
    sim = Simulator(world, seed=42)
    sim._record_world_event(  # noqa: SLF001 - characterization seam
        "Canonical only",
        kind="meeting",
        location_id="loc_thornwood",
    )

    payload = sim.to_dict()

    assert "history" not in payload
    assert "event_log" not in payload["world"]
    assert payload["world"]["event_records"]

    restored = Simulator.from_dict(payload)
    assert any("Canonical only" in line for line in restored.get_event_log())

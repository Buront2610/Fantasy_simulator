"""PR-K save/load contracts for world-change runtime state and history."""

from __future__ import annotations

import pytest

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.ids import RouteId
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World
from fantasy_simulator.world_change import RouteUpdate, WorldChangeSet, apply_world_change_set


def _event_payloads(records: list[WorldEventRecord]) -> list[dict]:
    return [record.to_dict() for record in records]


def test_save_load_roundtrip_preserves_world_change_runtime_state_and_canonical_history(tmp_path) -> None:
    world = World()
    route = world.routes[0]
    route_id = route.route_id
    from_location_id = route.from_site_id
    to_location_id = route.to_site_id
    location_id = "loc_aethoria_capital"
    location = world.get_location_by_id(location_id)
    assert location is not None

    old_name = location.canonical_name
    expected_records = [
        world.apply_route_blocked_change(route_id, True, month=2, day=3),
        world.apply_route_blocked_change(route_id, False, month=2, day=4),
        world.apply_route_blocked_change(route_id, True, month=2, day=5),
        world.apply_location_rename_change(location_id, "Aethoria March", month=2, day=6),
        world.apply_controlling_faction_change(location_id, "stormwatch_wardens", month=2, day=7),
        world.apply_controlling_faction_change(location_id, None, month=2, day=8),
        world.apply_controlling_faction_change(location_id, "free_city_league", month=2, day=9),
    ]
    assert all(record is not None for record in expected_records)
    expected_payloads = _event_payloads([record for record in expected_records if record is not None])

    path = tmp_path / "pr-k-world-change-roundtrip.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True

    restored = load_simulation(str(path))

    assert restored is not None
    restored_route = next(route for route in restored.world.routes if route.route_id == route_id)
    restored_location = restored.world.get_location_by_id(location_id)
    assert restored_location is not None
    assert restored_route.blocked is True
    assert restored_location.id == location_id
    assert restored_location.canonical_name == "Aethoria March"
    assert restored_location.aliases == [old_name]
    assert restored_location.controlling_faction_id == "free_city_league"
    assert restored.world.get_location_by_name("Aethoria March") is restored_location
    assert restored.world.get_location_by_name(old_name) is None
    assert _event_payloads(restored.world.event_records) == expected_payloads

    route_record_ids = {
        record.record_id
        for record in restored.world.event_records
        if record.kind in {"route_blocked", "route_reopened"}
    }
    for endpoint_id in (from_location_id, to_location_id):
        endpoint_records = [
            record
            for record in restored.world.get_events_by_location(endpoint_id)
            if record.record_id in route_record_ids
        ]
        endpoint = restored.world.get_location_by_id(endpoint_id)
        assert endpoint is not None
        assert [record.kind for record in endpoint_records] == [
            "route_blocked",
            "route_reopened",
            "route_blocked",
        ]
        assert route_record_ids.issubset(set(endpoint.recent_event_ids))

    rename_records = restored.world.get_events_by_location(location_id)
    assert [record.kind for record in rename_records] == [
        "location_renamed",
        "location_faction_changed",
        "location_faction_changed",
        "location_faction_changed",
    ]
    assert rename_records[0].record_id in restored_location.recent_event_ids
    control_records = [record for record in rename_records if record.kind == "location_faction_changed"]
    assert [record.render_params["old_faction_id"] for record in control_records] == [
        None,
        "stormwatch_wardens",
        None,
    ]
    assert [record.render_params["new_faction_id"] for record in control_records] == [
        "stormwatch_wardens",
        None,
        "free_city_league",
    ]
    assert {record.record_id for record in control_records}.issubset(set(restored_location.recent_event_ids))


def test_save_load_roundtrip_preserves_terrain_cell_mutation_and_canonical_history(tmp_path) -> None:
    world = World()
    assert world.terrain_map is not None
    x, y = 2, 2
    cell = world.terrain_map.get(x, y)
    assert cell is not None

    record = world.apply_terrain_cell_change(
        x,
        y,
        biome="forest",
        elevation=180,
        moisture=190,
        temperature=80,
        location_id="loc_aethoria_capital",
        reason_key="fey_bloom",
        month=3,
        day=4,
    )
    assert record is not None
    expected_payloads = _event_payloads([record])

    path = tmp_path / "pr-k-terrain-cell-roundtrip.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True

    restored = load_simulation(str(path))

    assert restored is not None
    assert restored.world.terrain_map is not None
    restored_cell = restored.world.terrain_map.get(x, y)
    assert restored_cell is not None
    assert restored_cell.biome == "forest"
    assert restored_cell.elevation == 180
    assert restored_cell.moisture == 190
    assert restored_cell.temperature == 80
    assert _event_payloads(restored.world.event_records) == expected_payloads
    assert restored.world.get_events_by_kind("terrain_cell_mutated") == [restored.world.event_records[0]]
    assert restored.world.get_events_by_location("loc_aethoria_capital") == [restored.world.event_records[0]]
    restored_location = restored.world.get_location_by_id("loc_aethoria_capital")
    assert restored_location is not None
    assert record.record_id in restored_location.recent_event_ids


def test_world_change_noops_do_not_mutate_runtime_state_or_append_canonical_records() -> None:
    world = World()
    route = world.routes[0]
    location = world.get_location_by_id("loc_aethoria_capital")
    assert world.terrain_map is not None
    terrain_cell = world.terrain_map.get(1, 0)
    assert location is not None
    assert terrain_cell is not None
    terrain_cell_payload = terrain_cell.to_dict()

    route_recent_event_ids = {
        route.from_site_id: list(world.get_location_by_id(route.from_site_id).recent_event_ids),
        route.to_site_id: list(world.get_location_by_id(route.to_site_id).recent_event_ids),
    }
    location_recent_event_ids = list(location.recent_event_ids)

    assert world.apply_route_blocked_change(route.route_id, route.blocked) is None
    assert world.apply_location_rename_change(location.id, location.canonical_name) is None
    assert world.apply_controlling_faction_change(location.id, location.controlling_faction_id) is None
    assert world.apply_terrain_cell_change(
        terrain_cell.x,
        terrain_cell.y,
        biome=terrain_cell.biome,
        elevation=terrain_cell.elevation,
        moisture=terrain_cell.moisture,
        temperature=terrain_cell.temperature,
    ) is None

    assert route.blocked is False
    assert location.canonical_name == "Aethoria Capital"
    assert location.aliases == []
    assert location.controlling_faction_id is None
    assert terrain_cell.to_dict() == terrain_cell_payload
    assert world.event_records == []
    assert {
        route.from_site_id: list(world.get_location_by_id(route.from_site_id).recent_event_ids),
        route.to_site_id: list(world.get_location_by_id(route.to_site_id).recent_event_ids),
    } == route_recent_event_ids
    assert location.recent_event_ids == location_recent_event_ids


def test_world_change_route_recording_failure_rolls_back_runtime_state(monkeypatch) -> None:
    world = World()
    route = world.routes[0]

    def fail_record_event(_record: WorldEventRecord) -> WorldEventRecord:
        raise ValueError("recording failed")

    monkeypatch.setattr(world, "record_event", fail_record_event)

    with pytest.raises(ValueError, match="recording failed"):
        world.apply_route_blocked_change(route.route_id, True)

    assert route.blocked is False
    assert world.event_records == []
    assert world.get_events_by_location(route.from_site_id) == []
    assert world.get_events_by_location(route.to_site_id) == []


def test_world_change_multi_event_failure_rolls_back_canonical_history_and_recent_indexes() -> None:
    world = World()
    route = world.routes[0]
    from_location = world.get_location_by_id(route.from_site_id)
    to_location = world.get_location_by_id(route.to_site_id)
    assert from_location is not None
    assert to_location is not None

    baseline_record = world.record_event(
        WorldEventRecord(
            record_id="baseline-event",
            kind="festival",
            year=999,
            location_id=route.from_site_id,
            description="A baseline event.",
        )
    )
    assert world.get_events_by_location(route.from_site_id) == [baseline_record]

    baseline_records = list(world.event_records)
    baseline_from_recent_event_ids = list(from_location.recent_event_ids)
    baseline_to_recent_event_ids = list(to_location.recent_event_ids)

    duplicated_record_id = "duplicate-world-change-event"
    change_set = WorldChangeSet(
        events=(
            WorldEventRecord(
                record_id=duplicated_record_id,
                kind="route_blocked",
                year=1001,
                location_id=route.from_site_id,
                description="The route was blocked.",
                render_params={
                    "endpoint_location_ids": [route.from_site_id, route.to_site_id],
                },
                tags=["world_change"],
            ),
            WorldEventRecord(
                record_id=duplicated_record_id,
                kind="route_reopened",
                year=1001,
                location_id=route.from_site_id,
                description="The route was reopened.",
                render_params={
                    "endpoint_location_ids": [route.from_site_id, route.to_site_id],
                },
                tags=["world_change"],
            ),
        ),
        route_updates=(
            RouteUpdate(
                route_id=RouteId(route.route_id),
                old_blocked=False,
                new_blocked=True,
            ),
        ),
    )

    with pytest.raises(ValueError, match="Duplicate event record ID"):
        apply_world_change_set(change_set, routes=world.routes, record_event=world.record_event)

    assert route.blocked is False
    assert world.event_records == baseline_records
    assert from_location.recent_event_ids == baseline_from_recent_event_ids
    assert to_location.recent_event_ids == baseline_to_recent_event_ids
    assert world.get_events_by_location(route.from_site_id) == [baseline_record]
    assert world.get_events_by_location(route.to_site_id) == []


def test_world_change_multi_event_changeset_rejects_non_snapshot_capable_recorder() -> None:
    world = World()
    route = world.routes[0]
    change_set = WorldChangeSet(
        events=(
            WorldEventRecord(
                record_id="first-world-change-event",
                kind="route_blocked",
                year=1001,
                location_id=route.from_site_id,
                description="The route was blocked.",
            ),
            WorldEventRecord(
                record_id="second-world-change-event",
                kind="route_reopened",
                year=1001,
                location_id=route.from_site_id,
                description="The route was reopened.",
            ),
        ),
        route_updates=(
            RouteUpdate(
                route_id=RouteId(route.route_id),
                old_blocked=False,
                new_blocked=True,
            ),
        ),
    )

    with pytest.raises(ValueError, match="snapshot-capable event recorder"):
        apply_world_change_set(
            change_set,
            routes=world.routes,
            record_event=lambda record: world.record_event(record),
        )

    assert route.blocked is False
    assert world.event_records == []
    assert world.get_events_by_location(route.from_site_id) == []


def test_world_change_rename_recording_failure_rolls_back_runtime_state(monkeypatch) -> None:
    world = World()
    location = world.get_location_by_id("loc_aethoria_capital")
    assert location is not None
    old_name = location.canonical_name

    def fail_record_event(_record: WorldEventRecord) -> WorldEventRecord:
        raise ValueError("recording failed")

    monkeypatch.setattr(world, "record_event", fail_record_event)

    with pytest.raises(ValueError, match="recording failed"):
        world.apply_location_rename_change(location.id, "Aethoria March")

    assert location.canonical_name == old_name
    assert location.aliases == []
    assert world.get_location_by_name(old_name) is location
    assert world.get_location_by_name("Aethoria March") is None
    assert world.event_records == []
    assert world.get_events_by_location(location.id) == []


def test_world_change_control_recording_failure_rolls_back_runtime_state(monkeypatch) -> None:
    world = World()
    location = world.get_location_by_id("loc_aethoria_capital")
    assert location is not None

    def fail_record_event(_record: WorldEventRecord) -> WorldEventRecord:
        raise ValueError("recording failed")

    monkeypatch.setattr(world, "record_event", fail_record_event)

    with pytest.raises(ValueError, match="recording failed"):
        world.apply_controlling_faction_change(location.id, "stormwatch_wardens")

    assert location.controlling_faction_id is None
    assert world.event_records == []
    assert world.get_events_by_location(location.id) == []


def test_world_change_terrain_recording_failure_rolls_back_runtime_state(monkeypatch) -> None:
    world = World()
    assert world.terrain_map is not None
    cell = world.terrain_map.get(1, 0)
    assert cell is not None
    old_payload = cell.to_dict()

    def fail_record_event(_record: WorldEventRecord) -> WorldEventRecord:
        raise ValueError("recording failed")

    monkeypatch.setattr(world, "record_event", fail_record_event)

    with pytest.raises(ValueError, match="recording failed"):
        world.apply_terrain_cell_change(1, 0, biome="forest", elevation=180)

    assert cell.to_dict() == old_payload
    assert world.event_records == []
    assert world.get_events_by_kind("terrain_cell_mutated") == []

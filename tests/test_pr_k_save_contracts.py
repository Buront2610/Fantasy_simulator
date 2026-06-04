"""PR-K save/load contracts for world-change runtime state and history."""

from __future__ import annotations

import json

import pytest

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.ids import RouteId
from fantasy_simulator.observation import build_era_timeline_projection, build_war_map_projection
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.reports import generate_monthly_report, generate_yearly_report
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World
from fantasy_simulator.world_change import RouteUpdate, WorldChangeSet, apply_world_change_set
from fantasy_simulator.world_location_state import clamp_state


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
        world.apply_controlling_faction_change(location_id, "silverbrook_merchant_league", month=2, day=9),
    ]
    assert all(record is not None for record in expected_records)
    expected_payloads = _event_payloads([record for record in expected_records if record is not None])
    expected_location_state = (
        location.danger,
        location.rumor_heat,
        location.safety,
        location.mood,
        location.road_condition,
        location.traffic,
        list(location.live_traces),
    )
    route_to_location = world.get_location_by_id(to_location_id)
    assert route_to_location is not None
    expected_route_to_state = (
        route_to_location.danger,
        route_to_location.rumor_heat,
        route_to_location.safety,
        route_to_location.mood,
        route_to_location.road_condition,
        route_to_location.traffic,
        list(route_to_location.live_traces),
    )

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
    assert restored_location.controlling_faction_id == "silverbrook_merchant_league"
    assert (
        restored_location.danger,
        restored_location.rumor_heat,
        restored_location.safety,
        restored_location.mood,
        restored_location.road_condition,
        restored_location.traffic,
        restored_location.live_traces,
    ) == expected_location_state
    restored_route_to_location = restored.world.get_location_by_id(to_location_id)
    assert restored_route_to_location is not None
    assert (
        restored_route_to_location.danger,
        restored_route_to_location.rumor_heat,
        restored_route_to_location.safety,
        restored_route_to_location.mood,
        restored_route_to_location.road_condition,
        restored_route_to_location.traffic,
        restored_route_to_location.live_traces,
    ) == expected_route_to_state
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
        "aethorian_crown_council",
        "stormwatch_wardens",
        None,
    ]
    assert [record.render_params["new_faction_id"] for record in control_records] == [
        "stormwatch_wardens",
        None,
        "silverbrook_merchant_league",
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
    location = world.get_location_by_id("loc_aethoria_capital")
    assert location is not None
    expected_location_state = (
        location.danger,
        location.rumor_heat,
        location.safety,
        location.mood,
        location.road_condition,
        list(location.live_traces),
    )
    expected_payloads = _event_payloads([record])

    path = tmp_path / "pr-k-terrain-cell-roundtrip.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert "terrain_map" not in payload["world"]

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
    assert (
        restored_location.danger,
        restored_location.rumor_heat,
        restored_location.safety,
        restored_location.mood,
        restored_location.road_condition,
        restored_location.live_traces,
    ) == expected_location_state


def test_save_load_roundtrip_preserves_war_declaration_projection_and_report(tmp_path) -> None:
    world = World()
    record = world.apply_war_declaration(
        "stormwatch_wardens",
        "silverbrook_merchant_league",
        location_ids=("loc_aethoria_capital", "loc_silverbrook"),
        year=1001,
        month=6,
        day=7,
        cause_key="border_incident",
    )
    capital = world.get_location_by_id("loc_aethoria_capital")
    silverbrook = world.get_location_by_id("loc_silverbrook")
    assert capital is not None
    assert silverbrook is not None
    expected_capital_state = (capital.danger, capital.rumor_heat, capital.safety, capital.mood, capital.live_traces[-1])
    expected_silverbrook_state = (
        silverbrook.danger,
        silverbrook.rumor_heat,
        silverbrook.safety,
        silverbrook.mood,
        silverbrook.live_traces[-1],
    )
    expected_payloads = _event_payloads([record])

    path = tmp_path / "pr-k-war-declaration-roundtrip.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["world"]["event_records"] == expected_payloads
    assert "war_runtime" not in payload["world"]
    assert "wars" not in payload["world"]

    restored = load_simulation(str(path))

    assert restored is not None
    assert _event_payloads(restored.world.event_records) == expected_payloads
    projection = build_war_map_projection(event_records=restored.world.event_records)
    assert projection.events[0].record_id == record.record_id
    assert projection.affected_location_ids == ("loc_aethoria_capital", "loc_silverbrook")
    assert projection.faction_ids == ("stormwatch_wardens", "silverbrook_merchant_league")
    restored_capital = restored.world.get_location_by_id("loc_aethoria_capital")
    restored_silverbrook = restored.world.get_location_by_id("loc_silverbrook")
    assert restored_capital is not None
    assert restored_silverbrook is not None
    assert (
        restored_capital.danger,
        restored_capital.rumor_heat,
        restored_capital.safety,
        restored_capital.mood,
        restored_capital.live_traces[-1],
    ) == expected_capital_state
    assert (
        restored_silverbrook.danger,
        restored_silverbrook.rumor_heat,
        restored_silverbrook.safety,
        restored_silverbrook.mood,
        restored_silverbrook.live_traces[-1],
    ) == expected_silverbrook_state
    report = generate_monthly_report(restored.world, 1001, 6)
    assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
        (record.record_id, "war")
    ]


def test_save_load_roundtrip_preserves_era_civilization_projection_without_runtime_fields(tmp_path) -> None:
    world = World()
    capital = world.get_location_by_id("loc_aethoria_capital")
    assert capital is not None
    before_capital = (
        capital.prosperity,
        capital.safety,
        capital.mood,
        capital.traffic,
        capital.danger,
        capital.rumor_heat,
    )
    era_record = world.apply_era_shift(
        "age_of_reckoning",
        authored_era_keys={"age_of_embers", "age_of_reckoning"},
        year=1002,
        month=1,
        cause_key="dragon_war",
    )
    drift_record = world.apply_civilization_phase_drift(
        "crisis",
        score_deltas={"prosperity": -7, "safety": -20, "mood": -5, "traffic": -3},
        year=1002,
        month=2,
        reason_key="war_pressure",
    )
    expected_payloads = _event_payloads([era_record, drift_record])
    expected_capital_state = (
        clamp_state(before_capital[0] + 3 - 7),
        clamp_state(before_capital[1] - 20),
        clamp_state(before_capital[2] + 4 - 5),
        clamp_state(before_capital[3] + 6 - 3),
        clamp_state(before_capital[4] + 10),
        clamp_state(before_capital[5] + 20 + 10),
        capital.live_traces[-1],
    )

    path = tmp_path / "pr-k-era-civilization-roundtrip.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert payload["world"]["event_records"] == expected_payloads
    assert "era_key" not in payload["world"]
    assert "civilization_phase" not in payload["world"]
    assert "world_scores" not in payload["world"]
    assert "era_runtime" not in payload["world"]

    restored = load_simulation(str(path))

    assert restored is not None
    assert _event_payloads(restored.world.event_records) == expected_payloads
    assert not hasattr(restored.world, "era_key")
    assert not hasattr(restored.world, "civilization_phase")
    assert not hasattr(restored.world, "world_scores")
    assert not hasattr(restored.world, "era_runtime")
    restored_capital = restored.world.get_location_by_id("loc_aethoria_capital")
    assert restored_capital is not None
    assert (
        restored_capital.prosperity,
        restored_capital.safety,
        restored_capital.mood,
        restored_capital.traffic,
        restored_capital.danger,
        restored_capital.rumor_heat,
        restored_capital.live_traces[-1],
    ) == expected_capital_state
    projection = build_era_timeline_projection(event_records=restored.world.event_records)
    assert [entry.record_id for entry in projection.entries] == [
        era_record.record_id,
        drift_record.record_id,
    ]
    assert projection.current_era_id == "age_of_reckoning"
    assert projection.current_civilization_phase == "crisis"
    report = generate_yearly_report(restored.world, 1002)
    assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
        (era_record.record_id, "era"),
        (drift_record.record_id, "civilization"),
    ]


def test_load_discards_conflicting_era_runtime_snapshot_when_canonical_records_exist(tmp_path) -> None:
    world = World()
    era_record = world.apply_era_shift(
        "age_of_reckoning",
        authored_era_keys={"age_of_embers", "age_of_reckoning"},
        year=1002,
        month=1,
    )
    drift_record = world.apply_civilization_phase_drift(
        "crisis",
        score_deltas={"safety": -10},
        year=1002,
        month=2,
    )
    path = tmp_path / "pr-k-conflicting-era-runtime.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    payload["world"].update({
        "era_key": "stale_age",
        "civilization_phase": "stable",
        "world_scores": {"safety": 99},
        "era_runtime": {
            "era_key": "snapshot_age",
            "civilization_phase": "golden_age",
            "world_scores": {"prosperity": 100},
        },
    })
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    restored = load_simulation(str(path))

    assert restored is not None
    assert not hasattr(restored.world, "era_key")
    assert not hasattr(restored.world, "civilization_phase")
    assert not hasattr(restored.world, "world_scores")
    assert not hasattr(restored.world, "era_runtime")
    assert not hasattr(restored.world, "_era_runtime")
    projection = build_era_timeline_projection(event_records=restored.world.event_records)
    assert [entry.record_id for entry in projection.entries] == [
        era_record.record_id,
        drift_record.record_id,
    ]
    assert projection.current_era_id == "age_of_reckoning"
    assert projection.current_civilization_phase == "crisis"


def test_load_ignores_era_runtime_snapshot_without_canonical_records(tmp_path) -> None:
    path = tmp_path / "pr-k-era-runtime-without-records.json"
    assert save_simulation(Simulator(World(), seed=0), str(path)) is True
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    payload["world"]["event_records"] = []
    payload["world"].update({
        "era_key": "stale_age",
        "civilization_phase": "golden_age",
        "world_scores": {"safety": 99},
        "era_runtime": {
            "era_key": "snapshot_age",
            "civilization_phase": "golden_age",
            "world_scores": {"prosperity": 100},
        },
    })
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    restored = load_simulation(str(path))

    assert restored is not None
    assert not hasattr(restored.world, "era_key")
    assert not hasattr(restored.world, "civilization_phase")
    assert not hasattr(restored.world, "world_scores")
    assert not hasattr(restored.world, "era_runtime")
    assert not hasattr(restored.world, "_era_runtime")
    projection = build_era_timeline_projection(event_records=restored.world.event_records)
    assert projection.entries == ()
    assert projection.current_era_id is None
    assert projection.current_civilization_phase is None


def test_save_load_full_terrain_snapshot_wins_over_sparse_event_replay(tmp_path) -> None:
    world = World()
    assert world.terrain_map is not None
    record = world.apply_terrain_cell_change(2, 2, biome="forest", elevation=180)
    assert record is not None

    snapshot = world.terrain_map.to_dict()
    snapshot_cell = next(cell for cell in snapshot["cells"] if cell["x"] == 2 and cell["y"] == 2)
    snapshot_cell["biome"] = "swamp"
    snapshot_cell["elevation"] = 77

    path = tmp_path / "pr-k-terrain-full-snapshot-precedence.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    payload["world"]["terrain_map"] = snapshot
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    restored = load_simulation(str(path))

    assert restored is not None
    assert restored.world.terrain_map is not None
    restored_cell = restored.world.terrain_map.get(2, 2)
    assert restored_cell is not None
    assert restored_cell.biome == "swamp"
    assert restored_cell.elevation == 77


def test_save_load_replays_multiple_sparse_terrain_records_on_same_cell(tmp_path) -> None:
    world = World()
    assert world.terrain_map is not None
    first = world.apply_terrain_cell_change(2, 2, biome="forest", elevation=180)
    second = world.apply_terrain_cell_change(2, 2, biome="swamp", moisture=200)
    assert first is not None
    assert second is not None

    path = tmp_path / "pr-k-terrain-multiple-sparse-records.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert "terrain_map" not in payload["world"]

    restored = load_simulation(str(path))

    assert restored is not None
    assert restored.world.terrain_map is not None
    restored_cell = restored.world.terrain_map.get(2, 2)
    assert restored_cell is not None
    assert restored_cell.biome == "swamp"
    assert restored_cell.elevation == 180
    assert restored_cell.moisture == 200
    assert [record.record_id for record in restored.world.event_records] == [first.record_id, second.record_id]


def test_save_load_accepts_reordered_sparse_terrain_changed_attributes(tmp_path) -> None:
    world = World()
    assert world.terrain_map is not None
    record = world.apply_terrain_cell_change(2, 2, biome="forest", elevation=180)
    assert record is not None

    path = tmp_path / "pr-k-terrain-reordered-changed-attributes.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert "terrain_map" not in payload["world"]
    payload["world"]["event_records"][0]["render_params"]["changed_attributes"] = ["elevation", "biome"]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    restored = load_simulation(str(path))

    assert restored is not None
    assert restored.world.terrain_map is not None
    restored_cell = restored.world.terrain_map.get(2, 2)
    assert restored_cell is not None
    assert restored_cell.biome == "forest"
    assert restored_cell.elevation == 180


def test_save_load_rejects_stale_sparse_terrain_record_without_snapshot(tmp_path) -> None:
    world = World()
    assert world.terrain_map is not None
    record = world.apply_terrain_cell_change(2, 2, biome="forest", elevation=180)
    assert record is not None

    path = tmp_path / "pr-k-terrain-stale-sparse-record.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert "terrain_map" not in payload["world"]
    payload["world"]["event_records"][0]["render_params"]["old_biome"] = "swamp"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    assert load_simulation(str(path)) is None


def test_save_load_rejects_sparse_terrain_record_with_mismatched_cell_id(tmp_path) -> None:
    world = World()
    assert world.terrain_map is not None
    record = world.apply_terrain_cell_change(2, 2, biome="forest", elevation=180)
    assert record is not None

    path = tmp_path / "pr-k-terrain-mismatched-cell-id.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert "terrain_map" not in payload["world"]
    payload["world"]["event_records"][0]["render_params"]["terrain_cell_id"] = "terrain:1:1"
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    assert load_simulation(str(path)) is None


def test_save_load_rejects_sparse_terrain_record_with_inconsistent_changed_attributes(tmp_path) -> None:
    world = World()
    assert world.terrain_map is not None
    record = world.apply_terrain_cell_change(2, 2, biome="forest", elevation=180)
    assert record is not None

    path = tmp_path / "pr-k-terrain-inconsistent-changed-attributes.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    with open(path, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    assert "terrain_map" not in payload["world"]
    payload["world"]["event_records"][0]["render_params"]["changed_attributes"] = ["biome"]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle)

    assert load_simulation(str(path)) is None


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
    assert location.controlling_faction_id == "aethorian_crown_council"
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
        apply_world_change_set(
            change_set,
            routes=world.routes,
            record_event=world.world_change_event_recorder(),
        )

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


def test_world_change_single_event_port_recording_failure_restores_event_history() -> None:
    world = World()
    route = world.routes[0]
    from_location = world.get_location_by_id(route.from_site_id)
    assert from_location is not None
    baseline_records = list(world.event_records)
    baseline_recent_event_ids = list(from_location.recent_event_ids)
    recorder = world.world_change_event_recorder()

    class _FailingAfterRecordingPort:
        snapshot_count = 0
        restore_count = 0

        def record(self, record: WorldEventRecord) -> WorldEventRecord:
            recorder.record(record)
            raise ValueError("recording failed after append")

        def snapshot(self):
            self.snapshot_count += 1
            return recorder.snapshot()

        def restore(self, snapshot) -> None:
            self.restore_count += 1
            recorder.restore(snapshot)

    failing_recorder = _FailingAfterRecordingPort()
    change_set = WorldChangeSet(
        events=(
            WorldEventRecord(
                record_id="single-world-change-event",
                kind="route_blocked",
                year=1001,
                location_id=route.from_site_id,
                description="The route was blocked.",
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

    with pytest.raises(ValueError, match="recording failed after append"):
        apply_world_change_set(
            change_set,
            routes=world.routes,
            record_event=failing_recorder,
        )

    assert failing_recorder.snapshot_count == 1
    assert failing_recorder.restore_count == 1
    assert route.blocked is False
    assert world.event_records == baseline_records
    assert from_location.recent_event_ids == baseline_recent_event_ids
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

    assert location.controlling_faction_id == "aethorian_crown_council"
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

from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.ids import LocationId
from fantasy_simulator.terrain import BIOME_TYPES, TerrainCell, TerrainMap
from fantasy_simulator.world import World
from fantasy_simulator.world_change import (
    MutateTerrainCellCommand,
    apply_world_change_set,
    build_terrain_cell_mutation_change_set,
)
from fantasy_simulator.world_change.state_machines import transition_terrain_cell


def _terrain_map() -> TerrainMap:
    terrain_map = TerrainMap(width=2, height=2)
    for y in range(2):
        for x in range(2):
            terrain_map.set_cell(TerrainCell(x=x, y=y, biome="plains"))
    return terrain_map


def _describe(summary_key: str, _render_params: dict, fallback_description: str) -> str:
    assert summary_key == "events.terrain_cell_mutated.summary"
    return fallback_description


def test_terrain_cell_state_machine_returns_noop_for_identical_cell_state() -> None:
    assert transition_terrain_cell(
        x=1,
        y=0,
        old_biome="plains",
        requested_biome="plains",
        old_elevation=128,
        requested_elevation=128,
        old_moisture=128,
        requested_moisture=128,
        old_temperature=128,
        requested_temperature=128,
    ) is None


def test_terrain_cell_state_machine_reports_changed_attributes() -> None:
    transition = transition_terrain_cell(
        x=1,
        y=0,
        old_biome="plains",
        requested_biome="forest",
        old_elevation=128,
        requested_elevation=160,
        old_moisture=128,
        requested_moisture=170,
        old_temperature=128,
        requested_temperature=90,
    )

    assert transition is not None
    assert transition.event_kind == "terrain_cell_mutated"
    assert transition.changed_attributes == ("biome", "elevation", "moisture", "temperature")


def test_terrain_cell_changeset_returns_noop_for_idempotent_command() -> None:
    terrain_map = _terrain_map()
    command = MutateTerrainCellCommand(x=1, y=0, year=1001)

    change_set = build_terrain_cell_mutation_change_set(
        command,
        terrain_map=terrain_map,
        allowed_biomes=set(BIOME_TYPES),
        describe=_describe,
    )

    assert change_set is None


def test_terrain_cell_changeset_contains_event_and_runtime_update() -> None:
    terrain_map = _terrain_map()
    command = MutateTerrainCellCommand(
        x=1,
        y=0,
        year=1001,
        month=2,
        day=3,
        biome="forest",
        elevation=160,
        moisture=170,
        temperature=90,
        location_id=LocationId("loc_origin"),
        reason_key="fey_bloom",
    )

    change_set = build_terrain_cell_mutation_change_set(
        command,
        terrain_map=terrain_map,
        allowed_biomes=set(BIOME_TYPES),
        describe=_describe,
    )

    assert change_set is not None
    assert change_set.projection_hints == ("terrain",)
    update = change_set.terrain_updates[0]
    assert update.x == 1
    assert update.y == 0
    assert update.old_biome == "plains"
    assert update.new_biome == "forest"
    assert update.old_elevation == 128
    assert update.new_elevation == 160
    assert update.old_moisture == 128
    assert update.new_moisture == 170
    assert update.old_temperature == 128
    assert update.new_temperature == 90

    record = change_set.events[0]
    assert record.kind == "terrain_cell_mutated"
    assert record.location_id == "loc_origin"
    assert record.summary_key == "events.terrain_cell_mutated.summary"
    assert record.render_params == {
        "terrain_cell_id": "terrain:1:0",
        "x": 1,
        "y": 0,
        "old_biome": "plains",
        "new_biome": "forest",
        "old_elevation": 128,
        "new_elevation": 160,
        "old_moisture": 128,
        "new_moisture": 170,
        "old_temperature": 128,
        "new_temperature": 90,
        "changed_attributes": ["biome", "elevation", "moisture", "temperature"],
        "location_id": "loc_origin",
        "reason_key": "fey_bloom",
    }
    assert record.impacts == [
        {
            "target_type": "terrain_cell",
            "target_id": "terrain:1:0",
            "attribute": "biome",
            "old_value": "plains",
            "new_value": "forest",
        },
        {
            "target_type": "terrain_cell",
            "target_id": "terrain:1:0",
            "attribute": "elevation",
            "old_value": 128,
            "new_value": 160,
        },
        {
            "target_type": "terrain_cell",
            "target_id": "terrain:1:0",
            "attribute": "moisture",
            "old_value": 128,
            "new_value": 170,
        },
        {
            "target_type": "terrain_cell",
            "target_id": "terrain:1:0",
            "attribute": "temperature",
            "old_value": 128,
            "new_value": 90,
        },
    ]
    assert "world_change" in record.tags
    assert "terrain" in record.tags
    assert "terrain_cell:terrain:1:0" in record.tags
    assert "location:loc_origin" in record.tags


def test_terrain_cell_changeset_validates_bounds_biome_and_scalar_ranges() -> None:
    terrain_map = _terrain_map()

    for command, expected_message in [
        (MutateTerrainCellCommand(x=2, y=0, year=1001, biome="forest"), "outside world bounds"),
        (MutateTerrainCellCommand(x=1, y=0, year=1001, biome="unknown"), "unknown terrain biome"),
        (MutateTerrainCellCommand(x=1, y=0, year=1001, moisture=300), "moisture must be between 0 and 255"),
    ]:
        try:
            build_terrain_cell_mutation_change_set(
                command,
                terrain_map=terrain_map,
                allowed_biomes=set(BIOME_TYPES),
                describe=_describe,
            )
        except ValueError as exc:
            assert expected_message in str(exc)
        else:
            raise AssertionError(f"Expected terrain validation to fail: {expected_message}")


def test_terrain_cell_changeset_requires_terrain_map() -> None:
    command = MutateTerrainCellCommand(x=1, y=0, year=1001, biome="forest")

    try:
        build_terrain_cell_mutation_change_set(
            command,
            terrain_map=None,
            allowed_biomes=set(BIOME_TYPES),
            describe=_describe,
        )
    except ValueError as exc:
        assert "terrain_map is required" in str(exc)
    else:
        raise AssertionError("Expected terrain_map validation to fail")


def test_world_change_reducer_applies_terrain_update_and_records_event() -> None:
    terrain_map = _terrain_map()
    records: list[WorldEventRecord] = []
    command = MutateTerrainCellCommand(x=1, y=0, year=1001, biome="forest", elevation=160)
    change_set = build_terrain_cell_mutation_change_set(
        command,
        terrain_map=terrain_map,
        allowed_biomes=set(BIOME_TYPES),
        describe=_describe,
    )
    assert change_set is not None

    stored = apply_world_change_set(
        change_set,
        routes=[],
        terrain_map=terrain_map,
        record_event=lambda record: records.append(record) or record,
    )

    cell = terrain_map.get(1, 0)
    assert cell is not None
    assert cell.biome == "forest"
    assert cell.elevation == 160
    assert stored == tuple(records)
    assert records[0].kind == "terrain_cell_mutated"


def test_world_change_reducer_rolls_back_terrain_update_when_recording_fails() -> None:
    terrain_map = _terrain_map()
    command = MutateTerrainCellCommand(x=1, y=0, year=1001, biome="forest", elevation=160)
    change_set = build_terrain_cell_mutation_change_set(
        command,
        terrain_map=terrain_map,
        allowed_biomes=set(BIOME_TYPES),
        describe=_describe,
    )
    assert change_set is not None

    def _fail_record(_record: WorldEventRecord) -> WorldEventRecord:
        raise ValueError("recording failed")

    try:
        apply_world_change_set(
            change_set,
            routes=[],
            terrain_map=terrain_map,
            record_event=_fail_record,
        )
    except ValueError as exc:
        assert "recording failed" in str(exc)
    else:
        raise AssertionError("Expected recording failure to roll back terrain state")

    cell = terrain_map.get(1, 0)
    assert cell is not None
    assert cell.biome == "plains"
    assert cell.elevation == 128


def test_world_terrain_cell_change_rejects_unknown_or_mismatched_explicit_location_id() -> None:
    world = World()
    assert world.terrain_map is not None
    capital_cell = world.terrain_map.get(2, 2)
    grey_pass_cell = world.terrain_map.get(1, 0)
    assert capital_cell is not None
    assert grey_pass_cell is not None
    assert world.grid[(2, 2)].id == "loc_aethoria_capital"
    assert world.grid[(1, 0)].id == "loc_the_grey_pass"
    capital_payload = capital_cell.to_dict()
    grey_pass_payload = grey_pass_cell.to_dict()

    for location_id in ["loc_missing", "loc_the_grey_pass"]:
        try:
            world.apply_terrain_cell_change(
                2,
                2,
                biome="forest",
                location_id=location_id,
            )
        except (KeyError, ValueError):
            pass
        else:
            raise AssertionError(f"Expected explicit location validation to fail for {location_id}")

    assert capital_cell.to_dict() == capital_payload
    assert grey_pass_cell.to_dict() == grey_pass_payload
    assert world.event_records == []

from __future__ import annotations

from dataclasses import dataclass, field

from fantasy_simulator.world_event.models import WorldEventRecord
from fantasy_simulator.world_core.ids import EraKey, FactionId, LocationId, RouteId
from fantasy_simulator.terrain import RouteEdge, TerrainCell, TerrainMap
from fantasy_simulator.world_change import (
    EraRuntimeUpdate,
    LocationOccupationUpdate,
    LocationRenameUpdate,
    RouteUpdate,
    TerrainCellUpdate,
    WorldChangeSet,
    WorldScoreUpdate,
    apply_world_change_set,
)


@dataclass
class _Location:
    id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    controlling_faction_id: str | None = None


@dataclass
class _EraRuntime:
    era_key: str
    civilization_phase: str
    world_scores: dict[str, int] = field(default_factory=dict)


def _record() -> WorldEventRecord:
    return WorldEventRecord(record_id="rec_stale", kind="test", year=1001, description="Prepared change.")


def _record_event(records: list[WorldEventRecord]):
    return lambda record: records.append(record) or record


def _terrain_map() -> TerrainMap:
    terrain_map = TerrainMap(width=1, height=1)
    terrain_map.set_cell(TerrainCell(x=0, y=0, biome="forest", elevation=128, moisture=128, temperature=128))
    return terrain_map


def test_reducer_rejects_stale_route_update_before_recording_event() -> None:
    route = RouteEdge("route_1", "loc_origin", "loc_destination", blocked=True)
    records: list[WorldEventRecord] = []
    change_set = WorldChangeSet(
        events=(_record(),),
        route_updates=(RouteUpdate(route_id=RouteId(route.route_id), old_blocked=False, new_blocked=True),),
    )

    try:
        apply_world_change_set(change_set, routes=[route], record_event=_record_event(records))
    except ValueError as exc:
        assert "stale route update" in str(exc)
    else:
        raise AssertionError("Expected stale route update to fail")

    assert route.blocked is True
    assert records == []


def test_reducer_rejects_stale_location_rename_update_before_mutation() -> None:
    location = _Location("loc_capital", "Aethoria March", aliases=["Aethoria Capital"])
    location_index = {location.id: location}
    location_name_index = {location.canonical_name: location}
    records: list[WorldEventRecord] = []
    change_set = WorldChangeSet(
        events=(_record(),),
        location_updates=(
            LocationRenameUpdate(
                location_id=LocationId(location.id),
                old_name="Aethoria Capital",
                new_name="Aethoria Harbor",
                old_aliases=(),
                new_aliases=("Aethoria Capital",),
            ),
        ),
    )

    try:
        apply_world_change_set(
            change_set,
            routes=[],
            location_index=location_index,
            location_name_index=location_name_index,
            record_event=_record_event(records),
        )
    except ValueError as exc:
        assert "stale location rename update" in str(exc)
    else:
        raise AssertionError("Expected stale location rename update to fail")

    assert location.canonical_name == "Aethoria March"
    assert location.aliases == ["Aethoria Capital"]
    assert location_name_index == {"Aethoria March": location}
    assert records == []


def test_reducer_rejects_stale_occupation_update_before_mutation() -> None:
    location = _Location("loc_capital", "Aethoria Capital", controlling_faction_id="wardens")
    records: list[WorldEventRecord] = []
    change_set = WorldChangeSet(
        events=(_record(),),
        occupation_updates=(
            LocationOccupationUpdate(
                location_id=LocationId(location.id),
                old_faction_id=None,
                new_faction_id=FactionId("dawn_court"),
            ),
        ),
    )

    try:
        apply_world_change_set(
            change_set,
            routes=[],
            location_index={location.id: location},
            record_event=_record_event(records),
        )
    except ValueError as exc:
        assert "stale location occupation update" in str(exc)
    else:
        raise AssertionError("Expected stale occupation update to fail")

    assert location.controlling_faction_id == "wardens"
    assert records == []


def test_reducer_rejects_stale_terrain_update_before_mutation() -> None:
    terrain_map = _terrain_map()
    records: list[WorldEventRecord] = []
    change_set = WorldChangeSet(
        events=(_record(),),
        terrain_updates=(
            TerrainCellUpdate(
                x=0,
                y=0,
                old_biome="plains",
                new_biome="swamp",
                old_elevation=128,
                new_elevation=80,
                old_moisture=128,
                new_moisture=200,
                old_temperature=128,
                new_temperature=140,
            ),
        ),
    )

    try:
        apply_world_change_set(change_set, routes=[], terrain_map=terrain_map, record_event=_record_event(records))
    except ValueError as exc:
        assert "stale terrain update" in str(exc)
    else:
        raise AssertionError("Expected stale terrain update to fail")

    cell = terrain_map.get(0, 0)
    assert cell is not None
    assert cell.biome == "forest"
    assert cell.elevation == 128
    assert cell.moisture == 128
    assert cell.temperature == 128
    assert records == []


def test_reducer_rejects_stale_era_update_before_mutation() -> None:
    runtime = _EraRuntime(
        era_key="age_of_reckoning",
        civilization_phase="crisis",
        world_scores={"prosperity": 35},
    )
    records: list[WorldEventRecord] = []
    change_set = WorldChangeSet(
        events=(_record(),),
        era_updates=(
            EraRuntimeUpdate(
                old_era_key=EraKey("age_of_embers"),
                new_era_key=EraKey("age_of_reckoning"),
                old_civilization_phase="stable",
                new_civilization_phase="crisis",
                score_updates=(WorldScoreUpdate(score_key="prosperity", old_value=50, new_value=35),),
            ),
        ),
    )

    try:
        apply_world_change_set(change_set, routes=[], era_runtime=runtime, record_event=_record_event(records))
    except ValueError as exc:
        assert "stale era update" in str(exc)
    else:
        raise AssertionError("Expected stale era update to fail")

    assert runtime.era_key == "age_of_reckoning"
    assert runtime.civilization_phase == "crisis"
    assert runtime.world_scores == {"prosperity": 35}
    assert records == []

from __future__ import annotations

import pytest

from fantasy_simulator.ids import (
    CharacterId,
    CultureId,
    EraKey,
    EventRecordId,
    FactionId,
    LocationId,
    RouteId,
    TerrainCellId,
)
import fantasy_simulator.ids as ids
from fantasy_simulator.terrain import BIOME_TYPES
from fantasy_simulator.world import World
from fantasy_simulator.world_change import (
    DeclareWarCommand,
    DriftCivilizationPhaseCommand,
    MutateTerrainCellCommand,
    RenameLocationCommand,
    SetRouteBlockedCommand,
    ShiftEraCommand,
    build_civilization_phase_drift_change_set,
    build_era_shift_change_set,
    build_terrain_cell_mutation_change_set,
    build_war_declaration_change_set,
    build_location_rename_change_set,
    build_route_blocked_change_set,
)


def _describe(_summary_key: str, _render_params: dict, fallback: str) -> str:
    return fallback


def test_pr_k_id_newtypes_are_runtime_strings() -> None:
    assert LocationId("loc_aethoria_capital") == "loc_aethoria_capital"
    assert RouteId("route_1") == "route_1"
    assert FactionId("dawn_court") == "dawn_court"
    assert EventRecordId("evt_1") == "evt_1"
    assert CharacterId("char_1") == "char_1"
    assert EraKey("first_dawn") == "first_dawn"
    assert CultureId("aethorian") == "aethorian"
    assert TerrainCellId("terrain:1:0") == "terrain:1:0"


def test_pr_k_id_exports_are_stable() -> None:
    assert ids.__all__ == [
        "CharacterId",
        "LocationId",
        "RouteId",
        "TerrainCellId",
        "FactionId",
        "EventRecordId",
        "EraKey",
        "CultureId",
    ]


def test_route_command_boundary_normalizes_typed_route_id_before_recording() -> None:
    world = World()
    route = world.routes[0]

    change_set = build_route_blocked_change_set(
        SetRouteBlockedCommand(route_id=RouteId(f"  {route.route_id}  "), blocked=True, year=1001),
        routes=world.routes,
        location_ids=set(world.location_ids),
        location_name=world.location_name,
        describe=_describe,
    )

    assert change_set is not None
    assert change_set.route_updates[0].route_id == route.route_id
    assert change_set.events[0].render_params["route_id"] == route.route_id


def test_location_command_boundary_normalizes_typed_location_id_before_recording() -> None:
    world = World()

    change_set = build_location_rename_change_set(
        RenameLocationCommand(
            location_id=LocationId("  loc_aethoria_capital  "),
            new_name="Aethoria March",
            year=1001,
        ),
        location_index=world._location_id_index,
        location_name_index=world._location_name_index,
        max_aliases=world.MAX_ALIASES,
        describe=_describe,
    )

    assert change_set is not None
    assert change_set.location_updates[0].location_id == "loc_aethoria_capital"
    assert change_set.events[0].location_id == "loc_aethoria_capital"
    assert change_set.events[0].render_params["location_id"] == "loc_aethoria_capital"


def test_blank_typed_route_id_is_rejected_before_lookup() -> None:
    world = World()

    with pytest.raises(ValueError, match="route_id must not be blank"):
        build_route_blocked_change_set(
            SetRouteBlockedCommand(route_id=RouteId("   "), blocked=True, year=1001),
            routes=world.routes,
            location_ids=set(world.location_ids),
            location_name=world.location_name,
            describe=_describe,
        )


def test_war_command_boundary_normalizes_faction_locations_and_cause_event_id() -> None:
    world = World()
    change_set = build_war_declaration_change_set(
        DeclareWarCommand(
            aggressor_faction_id=FactionId("  stormwatch_wardens  "),
            target_faction_id=FactionId("  silverbrook_merchant_league  "),
            location_ids=(LocationId(" loc_aethoria_capital "), LocationId(" loc_aethoria_capital ")),
            year=1001,
            cause_event_id=EventRecordId(" cause-war "),
        ),
        known_faction_ids={"stormwatch_wardens", "silverbrook_merchant_league"},
        location_ids=set(world.location_ids),
        describe=_describe,
    )

    record = change_set.events[0]
    assert record.render_params["aggressor_faction_id"] == "stormwatch_wardens"
    assert record.render_params["target_faction_id"] == "silverbrook_merchant_league"
    assert record.render_params["location_ids"] == ["loc_aethoria_capital"]
    assert record.render_params["cause_event_id"] == "cause-war"


def test_terrain_command_boundary_normalizes_optional_location_and_cause_event_id() -> None:
    world = World()
    assert world.terrain_map is not None

    change_set = build_terrain_cell_mutation_change_set(
        MutateTerrainCellCommand(
            x=2,
            y=2,
            biome="forest",
            year=1001,
            location_id=LocationId(" loc_aethoria_capital "),
            cause_event_id=EventRecordId(" cause-terrain "),
        ),
        terrain_map=world.terrain_map,
        allowed_biomes=BIOME_TYPES,
        describe=_describe,
    )

    assert change_set is not None
    assert change_set.events[0].render_params["location_id"] == "loc_aethoria_capital"
    assert change_set.events[0].render_params["cause_event_id"] == "cause-terrain"


def test_era_and_civilization_boundaries_normalize_era_and_cause_event_ids() -> None:
    runtime = type(
        "Runtime",
        (),
        {
            "era_key": "age_of_embers",
            "civilization_phase": "stable",
            "world_scores": {"prosperity": 50, "safety": 50, "traffic": 50, "mood": 50},
        },
    )()

    era_change_set = build_era_shift_change_set(
        ShiftEraCommand(
            new_era_key=EraKey(" age_of_reckoning "),
            new_civilization_phase="new_era",
            year=1001,
            cause_event_id=EventRecordId(" cause-era "),
        ),
        era_runtime=runtime,
        authored_era_keys={"age_of_embers", "age_of_reckoning"},
        describe=_describe,
    )
    assert era_change_set is not None
    assert era_change_set.events[0].render_params["new_era_key"] == "age_of_reckoning"
    assert era_change_set.events[0].render_params["cause_event_id"] == "cause-era"

    drift_change_set = build_civilization_phase_drift_change_set(
        DriftCivilizationPhaseCommand(
            new_phase="crisis",
            year=1002,
            score_deltas={"mood": -5},
            cause_event_id=EventRecordId(" cause-civilization "),
        ),
        era_runtime=runtime,
        describe=_describe,
    )
    assert drift_change_set is not None
    assert drift_change_set.events[0].render_params["cause_event_id"] == "cause-civilization"

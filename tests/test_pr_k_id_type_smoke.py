from __future__ import annotations

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

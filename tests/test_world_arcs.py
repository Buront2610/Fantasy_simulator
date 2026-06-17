from __future__ import annotations

import json

from fantasy_simulator.persistence.migrations import _migrate_v8_to_v9
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.simulation.world_change_driver import generate_war_arc_pulse
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


class BattlePulseRng:
    def choice(self, values):
        return list(values)[0]

    def random(self) -> float:
        return 0.95

    def getrandbits(self, _bits: int) -> int:
        return 12345


def test_war_declaration_creates_persistent_world_arc_and_roundtrips(tmp_path) -> None:
    world = World()
    declared = world.apply_war_declaration(
        "stormwatch_wardens",
        "silverbrook_merchant_league",
        location_ids=("loc_aethoria_capital", "loc_silverbrook"),
        month=2,
        day=3,
    )

    assert len(world.world_arcs) == 1
    arc = world.world_arcs[0]
    assert arc.kind == "war"
    assert arc.phase == "active"
    assert arc.cause_event_id == declared.record_id
    assert arc.related_event_ids == [declared.record_id]
    assert arc.location_ids == ("loc_aethoria_capital", "loc_silverbrook")
    assert [(record.cause_key, record.cause_event_id) for record in world.language_evolution_history] == [
        ("war_declared", declared.record_id)
    ]

    path = tmp_path / "world-arc-roundtrip.json"
    assert save_simulation(Simulator(world, seed=0), str(path)) is True
    restored = load_simulation(str(path))

    assert restored is not None
    assert [item.to_dict() for item in restored.world.world_arcs] == [arc.to_dict()]


def test_war_arc_pulse_records_battle_with_cause_link_and_pressure() -> None:
    world = World()
    declared = world.apply_war_declaration(
        "stormwatch_wardens",
        "silverbrook_merchant_league",
        location_ids=("loc_aethoria_capital", "loc_silverbrook"),
        month=2,
        day=3,
    )
    location = world.get_location_by_id("loc_aethoria_capital")
    assert location is not None
    before = (location.danger, location.rumor_heat, location.safety, location.mood, location.road_condition)

    battle = generate_war_arc_pulse(world, month=3, day=4, rng=BattlePulseRng())

    assert battle is not None
    assert battle.kind == "war_battle"
    assert battle.render_params["cause_event_id"] == declared.record_id
    assert battle.render_params["combat_log"]
    assert {"round_number", "dice", "skill_key", "damage"} <= set(battle.render_params["combat_log"][0])
    assert battle.render_params["winner_faction_id"] in {
        "stormwatch_wardens",
        "silverbrook_merchant_league",
    }
    assert battle.record_id in world.world_arcs[0].related_event_ids
    assert world.world_arcs[0].related_event_ids == [declared.record_id, battle.record_id]
    assert "war" in battle.tags
    assert "battle" in battle.tags
    assert location.danger > before[0]
    assert location.rumor_heat > before[1]
    assert location.safety < before[2]
    assert location.mood < before[3]
    assert location.road_condition < before[4]
    assert [(record.cause_key, record.cause_event_id) for record in world.language_evolution_history] == [
        ("war_declared", declared.record_id),
        ("war_battle", battle.record_id),
    ]


def test_v8_to_v9_migration_reconstructs_war_arcs_from_event_records() -> None:
    world = World()
    declared = world.apply_war_declaration(
        "stormwatch_wardens",
        "silverbrook_merchant_league",
        location_ids=("loc_aethoria_capital", "loc_silverbrook"),
        month=2,
        day=3,
    )
    ended = world.apply_war_ended(
        "silverbrook_merchant_league",
        "stormwatch_wardens",
        location_ids=("loc_silverbrook", "loc_aethoria_capital"),
        month=4,
        day=5,
        cause_event_id=declared.record_id,
    )
    payload = {
        "schema_version": 8,
        "characters": [],
        "world": {
            "event_records": [record.to_dict() for record in world.event_records],
        },
    }

    migrated = _migrate_v8_to_v9(json.loads(json.dumps(payload)))

    assert migrated["schema_version"] == 9
    assert len(migrated["world"]["world_arcs"]) == 1
    arc = migrated["world"]["world_arcs"][0]
    assert arc["phase"] == "resolved"
    assert arc["cause_event_id"] == declared.record_id
    assert arc["related_event_ids"] == [declared.record_id, ended.record_id]

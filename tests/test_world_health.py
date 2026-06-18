from __future__ import annotations

from fantasy_simulator.adventure import AdventureRun
from fantasy_simulator.character import Character
from fantasy_simulator.death_resolution import mark_character_dead
from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.testing.world_metrics import (
    assert_population_floor,
    assert_no_dangling_adventure_members,
    assert_no_stranded_living_adventurers,
    collect_world_health_metrics,
)
from fantasy_simulator.world import World


def _make_character(name: str) -> Character:
    return Character(
        name=name,
        age=25,
        gender="Male",
        race="Human",
        job="Warrior",
        location_id="loc_aethoria_capital",
    )


def test_world_health_detects_no_stranded_survivors_after_party_member_death() -> None:
    world = World()
    leader = _make_character("Leader")
    companion = _make_character("Companion")
    world.add_character(leader)
    world.add_character(companion)
    run = AdventureRun(
        character_id=leader.char_id,
        character_name=leader.name,
        origin=leader.location_id,
        destination="loc_thornwood",
        year_started=world.year,
        state="exploring",
        member_ids=[leader.char_id, companion.char_id],
    )
    leader.active_adventure_id = run.adventure_id
    companion.active_adventure_id = run.adventure_id
    world.add_adventure(run)

    mark_character_dead(companion, world)

    assert run.death_member_id == companion.char_id
    assert leader.active_adventure_id is None
    assert companion.active_adventure_id is None
    assert_no_stranded_living_adventurers(world)
    assert_no_dangling_adventure_members(world)


def test_world_health_metrics_are_headless_and_serializable() -> None:
    world = World()
    world.add_character(_make_character("Observer"))

    metrics = collect_world_health_metrics(world)

    assert metrics["characters"] == 1
    assert metrics["stranded_living_adventurers"] == []
    assert metrics["marriage_count"] == 0
    assert metrics["birth_count"] == 0
    assert metrics["combat_event_count"] == 0
    assert metrics["event_record_count"] == 0
    assert metrics["event_records_json_bytes"] > 0
    assert metrics["rumor_archive_count"] == 0
    assert metrics["estimated_world_save_json_bytes"] > 0


def test_world_health_metrics_include_combat_statistics() -> None:
    world = World()
    cause = WorldEventRecord(record_id="war-start", kind="war_declared", description="A war started.")
    world.event_records.append(
        cause
    )
    world.event_records.append(
        WorldEventRecord(
            record_id="war-battle",
            kind="war_battle",
            description="A battle happened.",
            render_params={
                "cause_event_id": cause.record_id,
                "combat_log": [
                    {"round_number": 1, "action_kind": "weapon_attack", "damage": 2},
                    {"round_number": 2, "action_kind": "spell_attack", "damage": 4},
                ]
            },
        )
    )
    world.event_records.append(WorldEventRecord(kind="birth", description="A child was born."))

    metrics = collect_world_health_metrics(world)

    assert metrics["combat_event_count"] == 1
    assert metrics["combat_round_count"] == 2
    assert metrics["average_combat_rounds"] == 2.0
    assert metrics["magic_combat_action_count"] == 1
    assert metrics["war_battle_count"] == 1
    assert metrics["adventure_combat_count"] == 0
    assert metrics["birth_count"] == 1
    assert metrics["causal_event_count"] == 1
    assert metrics["dangling_cause_event_ids"] == []
    assert metrics["event_record_count"] == 3
    assert metrics["event_records_json_bytes"] > metrics["active_rumors_json_bytes"]


def test_world_health_metrics_report_dangling_cause_event_ids() -> None:
    world = World()
    world.event_records.append(
        WorldEventRecord(
            record_id="orphan-effect",
            kind="war_ended",
            render_params={"cause_event_id": "missing-cause"},
        )
    )

    metrics = collect_world_health_metrics(world)

    assert metrics["causal_event_count"] == 1
    assert metrics["dangling_cause_event_ids"] == [
        {
            "record_id": "orphan-effect",
            "kind": "war_ended",
            "cause_event_id": "missing-cause",
        }
    ]


def test_world_health_metrics_include_adventure_combat_statistics() -> None:
    world = World()
    leader = _make_character("Leader")
    world.add_character(leader)
    run = AdventureRun(
        character_id=leader.char_id,
        character_name=leader.name,
        origin=leader.location_id,
        destination="loc_thornwood",
        year_started=world.year,
        state="resolved",
        combat_logs=[
            {
                "location_id": "loc_thornwood",
                "combat_log": [
                    {"round_number": 1, "action_kind": "weapon_attack", "damage": 1},
                    {"round_number": 2, "action_kind": "spell_attack", "damage": 3},
                ],
            },
        ],
    )
    world.completed_adventures.append(run)

    metrics = collect_world_health_metrics(world)

    assert metrics["combat_event_count"] == 1
    assert metrics["combat_round_count"] == 2
    assert metrics["magic_combat_action_count"] == 1
    assert metrics["adventure_combat_count"] == 1
    assert metrics["war_battle_count"] == 0


def test_world_health_population_floor_assertion() -> None:
    world = World()
    for index in range(3):
        world.add_character(_make_character(f"Observer{index}"))

    assert_population_floor(world, minimum_alive=3)

from __future__ import annotations

from fantasy_simulator.adventure import AdventureRun
from fantasy_simulator.character import Character
from fantasy_simulator.combat_system.log_index import build_combat_log_index
from fantasy_simulator.world_event.models import WorldEventRecord
from fantasy_simulator.world import World


def _combat_round(actor_id: str, target_id: str) -> dict:
    return {
        "round_number": 1,
        "actor_id": actor_id,
        "actor_name": actor_id.title(),
        "target_id": target_id,
        "target_name": target_id.title(),
        "action_kind": "weapon_attack",
        "skill_key": "Swordsmanship",
        "dice": 12,
        "modifier": 5,
        "attack_total": 17,
        "defense_total": 11,
        "damage": 4,
        "outcome": "decisive",
    }


def test_combat_log_index_collects_event_and_adventure_combat() -> None:
    world = World()
    hero = Character("Aldric", 25, "Male", "Human", "Warrior", char_id="hero")
    world.add_character(hero)
    world.record_event(
        WorldEventRecord(
            record_id="battle_1",
            kind="battle",
            year=1001,
            primary_actor_id="hero",
            secondary_actor_ids=["rival"],
            description="Aldric fought a rival.",
            render_params={"combat_log": [_combat_round("hero", "rival")]},
        )
    )
    run = AdventureRun(
        character_id=hero.char_id,
        character_name=hero.name,
        origin="loc_aethoria_capital",
        destination="loc_thornwood",
        year_started=1002,
    )
    run.combat_logs.append({
        "member_id": hero.char_id,
        "member_name": hero.name,
        "hazard_id": "hazard:1",
        "hazard_name": "forest warden",
        "combat_log": [_combat_round("hero", "hazard:1")],
    })
    world.complete_adventure(run.adventure_id)
    world.completed_adventures.append(run)

    entries = build_combat_log_index(world)
    hero_entries = build_combat_log_index(world, character_id="hero")
    missing_entries = build_combat_log_index(world, character_id="missing")

    assert [entry.source_kind for entry in entries] == ["adventure_combat", "battle"]
    assert len(hero_entries) == 2
    assert missing_entries == ()

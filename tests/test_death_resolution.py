from __future__ import annotations

from fantasy_simulator.adventure import AdventureRun
from fantasy_simulator.character import Character
from fantasy_simulator.death_resolution import (
    handle_death_side_effects,
    mark_character_dead,
    resolve_active_adventure_for_death,
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


def test_handle_death_side_effects_clears_surviving_spouse_once() -> None:
    world = World()
    hero = _make_character("Hero")
    spouse = _make_character("Spouse")
    world.add_character(hero)
    world.add_character(spouse)
    hero.spouse_id = spouse.char_id
    spouse.spouse_id = hero.char_id
    hero.alive = False

    handle_death_side_effects(hero, world)
    history_len = len(spouse.history)
    handle_death_side_effects(hero, world)

    assert spouse.spouse_id is None
    assert len(spouse.history) == history_len


def test_resolve_active_adventure_for_death_completes_unresolved_run() -> None:
    world = World()
    hero = _make_character("Hero")
    world.add_character(hero)
    run = AdventureRun(
        character_id=hero.char_id,
        character_name=hero.name,
        origin=hero.location_id,
        destination="loc_thornwood",
        year_started=world.year,
        state="exploring",
    )
    hero.active_adventure_id = run.adventure_id
    world.add_adventure(run)

    resolve_active_adventure_for_death(hero, world)

    assert hero.active_adventure_id is None
    assert world.active_adventures == []
    assert world.completed_adventures == [run]
    assert run.state == "resolved"
    assert run.outcome == "death"
    assert run.resolution_year == world.year
    assert run.pending_choice is None


def test_mark_character_dead_applies_common_death_state() -> None:
    world = World()
    hero = _make_character("Hero")
    spouse = _make_character("Spouse")
    world.add_character(hero)
    world.add_character(spouse)
    hero.spouse_id = spouse.char_id
    spouse.spouse_id = hero.char_id

    mark_character_dead(hero, world)

    assert hero.alive is False
    assert hero.active_adventure_id is None
    assert spouse.spouse_id is None

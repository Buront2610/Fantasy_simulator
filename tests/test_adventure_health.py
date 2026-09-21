"""Health consequences must agree with combat evidence and current Character state."""

import random

import pytest

from fantasy_simulator.adventure import AdventureRun
from fantasy_simulator.adventure.hazards import resolve_critical_hazard, resolve_hazard_band
from fantasy_simulator.character import Character
from fantasy_simulator.character_model.death_resolution import mark_character_dead
from fantasy_simulator.events import EventSystem
from fantasy_simulator.i18n import tr
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.simulation import Simulator
from fantasy_simulator.world import World


def make_run(*, skills=None, danger=90):
    world = World()
    hero = Character(name="Hero", char_id="hero", age=25, gender="Male", race="Human", job="Warrior",
                     strength=60, dexterity=50, constitution=55, location_id="loc_aethoria_capital",
                     skills=skills or {})
    world.add_character(hero)
    run = AdventureRun(character_id=hero.char_id, character_name=hero.name, origin=hero.location_id,
                       destination="loc_thornwood", year_started=world.year, danger_level=danger,
                       adventure_id="health-regression", state="exploring")
    return world, hero, run


@pytest.mark.parametrize("critical", [False, True])
def test_unharmed_encounter_does_not_worsen_health_or_claim_injury(critical):
    world, hero, run = make_run(skills={"Shield Block": 10})
    hero.dexterity = hero.constitution = 100
    resolve = resolve_critical_hazard if critical else resolve_hazard_band
    args = (run, hero, world, random.Random(0), "Thornwood")
    if not critical:
        args = (run, hero, hero, world, random.Random(0), "Thornwood")
    result = resolve(*args)
    assert run.combat_logs[-1]["damage_taken"] == 0
    assert hero.injury_status == "none"
    assert run.injury_status == "none"
    assert run.injury_member_id is None
    assert result.summaries == (tr("summary_adventure_hazard_unharmed", name=hero.name, destination="Thornwood"),)
    assert AdventureRun.from_dict(run.to_dict()).combat_logs == run.combat_logs


@pytest.mark.parametrize("current", ["none", "injured", "serious", "dying"])
@pytest.mark.parametrize("saved", [False, True])
def test_return_uses_current_health_without_reapplying_old_dying_state(current, saved, tmp_path):
    world, hero, run = make_run()
    run.state, run.injury_status, run.injury_member_id = "returning", "dying", hero.char_id
    hero.injury_status = current
    hero.active_adventure_id = run.adventure_id
    if saved:
        world.add_adventure(run)
        path = str(tmp_path / "return.json")
        assert save_simulation(Simulator(world, seed=0), path)
        restored = load_simulation(path)
        assert restored is not None
        world = restored.world
        hero = world.get_character_by_id(hero.char_id)
        run = world.get_adventure_by_id(run.adventure_id)
    run.step(hero, world, random.Random(0))
    assert hero.alive
    assert hero.injury_status == current
    assert run.injury_status == current
    assert run.outcome == ("retreat" if current == "none" else "injury")
    assert hero.active_adventure_id is None
    assert run.step(hero, world, random.Random(0)) == []


def test_actual_rescue_then_return_preserves_rescue_and_life():
    world, hero, run = make_run()
    hero.injury_status = "dying"
    run.injury_status, run.injury_member_id, run.state = "dying", hero.char_id, "returning"
    result = EventSystem().check_dying_resolution(hero, world, rng=random.Random(1))
    assert result.event_type == "dying_rescued"
    assert hero.injury_status == "serious"
    run.step(hero, world)
    assert hero.alive and hero.injury_status == "serious"
    assert run.outcome == "injury"


def test_return_records_current_injury_of_companion_even_when_run_names_leader():
    world, leader, run = make_run()
    companion = Character(name="Companion", char_id="companion", age=25, gender="Female", race="Human",
                          job="Warrior", injury_status="serious", location_id=leader.location_id)
    world.add_character(companion)
    run.member_ids = [leader.char_id, companion.char_id]
    run.state, run.injury_status, run.injury_member_id = "returning", "dying", leader.char_id
    run.step(leader, world)
    assert leader.alive and leader.injury_status == "none"
    assert companion.injury_status == "serious"
    assert run.injury_member_id == companion.char_id
    assert run.outcome == "injury"


def test_direct_adventure_death_cleans_spouse_once():
    world, hero, run = make_run()
    spouse = Character(name="Spouse", char_id="spouse", age=25, gender="Female", race="Human", job="Warrior")
    world.add_character(spouse)
    hero.spouse_id, spouse.spouse_id = spouse.char_id, hero.char_id
    hero.injury_status = "dying"
    hero.active_adventure_id = run.adventure_id
    resolve_hazard_band(run, hero, hero, world, random.Random(0), "Thornwood")
    assert not hero.alive and spouse.spouse_id is None
    history = list(spouse.history)
    mark_character_dead(hero, world)
    assert spouse.history == history


def test_defensive_training_reduces_damage_and_injuries_across_fixed_seeds():
    totals = []
    for skills in ({}, {"Shield Block": 10}):
        damage = injuries = 0
        world, initial_hero, initial_run = make_run(skills=skills)
        for seed in range(32):
            hero = Character.from_dict(initial_hero.to_dict())
            run = AdventureRun.from_dict(initial_run.to_dict())
            resolve_critical_hazard(run, hero, world, random.Random(seed), "Thornwood")
            damage += run.combat_logs[-1]["damage_taken"]
            injuries += hero.injury_status != "none"
        totals.append((damage, injuries))
    assert totals[1][0] < totals[0][0], totals
    assert totals[1][1] < totals[0][1], totals


@pytest.mark.parametrize("unharmed", [False, True])
def test_simulator_records_actual_companion_and_damage_outcome(unharmed):
    world, leader, run = make_run()
    companion = Character.from_dict({**leader.to_dict(), "char_id": "companion", "name": "Companion"})
    if unharmed:
        companion.dexterity = companion.constitution = 100
        companion.skills = {"Shield Block": 10}
    world.add_character(companion)
    run.member_ids = [leader.char_id, companion.char_id]
    world.add_adventure(run)
    for member in (leader, companion):
        member.active_adventure_id = run.adventure_id

    class EncounterRng(random.Random):
        def __init__(self, seed):
            super().__init__(seed)
            self.combat_rng = random.Random(seed)

        def random(self):
            return 0.01

        def randint(self, lo, hi):
            return self.combat_rng.randint(lo, hi)

        def choice(self, sequence):
            return companion if companion in sequence else sequence[0]

    sim = Simulator(world, seed=0)
    sim.rng = EncounterRng(0)
    sim._advance_adventures(steps=1)
    record = world.event_records[-1]
    assert record.primary_actor_id == companion.char_id
    assert record.kind == ("adventure_encounter" if unharmed else "adventure_injured")
    assert (run.combat_logs[-1]["damage_taken"] == 0) == unharmed
    assert leader.injury_status == "none"

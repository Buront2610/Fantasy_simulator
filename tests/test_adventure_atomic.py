"""Failure injection across adventure planning, recording, completion and retry."""

from copy import deepcopy
import random

import pytest

from fantasy_simulator.adventure import AdventureChoice, AdventureRun, CHOICE_PRESS_ON, RETREAT_NEVER
from fantasy_simulator.character import Character
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.simulation import Simulator
from fantasy_simulator.simulation.adventure_transition import apply_adventure_transition
from fantasy_simulator.world import World


@pytest.fixture
def sim():
    world = World()
    for name in ("hero", "companion", "spouse"):
        world.add_character(Character(
            name=name.title(), char_id=name, age=25, gender="Male", race="Human", job="Warrior",
            location_id="loc_aethoria_capital",
        ))
    return Simulator(world, seed=7)


def add_run(sim, *, state="exploring", fatal=False):
    hero, companion, spouse = sim.world.characters
    run = AdventureRun(
        character_id=hero.char_id, character_name=hero.name, origin=hero.location_id,
        destination="loc_thornwood", year_started=sim.world.year, adventure_id="atomic", state=state,
        member_ids=[hero.char_id, companion.char_id],
    )
    sim.world.add_adventure(run)
    hero.active_adventure_id = companion.active_adventure_id = run.adventure_id
    if fatal:
        companion.alive = False
        companion.spouse_id, spouse.spouse_id = spouse.char_id, companion.char_id
    return run


def snapshot(sim):
    return deepcopy({
        "save": sim.to_dict(),
        "notifications": [record.to_dict() for record in sim.pending_notifications],
        "completed": [run.to_dict() for run in sim._recently_completed_adventures],
        "memorial_history": sim.memorial_template_history.to_dict(),
        "alias_history": sim.alias_template_history.to_dict(),
    })


def fail_after(original):
    def failing(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("injected after mutation")
    return failing


@pytest.mark.parametrize("retention", [False, True])
def test_record_failure_restores_state_indexes_rng_and_deterministic_retry(sim, monkeypatch, retention):
    run = add_run(sim)
    if retention:
        monkeypatch.setattr(sim.world, "MAX_EVENT_RECORDS", 2)
        for _ in range(2):
            sim._record_world_event("existing", kind="aging", location_id="loc_elderroot_forest",
                                    primary_actor_id="spouse")
    before = snapshot(sim)
    original_run, original_hero = run, sim.world.characters[0]
    original_location = sim.world.get_location_by_id(run.destination)
    original_rng, original_id_rng = sim.rng, sim.id_rng
    sim.world.get_events_by_actor("spouse")  # Prime the read index before the failed append.
    record = sim.world.record_event

    def failing_record(event):
        result = record(event)
        assert sim.world.get_event_by_id(result.record_id) is not None
        raise RuntimeError("record failure after index rebuild")

    with monkeypatch.context() as patch:
        patch.setattr(sim.world, "record_event", failing_record)
        with pytest.raises(RuntimeError, match="record failure"):
            sim._advance_adventures(steps=1)
    assert snapshot(sim) == before
    assert sim.world.get_adventure_by_id(run.adventure_id) is original_run
    assert sim.world.get_character_by_id("hero") is original_hero
    assert sim.world.get_location_by_id(run.destination) is original_location
    assert sim.rng is original_rng and sim.id_rng is original_id_rng
    assert [event.record_id for event in sim.world.get_events_by_actor("spouse")] == [
        event["record_id"] for event in before["save"]["world"]["event_records"]
    ]
    control = Simulator.from_dict(deepcopy(before["save"]))
    if retention:
        control.world.MAX_EVENT_RECORDS = 2
    sim._advance_adventures(steps=1)
    control._advance_adventures(steps=1)
    assert snapshot(sim) == snapshot(control)


@pytest.mark.parametrize("fault", ["notify", "memory", "complete"])
def test_fatal_return_failure_restores_spouse_memory_completion_and_save(sim, monkeypatch, tmp_path, fault):
    run = add_run(sim, state="returning", fatal=True)
    before = snapshot(sim)
    hook = {"notify": "_record_world_event", "memory": "_apply_world_memory",
            "complete": "_complete_resolved_adventure"}[fault]
    with monkeypatch.context() as patch:
        patch.setattr(sim, hook, fail_after(getattr(sim, hook)))
        with pytest.raises(RuntimeError, match="injected"):
            sim._advance_adventures(steps=1)
    assert snapshot(sim) == before
    assert sim.world.get_character_by_id("spouse").spouse_id == "companion"
    assert sim.world.get_adventure_by_id(run.adventure_id) is run
    path = str(tmp_path / "rolled-back.json")
    assert save_simulation(sim, path)
    loaded = load_simulation(path)
    assert loaded is not None
    sim._advance_adventures(steps=1)
    loaded._advance_adventures(steps=1)
    assert sim.to_dict() == loaded.to_dict()
    assert sim.world.get_character_by_id("spouse").spouse_id is None
    assert len(sim.world.memorials) == 1
    assert len(sim.world.completed_adventures) == 1
    after = snapshot(sim)
    sim._advance_adventures(steps=1)
    assert snapshot(sim) == after


def test_planning_failure_cannot_mutate_live_party_or_rng(sim, monkeypatch):
    run = add_run(sim)
    before = snapshot(sim)

    def broken_step(draft_run, character, world, rng):
        assert draft_run is not run
        assert character is not sim.world.get_character_by_id(character.char_id)
        character.strength += 50
        draft_run.state = "resolved"
        rng.random()
        raise RuntimeError("planning failure")

    monkeypatch.setattr(AdventureRun, "step_result", broken_step)
    with pytest.raises(RuntimeError, match="planning failure"):
        sim._advance_adventures(steps=1)
    assert snapshot(sim) == before


@pytest.mark.parametrize("method", ["_start_solo_adventure", "_start_party_adventure", "_maybe_start_adventure"])
def test_failed_start_restores_planning_rng_members_and_history(sim, monkeypatch, method):
    sim.rng = random.Random(1)
    before = snapshot(sim)
    args = [] if method == "_maybe_start_adventure" else [sim.world.characters]
    with monkeypatch.context() as patch:
        patch.setattr(sim, "_record_world_event", fail_after(sim._record_world_event))
        with pytest.raises(RuntimeError, match="injected"):
            getattr(sim, method)(*args)
    assert snapshot(sim) == before
    control = Simulator.from_dict(deepcopy(before["save"]))
    getattr(sim, method)(*args)
    control_args = [] if method == "_maybe_start_adventure" else [control.world.characters]
    getattr(control, method)(*control_args)
    assert snapshot(sim) == snapshot(control)


def test_fatal_encounter_can_rollback_death_and_retry_without_duplicate_memorial(sim, monkeypatch):
    run = add_run(sim)
    companion, spouse = sim.world.characters[1:]
    companion.spouse_id, spouse.spouse_id = spouse.char_id, companion.char_id
    companion.injury_status = "dying"
    run.retreat_rule = RETREAT_NEVER
    sim.rng = random.Random(4)
    before = snapshot(sim)
    with monkeypatch.context() as patch:
        patch.setattr(sim, "_complete_resolved_adventure", fail_after(sim._complete_resolved_adventure))
        with pytest.raises(RuntimeError, match="injected"):
            sim._advance_adventures(steps=1)
    assert snapshot(sim) == before
    assert companion.alive and spouse.spouse_id == companion.char_id
    sim._advance_adventures(steps=1)
    assert not companion.alive and spouse.spouse_id is None
    assert run.outcome == "death" and run.death_member_id == companion.char_id
    assert len(sim.world.memorials) == len(sim.world.completed_adventures) == 1


def test_choice_failure_preserves_pending_choice_and_can_retry_once(sim, monkeypatch):
    run = add_run(sim, state="waiting_for_choice")
    run.pending_choice = AdventureChoice("prompt", [CHOICE_PRESS_ON], CHOICE_PRESS_ON, "approach")
    before = snapshot(sim)
    with monkeypatch.context() as patch:
        patch.setattr(sim, "_record_world_event", fail_after(sim._record_world_event))
        with pytest.raises(RuntimeError, match="injected"):
            sim.resolve_adventure_choice(run.adventure_id, CHOICE_PRESS_ON)
    assert snapshot(sim) == before
    assert sim.resolve_adventure_choice(run.adventure_id, CHOICE_PRESS_ON)
    assert not sim.resolve_adventure_choice(run.adventure_id, CHOICE_PRESS_ON)
    assert len(sim.world.event_records) == 1


@pytest.mark.parametrize("invalid", ["unknown_member", "duplicate_member", "other_run", "unknown_location"])
def test_invalid_references_are_rejected_before_rng_or_state_changes(sim, invalid):
    run = add_run(sim)
    if invalid == "unknown_member":
        run.member_ids.append("missing")
    elif invalid == "duplicate_member":
        run.member_ids.append("hero")
    elif invalid == "other_run":
        sim.world.get_character_by_id("companion").active_adventure_id = "other"
    else:
        run.destination = "missing"
    rng_state, id_state, run_state = sim.rng.getstate(), sim.id_rng.getstate(), run.to_dict()
    with pytest.raises(ValueError):
        apply_adventure_transition(sim, run)
    assert (sim.rng.getstate(), sim.id_rng.getstate(), run.to_dict()) == (rng_state, id_state, run_state)
    assert not sim.world.event_records


def test_scripted_rng_constructor_and_extra_state_survive_failure(sim, monkeypatch):
    class ScriptedRng(random.Random):
        def __init__(self, seed):
            super().__init__(seed)
            self.draws = 0

        def random(self):
            self.draws += 1
            return super().random()

    add_run(sim)
    sim.rng = ScriptedRng(7)
    before = sim.rng.getstate()
    with monkeypatch.context() as patch:
        patch.setattr(sim, "_record_world_event", fail_after(sim._record_world_event))
        with pytest.raises(RuntimeError):
            sim._advance_adventures(steps=1)
    assert sim.rng.getstate() == before and sim.rng.draws == 0
    sim._advance_adventures(steps=1)
    assert sim.rng.draws > 0


def test_step_does_not_clone_unrelated_world_state(sim, monkeypatch):
    add_run(sim)

    def reject_world_copy(*_args):
        raise AssertionError("Adventure must not clone the whole World")

    monkeypatch.setattr(World, "__deepcopy__", reject_world_copy, raising=False)
    sim._advance_adventures(steps=1)


def test_start_rejects_detached_character_before_any_live_mutation(sim):
    detached = Character.from_dict(sim.world.characters[0].to_dict())
    before = snapshot(sim)
    with pytest.raises(ValueError, match="live world character"):
        sim._start_solo_adventure([detached])
    assert snapshot(sim) == before
    assert detached.active_adventure_id is None

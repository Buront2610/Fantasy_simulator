"""Timing, cumulative resource costs, save continuity and atomic scheduled choices."""

from copy import deepcopy
from random import Random

import pytest

from fantasy_simulator.adventure import AdventureChoice, AdventureRun
from fantasy_simulator.adventure.schedule import AdventureSchedule
from fantasy_simulator.character import Character
from fantasy_simulator.simulation import Simulator
from fantasy_simulator.world import World
from fantasy_simulator.world_event.rendering import render_event_record


@pytest.fixture
def simulation():
    world = World()
    hero = Character(name="Scheduled", age=25, gender="Male", race="Human", job="Warrior",
                     location_id="loc_aethoria_capital", char_id="hero")
    world.add_character(hero)
    sim = Simulator(world, seed=37, adventure_steps_per_year=36)
    run = AdventureRun(
        character_id=hero.char_id, character_name=hero.name, origin=hero.location_id,
        destination="loc_thornwood", year_started=world.year, adventure_id="scheduled",
        schedule=AdventureSchedule.begin(1, 10, 1),
    )
    hero.active_adventure_id = run.adventure_id
    world.add_adventure(run)
    return sim, run, hero


def waiting(run):
    run.state = "waiting_for_choice"
    run.pending_choice = AdventureChoice("approach", ["press_on", "proceed_cautiously", "retreat"],
                                         "proceed_cautiously", "approach")


def test_due_dates_are_individual_and_idle_days_do_not_draw_rng(simulation):
    sim, run, hero = simulation
    before = sim.rng.getstate()
    for day in range(10):
        sim.elapsed_days = day
        sim._advance_scheduled_adventures()
    assert run.steps_taken == 0
    assert sim.rng.getstate() == before
    sim.elapsed_days = 10
    sim._advance_scheduled_adventures()
    assert run.steps_taken == 1
    assert run.schedule.next_step_tick > 11
    assert run.schedule.provisions == 50
    sim._advance_scheduled_adventures()
    assert run.steps_taken == 1


def test_choice_changes_next_segment_time_risk_and_supplies_then_expires(simulation):
    sim, run, hero = simulation
    waiting(run)
    payload = sim.to_dict()
    outcomes = {}
    for choice in ("proceed_cautiously", "press_on"):
        branch = Simulator.from_dict(deepcopy(payload))
        active = branch.world.get_adventure_by_id(run.adventure_id)
        member = branch.world.get_character_by_id(hero.char_id)
        assert branch.resolve_adventure_choice(run.adventure_id, choice)
        risk = active._compute_injury_chance([member])
        discovery = active._compute_loot_chance([member])
        due = active.schedule.next_step_tick
        branch.elapsed_days = due - 1
        branch._advance_scheduled_adventures()
        assert active.schedule.segment_mode == "standard"
        outcomes[choice] = due, risk, discovery, active.schedule.provisions
    cautious, swift = outcomes.values()
    assert cautious[0] > swift[0]
    assert cautious[1] < swift[1]
    assert cautious[2] > swift[2]
    assert cautious[3] < swift[3]


def test_save_reload_mid_segment_preserves_due_day_and_rng(simulation):
    sim, run, _ = simulation
    waiting(run)
    sim.resolve_adventure_choice(run.adventure_id, "proceed_cautiously")
    sim.elapsed_days = 4
    restored = Simulator.from_dict(deepcopy(sim.to_dict()))
    assert restored.to_dict() == sim.to_dict()
    for day in range(4, 25):
        for branch in (sim, restored):
            branch.elapsed_days = day
            branch._advance_scheduled_adventures()
        assert sim.to_dict() == restored.to_dict()


@pytest.mark.parametrize("limit", ["deadline", "supplies"])
def test_limits_force_return_and_clear_pending_choice(simulation, limit):
    sim, run, _ = simulation
    waiting(run)
    run.schedule.next_step_tick = 11
    if limit == "deadline":
        run.schedule.deadline_tick = 11
    else:
        run.schedule.provisions = 5
    sim.elapsed_days = 10
    sim._advance_scheduled_adventures()
    assert run.state == "returning"
    assert run.pending_choice is None
    assert sim.world.event_records[-1].render_params["limit"] == limit
    record = sim.world.event_records[-1]
    record.render_params["reason"] = "stale reason"
    assert "stale reason" not in render_event_record(record, locale="en", strict=True)
    assert "stale reason" not in render_event_record(record, locale="ja", strict=True)
    sim.elapsed_days = run.schedule.next_step_tick - 1
    sim._advance_scheduled_adventures()
    assert run.is_resolved


def test_scheduled_failure_restores_clock_supplies_rng_and_retry(simulation, monkeypatch):
    sim, run, _ = simulation
    sim.elapsed_days = 10
    before = deepcopy(sim.to_dict())
    record = sim._record_adventure_step_result

    def fail(*args):
        record(*args)
        raise RuntimeError("after scheduled fact")

    with monkeypatch.context() as patch:
        patch.setattr(sim, "_record_adventure_step_result", fail)
        with pytest.raises(RuntimeError, match="scheduled fact"):
            sim._advance_scheduled_adventures()
    assert sim.to_dict() == before
    control = Simulator.from_dict(deepcopy(before))
    sim._advance_scheduled_adventures()
    control._advance_scheduled_adventures()
    assert sim.to_dict() == control.to_dict()


def test_old_payload_retains_legacy_progression(simulation):
    sim, run, _ = simulation
    payload = run.to_dict()
    payload.pop("schedule")
    old = AdventureRun.from_dict(payload)
    assert old.schedule is None
    sim.world.active_adventures[0].schedule = None
    sim._advance_adventures(steps=1)
    assert run.steps_taken == 1


def test_daily_progression_uses_schedule_without_global_draw_and_matches_manual_choice(simulation, monkeypatch):
    sim, run, _ = simulation
    waiting(run)
    run.schedule.next_step_tick = 2
    sim.elapsed_days = 1
    manual = Simulator.from_dict(deepcopy(sim.to_dict()))

    def reject_global_draw():
        raise AssertionError("Scheduled adventures must not wait for the world draw")

    monkeypatch.setattr(sim, "_adventure_steps_for_day", reject_global_draw)
    sim._run_adventure_progression()
    manual.resolve_adventure_choice(run.adventure_id, "proceed_cautiously")
    assert sim.to_dict() == manual.to_dict()
    sim.adventure_steps_per_year = 0
    sim.elapsed_days = run.schedule.next_step_tick - 1
    before = deepcopy(sim.to_dict())
    sim._run_adventure_progression()
    assert sim.to_dict() == before


@pytest.mark.parametrize("field,value", [("next_step_tick", -1), ("interval_days", 0),
                                         ("provisions", True), ("segment_mode", "unknown")])
def test_invalid_schedule_rejected(field, value):
    data = AdventureSchedule.begin(1, 10, 1).to_dict()
    data[field] = value
    with pytest.raises(ValueError):
        AdventureSchedule.from_dict(data)


def test_cumulative_hazard_tradeoff_is_not_extra_rolls_for_waiting(simulation):
    sim, run, hero = simulation
    observed = {}
    for mode in ("cautious", "swift"):
        run.schedule.segment_mode = mode
        risk = run._compute_injury_chance([hero])
        run.schedule.plan_next("exploring", 1)
        # Same number of traversed segments, not one hazard draw per elapsed day.
        rng = Random(71)
        harmed = sum(any(rng.random() < risk for _ in range(3)) for _ in range(4000))
        observed[mode] = harmed / 4000
    assert observed["cautious"] < observed["swift"] - 0.08

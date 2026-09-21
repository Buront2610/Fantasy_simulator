"""Real rescue trips: knowledge, target changes, transfer, treatment and return."""

from copy import deepcopy
from dataclasses import replace

import pytest

from fantasy_simulator.adventure import AdventureRun
from fantasy_simulator.adventure import AdventureChoice
from fantasy_simulator.adventure.itinerary import AdventureItinerary
from fantasy_simulator.adventure.objective import AdventureObjective
from fantasy_simulator.adventure.policy import AdventurePolicyEngine
from fantasy_simulator.adventure.schedule import AdventureSchedule
from fantasy_simulator.character import Character
from fantasy_simulator.character_model.death_resolution import mark_character_dead
from fantasy_simulator.rumor import Rumor
from fantasy_simulator.simulation import Simulator
from fantasy_simulator.simulation.adventure_objectives import known_rescue_targets
from fantasy_simulator.simulation.adventure_travel import initialize_itinerary
from tests.test_adventure_routes import expedition, advance_due  # noqa: F401


@pytest.fixture
def rescue_case(expedition, monkeypatch):  # noqa: F811
    sim, run, hero = expedition
    target = Character("Stranded", 30, "Female", "Human", "Mage", char_id="target",
                       location_id="dungeon", residence_location_id="home", injury_status="serious")
    sim.world.add_character(target)
    run.objective = AdventureObjective("rescue", "standard", target.char_id)
    monkeypatch.setattr(AdventurePolicyEngine, "compute_injury_chance", lambda *_: 0)
    return sim, run, hero, target


def finish(sim, run):
    for _ in range(30):
        if run.is_resolved:
            return
        advance_due(sim, run)
    pytest.fail("Rescue did not finish within its finite itinerary")


def test_rescue_treats_transports_and_remembers_real_target(rescue_case):
    sim, run, hero, target = rescue_case
    initial_supplies = run.schedule.provisions
    finish(sim, run)
    assert run.objective.status == "completed"
    assert target.alive and target.injury_status == "injured"
    assert target.location_id == hero.location_id == "home"
    assert target.active_adventure_id is None
    assert target.residence_location_id == "home"
    assert target.get_relationship(hero.char_id) == hero.get_relationship(target.char_id) == 15
    assert run.schedule.provisions < initial_supplies
    rescued = [record for record in sim.world.event_records if record.kind == "adventure_rescued"]
    assert len(rescued) == 1
    assert target.char_id in rescued[0].secondary_actor_ids
    assert rescued[0].render_params["participant_roles"][target.char_id] == "rescue_target"
    assert any("Stranded" in text for text in target.history)
    assert sim.world.get_location_by_id("dungeon").adventure_reputation == 8
    assert sim.world.get_location_by_id("dungeon").exploration_progress == 0


@pytest.mark.parametrize("change,reason", [("death", "dead"), ("recovery", "recovered"), ("claim", "claimed")])
def test_obsolete_rescue_returns_without_treating(rescue_case, change, reason):
    sim, run, hero, target = rescue_case
    if change == "death":
        target.alive = False
    elif change == "recovery":
        target.injury_status = "none"
    else:
        target.active_adventure_id = "other-rescuer"
    finish(sim, run)
    assert run.objective.status == "invalidated" and run.objective.reason == reason
    assert hero.location_id == "home"
    assert target.location_id == "dungeon"
    assert not any(record.kind == "adventure_rescued" for record in sim.world.event_records)


def test_target_movement_replans_without_teleporting(rescue_case):
    sim, run, hero, target = rescue_case
    target.location_id = "detour"
    advance_due(sim, run)
    assert hero.location_id == "waypoint"
    assert run.destination == "detour"
    assert run.itinerary.active_leg.route_id == "wt"
    assert sim.world.event_records[-1].kind == "adventure_target_moved"
    finish(sim, run)
    assert target.location_id == "home" and run.objective.status == "completed"


def test_rescue_information_requires_witness_or_reachable_rumor(rescue_case):
    sim, run, hero, target = rescue_case
    run.objective = AdventureObjective()
    assert known_rescue_targets(sim.world, hero) == []
    record = sim._record_world_event("injury", kind="adventure_injured", location_id="dungeon",
                                     primary_actor_id=target.char_id, severity=3)
    rumor = Rumor(source_event_id=record.record_id, source_location_id="dungeon", spread_level=1)
    sim.world.rumors.append(rumor)
    assert known_rescue_targets(sim.world, hero) == []
    rumor.spread_level = 2
    assert known_rescue_targets(sim.world, hero) == [(target, record.record_id)]
    hero.update_relationship(target.char_id, -50)
    assert known_rescue_targets(sim.world, hero) == []
    hero.update_relationship(target.char_id, 50)
    sim.world.event_records[-1] = replace(record, kind="meeting")
    assert known_rescue_targets(sim.world, hero) == []


@pytest.mark.parametrize("companions", [False, True])
def test_rescue_transfers_from_previous_adventure_atomically(rescue_case, companions):
    sim, run, hero, target = rescue_case
    members = [target.char_id]
    if companions:
        friend = Character("Friend", 30, "Male", "Human", "Warrior", char_id="friend", location_id="dungeon")
        sim.world.add_character(friend)
        members.append(friend.char_id)
        friend.active_adventure_id = "source"
    source = AdventureRun(target.char_id, target.name, "home", "dungeon", sim.world.year,
                          adventure_id="source", state="exploring", member_ids=members,
                          itinerary=AdventureItinerary("dungeon", visited_destination=True),
                          schedule=AdventureSchedule(10000, 0, 1, 10000, 10000, 10000))
    target.active_adventure_id = source.adventure_id
    sim.world.add_adventure(source)
    run.objective.source_adventure_id = source.adventure_id
    while run.objective.status == "active":
        advance_due(sim, run)
    assert target.active_adventure_id == run.adventure_id
    if companions:
        assert source.member_ids == ["friend"] and source.character_id == "friend"
        assert source.state == "returning" and source.itinerary.active_leg is not None
    else:
        assert source.is_resolved and source.outcome == "rescued"
    loaded = Simulator.from_dict(deepcopy(sim.to_dict()))
    assert loaded.to_dict() == sim.to_dict()
    finish(sim, run)
    assert target.alive and target.location_id == "home"


def test_rescue_failure_rolls_back_target_membership_resources_and_relationship(rescue_case, monkeypatch):
    sim, run, hero, target = rescue_case
    while run.state != "exploring":
        advance_due(sim, run)
    sim.elapsed_days = run.schedule.next_step_tick - 1
    before = deepcopy(sim.to_dict())
    original = sim._record_adventure_step_result

    def fail(*args):
        original(*args)
        raise RuntimeError("rescue record failed")

    with monkeypatch.context() as patch:
        patch.setattr(sim, "_record_adventure_step_result", fail)
        with pytest.raises(RuntimeError, match="rescue record"):
            sim._advance_scheduled_adventures()
    assert sim.to_dict() == before
    assert target.active_adventure_id is None and target.injury_status == "serious"
    loaded = Simulator.from_dict(before)
    sim._advance_scheduled_adventures()
    loaded._advance_scheduled_adventures()
    assert sim.to_dict() == loaded.to_dict()


def test_goal_and_pace_are_independent_of_legacy_policy(rescue_case):
    _, run, hero, _ = rescue_case
    run.objective.pace = "standard"
    run.schedule.segment_mode = "standard"
    engine = AdventurePolicyEngine(run)
    run.policy = "treasure"
    chance = engine.compute_loot_chance([hero])
    run.policy = "rescue"
    assert engine.compute_loot_chance([hero]) == chance
    old = run.to_dict()
    old.pop("objective")
    assert AdventureRun.from_dict(old).objective is None


def test_saved_unknown_rescue_target_is_rejected(rescue_case):
    sim, run, _, _ = rescue_case
    data = sim.to_dict()
    data["characters"] = [row for row in data["characters"] if row["char_id"] != run.objective.target_id]
    with pytest.raises(ValueError, match="unknown rescue target"):
        Simulator.from_dict(data)


def test_report_triggers_real_emergency_departure_and_no_duplicate(rescue_case):
    sim, old_run, hero, target = rescue_case
    old_run.state = "resolved"
    hero.active_adventure_id = None
    sim.world.complete_adventure(old_run.adventure_id)
    sim.adventure_steps_per_year = 3
    record = sim._record_world_event("injury", kind="adventure_injured", location_id="dungeon",
                                     primary_actor_id=target.char_id, severity=3)
    sim.world.rumors.append(Rumor(source_event_id=record.record_id, source_location_id="dungeon", spread_level=2))
    sim._maybe_start_adventure(year_fraction=1 / 360)
    run = sim.world.active_adventures[0]
    assert run.objective.purpose == "rescue" and run.objective.target_id == target.char_id
    assert run.objective.evidence_event_id == record.record_id
    assert run.schedule.interval_days == 7
    assert known_rescue_targets(sim.world, hero) == []
    finish(sim, run)
    rescued = next(event for event in sim.world.event_records if event.kind == "adventure_rescued")
    assert record.record_id in rescued.cause_event_ids
    assert target.alive and target.location_id == "home"


def test_treatment_requires_extra_supplies(rescue_case):
    sim, run, _, target = rescue_case
    while run.state != "exploring":
        advance_due(sim, run)
    run.schedule.provisions = run.schedule.next_step_tick - run.schedule.last_tick + 1
    advance_due(sim, run)
    assert run.objective.status == "failed" and run.objective.reason == "supplies"
    assert target.active_adventure_id is None and target.injury_status == "serious"


def test_treated_health_survives_old_injury_value_and_reload(rescue_case):
    sim, run, _, target = rescue_case
    while run.objective.status == "active":
        advance_due(sim, run)
    run.injury_status = "dying"
    run.injury_member_id = target.char_id
    target.injury_status = "none"
    loaded = Simulator.from_dict(sim.to_dict())
    restored = loaded.world.get_adventure_by_id(run.adventure_id)
    finish(loaded, restored)
    survivor = loaded.world.get_character_by_id(target.char_id)
    assert survivor.alive and survivor.injury_status == "none"
    assert restored.objective.status == "completed"


def test_transfer_failure_restores_previous_run_and_supplies(rescue_case, monkeypatch):
    sim, run, _, target = rescue_case
    source = AdventureRun(target.char_id, target.name, "home", "dungeon", sim.world.year,
                          adventure_id="source", state="exploring",
                          itinerary=AdventureItinerary("dungeon", visited_destination=True),
                          schedule=AdventureSchedule(10000, 0, 1, 10000, 10000, 10000))
    target.active_adventure_id = source.adventure_id
    sim.world.add_adventure(source)
    run.objective.source_adventure_id = source.adventure_id
    while run.state != "exploring":
        advance_due(sim, run)
    sim.elapsed_days = run.schedule.next_step_tick - 1
    before = deepcopy(sim.to_dict())
    record = sim._record_adventure_step_result

    def fail(*args):
        record(*args)
        raise RuntimeError("transfer failed")

    with monkeypatch.context() as patch:
        patch.setattr(sim, "_record_adventure_step_result", fail)
        with pytest.raises(RuntimeError, match="transfer failed"):
            sim._advance_scheduled_adventures()
    assert sim.to_dict() == before
    assert sim.world.get_adventure_by_id("source") is source and not source.is_resolved
    sim._advance_scheduled_adventures()
    assert source.is_resolved
    assert source.schedule.provisions == 10000 - sim.elapsed_days - 1


@pytest.mark.parametrize("deceased", ["target", "rescuer"])
def test_natural_death_during_return_finishes_objective(rescue_case, deceased):
    sim, run, hero, target = rescue_case
    while run.objective.status == "active":
        advance_due(sim, run)
    mark_character_dead(target if deceased == "target" else hero, sim.world)
    assert run.is_resolved and run.objective.status == "failed"
    assert target.active_adventure_id is None and hero.active_adventure_id is None
    assert target.location_id == hero.location_id == "dungeon"
    loaded = Simulator.from_dict(sim.to_dict())
    assert loaded.world.get_adventure_by_id(run.adventure_id).objective.status == "failed"


@pytest.mark.parametrize("pace,days", [("cautious", 6), ("standard", 4), ("swift", 3)])
def test_base_pace_changes_edge_time_without_free_supplies(rescue_case, pace, days):
    sim, run, _, _ = rescue_case
    run.schedule.interval_days = 4
    run.objective.pace = pace
    initialize_itinerary(sim.world, run, 1)
    assert run.schedule.next_step_tick == 1 + days
    assert run.schedule.initial_provisions == 40


def test_choice_override_expires_back_to_saved_base_pace(rescue_case):
    sim, run, _, _ = rescue_case
    while run.state != "exploring":
        advance_due(sim, run)
    run.objective.pace = "swift"
    run.pending_choice = AdventureChoice("approach", ["proceed_cautiously"], "proceed_cautiously", context="approach")
    run.state = "waiting_for_choice"
    assert sim.resolve_adventure_choice(run.adventure_id, "proceed_cautiously")
    assert run.schedule.segment_mode == "cautious"
    assert run.schedule.next_step_tick - sim.elapsed_days - 1 == 2
    advance_due(sim, run)
    assert run.objective.status == "rescued"
    assert run.schedule.segment_mode == run.objective.pace == "swift"


@pytest.mark.parametrize("status", ["rescued", "completed"])
def test_saved_rescue_success_requires_actual_membership(rescue_case, status):
    _, run, _, _ = rescue_case
    data = run.to_dict()
    data["objective"]["status"] = status
    with pytest.raises(ValueError, match="must belong"):
        AdventureRun.from_dict(data)


@pytest.mark.parametrize("location,expected", [("dungeon", "completed"), ("home", "invalidated")])
def test_leaving_old_party_is_not_the_same_as_returning_home(rescue_case, location, expected):
    sim, run, _, target = rescue_case
    source = AdventureRun(target.char_id, target.name, "home", "dungeon", sim.world.year,
                          adventure_id="old-source", state="resolved", outcome="retreat")
    sim.world.add_adventure(source)
    sim.world.complete_adventure(source.adventure_id)
    run.objective.source_adventure_id = source.adventure_id
    target.location_id = location
    finish(sim, run)
    assert run.objective.status == expected
    if expected == "invalidated":
        assert run.objective.reason == "returned"
    else:
        assert target.location_id == "home" and target.injury_status == "injured"

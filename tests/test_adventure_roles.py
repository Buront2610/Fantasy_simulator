"""Roles affect real travel, encounters, deterioration, selection and saved evidence."""

from copy import deepcopy

import pytest

from fantasy_simulator.adventure.itinerary import AdventureItinerary
from fantasy_simulator.adventure.roles import capability, choose_companions, party_care_factor
from fantasy_simulator.adventure.policy import AdventurePolicyEngine
from fantasy_simulator.character import Character
from fantasy_simulator.i18n import get_locale, set_locale, tr
from fantasy_simulator.simulation import Simulator
from fantasy_simulator.simulation.adventure_travel import initialize_itinerary
from tests.test_adventure_routes import expedition, advance_due  # noqa: F401


def actor(identity, **kwargs):
    stats = dict(strength=50, constitution=50, wisdom=50, intelligence=50, dexterity=50, charisma=50)
    return Character(identity, 30, "Female", "Human", "Mage", char_id=identity, location_id="home",
                     **{**stats, **kwargs})


def test_specialists_are_not_diluted_and_support_diminishes():
    experts = [actor(str(i), strength=80, constitution=80) for i in range(4)]
    novice = actor("novice", strength=10, constitution=10)
    scores = [capability(experts[:n], "frontline").score for n in range(1, 5)]
    assert scores[0] < scores[1] < scores[2] == scores[3]
    assert scores[1] - scores[0] > scores[2] - scores[1]
    assert capability([experts[0], novice], "frontline").score >= scores[0]
    assert capability(list(reversed(experts)), "frontline") == capability(experts, "frontline")


def test_skills_health_and_not_job_determine_role():
    novice = actor("a")
    expert = actor("b", skills={"First Aid": 10, "Navigation": 10})
    assert capability([novice, expert], "medic").holder_id == expert.char_id
    assert capability([novice, expert], "scout").holder_id == expert.char_id
    expert.job = "Warrior"
    assert capability([novice, expert], "medic").holder_id == expert.char_id
    expert.injury_status = "dying"
    assert capability([novice, expert], "medic").holder_id is None
    assert capability([novice, expert], "scout").holder_id == novice.char_id


def test_rescue_invites_medic_and_respects_willingness_and_presence():
    leader, fighter = actor("leader"), actor("fighter", strength=90, constitution=90)
    medic, target = actor("medic", skills={"First Aid": 10}), actor("target", injury_status="serious")
    assert choose_companions(leader, [fighter, medic], 1, target=target) == [medic]
    medic.update_relationship(leader.char_id, -1)
    assert choose_companions(leader, [fighter, medic], 2, target=target) == [fighter]
    fighter.location_id = "elsewhere"
    assert choose_companions(leader, [fighter, medic], 2, target=target) == []


def test_scout_changes_real_arrival_without_free_stock_and_survives_reload(expedition):  # noqa: F811
    sim, run, hero = expedition
    hero.dexterity = hero.wisdom = 50
    run.schedule.interval_days = 10
    initialize_itinerary(sim.world, run, 1)
    before, stock = run.itinerary.arrival_tick, run.schedule.initial_provisions
    hero.skills["Navigation"] = 10
    initialize_itinerary(sim.world, run, 1)
    assert run.itinerary.arrival_tick < before
    assert run.schedule.initial_provisions == stock
    restored = Simulator.from_dict(sim.to_dict())
    saved = restored.world.get_adventure_by_id(run.adventure_id)
    assert saved.itinerary.arrival_tick == run.itinerary.arrival_tick
    restored.elapsed_days = saved.itinerary.arrival_tick - 1
    restored._advance_scheduled_adventures()
    assert restored.world.get_character_by_id(hero.char_id).location_id == "waypoint"
    assert restored.world.event_records[-1].render_params["party_roles"]["scout"] == hero.char_id


def test_frontline_takes_encounter_and_role_fact_is_historical(expedition, monkeypatch):  # noqa: F811
    sim, run, hero = expedition
    front = actor("front", strength=90, constitution=90, skills={"Swordsmanship": 10})
    sim.world.add_character(front)
    front.active_adventure_id = run.adventure_id
    run.member_ids.append(front.char_id)
    run.state = "exploring"
    run.itinerary = AdventureItinerary(run.destination, visited_destination=True)
    hero.location_id = front.location_id = run.destination
    monkeypatch.setattr(AdventurePolicyEngine, "compute_injury_chance", lambda *_: 1.0)
    advance_due(sim, run)
    assert run.combat_logs[-1]["member_id"] == front.char_id
    assert sim.world.event_records[-1].render_params["party_roles"]["frontline"] == front.char_id
    front.injury_status = "dying"
    restored = Simulator.from_dict(sim.to_dict())
    assert restored.world.event_records[-1].render_params["party_roles"]["frontline"] == front.char_id


def test_accompanying_medic_prevents_actual_deterioration_without_self_care(expedition, monkeypatch):  # noqa: F811
    sim, run, patient = expedition
    medic = actor("medic", skills={"First Aid": 10})
    sim.world.add_character(medic)
    run.member_ids.append(medic.char_id)
    medic.active_adventure_id = run.adventure_id
    patient.injury_status = "serious"
    monkeypatch.setattr("fantasy_simulator.simulation.timeline.cached_natural_death_chance", lambda *_: 0.5)
    monkeypatch.setattr(sim.rng, "random", lambda: 0.4)
    sim._process_natural_health_check(patient, 1.0, known_candidate=True)
    assert patient.injury_status == "serious"
    saved = Simulator.from_dict(sim.to_dict())
    assert party_care_factor(saved.world, saved.world.get_character_by_id(patient.char_id), 1) < 1
    medic.active_adventure_id = None
    sim._process_natural_health_check(patient, 1.0, known_candidate=True)
    assert patient.injury_status == "dying"
    assert sim.world.event_records[-1].kind == "condition_worsened"


@pytest.mark.parametrize("disabled", ["dead", "dying", "elsewhere", "supplies", "patient"])
def test_care_needs_a_capable_present_funded_other_member(expedition, disabled):  # noqa: F811
    sim, run, patient = expedition
    medic = actor("medic", skills={"First Aid": 10})
    sim.world.add_character(medic)
    medic.active_adventure_id = run.adventure_id
    run.member_ids.append(medic.char_id)
    patient.injury_status = "serious"
    assert party_care_factor(sim.world, patient, 1) < 1
    if disabled == "dead":
        medic.alive = False
    elif disabled == "dying":
        medic.injury_status = "dying"
    elif disabled == "elsewhere":
        medic.location_id = "dungeon"
    elif disabled == "supplies":
        run.schedule.provisions = 0
    else:
        medic.skills.clear()
        patient.skills["First Aid"] = 10
    assert party_care_factor(sim.world, patient, 1) == 1


def test_helpers_still_consume_person_days(expedition):  # noqa: F811
    _, run, _ = expedition
    solo, party = deepcopy(run.schedule), deepcopy(run.schedule)
    solo.settle(solo.last_tick + 2, 1)
    party.settle(party.last_tick + 2, 3)
    assert run.schedule.provisions - party.provisions == 3 * (run.schedule.provisions - solo.provisions)


def test_scout_and_lore_specialists_change_their_actual_resolution_chances(expedition):  # noqa: F811
    _, run, _ = expedition
    member = actor("test")
    policy = AdventurePolicyEngine(run)
    risk, discovery = policy.compute_injury_chance([member]), policy.compute_loot_chance([member])
    member.skills["Navigation"] = 10
    assert policy.compute_injury_chance([member]) < risk
    assert policy.compute_loot_chance([member]) == discovery
    member.skills["Lore Mastery"] = 10
    assert policy.compute_loot_chance([member]) > discovery


@pytest.mark.parametrize("locale", ["ja", "en"])
def test_details_show_current_role_effects_and_do_not_rewrite_completed_history(expedition, locale):  # noqa: F811
    sim, run, hero = expedition
    previous = get_locale()
    try:
        set_locale(locale)
        details = sim.get_adventure_details(run.adventure_id)
        assert any(tr("adventure.role_effect_scout") in line and hero.name in line for line in details)
        assert any(tr("adventure.role_unfilled") in line for line in details)
        run.state = "resolved"
        completed = sim.get_adventure_details(run.adventure_id)
        assert not any(tr("adventure.role_effect_scout") in line for line in completed)
    finally:
        set_locale(previous)

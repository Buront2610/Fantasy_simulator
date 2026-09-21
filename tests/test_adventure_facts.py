"""Adventure records describe decisions and outcomes, not guesses from final state."""

from typing import get_args

import pytest

from fantasy_simulator.adventure import AdventureChoice, AdventureRun, CHOICE_PRESS_ON, CHOICE_PROCEED_CAUTIOUSLY
from fantasy_simulator.adventure.results import AdventureFactKind
from fantasy_simulator.character import Character
from fantasy_simulator.i18n import tr_for_locale, tr_term_for_locale
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.simulation import Simulator
from fantasy_simulator.world import World
from fantasy_simulator.world_event.rendering import render_event_record


@pytest.mark.parametrize("locale", ["ja", "en"])
def test_fact_kinds_have_translated_report_labels(locale):
    for kind in get_args(AdventureFactKind):
        key = f"event_type_{kind}"
        assert tr_for_locale(locale, key) != key


class StepRng:
    def __init__(self, rolls):
        self.rolls = iter(rolls)

    def random(self):
        return next(self.rolls)

    def choice(self, values):
        return values[0]


@pytest.fixture
def adventure():
    world = World()
    hero = Character(name="Hero", char_id="hero", age=25, gender="Male", race="Human", job="Warrior",
                     location_id="loc_aethoria_capital")
    world.add_character(hero)
    run = AdventureRun(character_id=hero.char_id, character_name=hero.name, origin=hero.location_id,
                       destination="loc_thornwood", year_started=world.year, adventure_id="facts")
    hero.active_adventure_id = run.adventure_id
    world.add_adventure(run)
    return Simulator(world, seed=7), hero, run


@pytest.mark.parametrize("loot_roll,kind", [(0.0, "adventure_discovery"), (0.99, "adventure_scouted")])
def test_exploration_fact_is_independent_of_waiting_for_choice(adventure, loot_roll, kind):
    sim, hero, run = adventure
    run.state = "exploring"
    sim.rng = StepRng([0.99, loot_roll, 0.0])
    destination = sim.world.get_location_by_id(run.destination)
    prosperity = destination.prosperity
    sim._advance_adventures(steps=1)
    record = sim.world.event_records[-1]
    assert run.state == "waiting_for_choice"
    assert record.kind == kind
    assert bool(run.loot_summary) == (kind == "adventure_discovery")
    assert record.render_params["discovery"] == (run.loot_summary[-1] if run.loot_summary else None)
    assert destination.prosperity == min(100, prosperity + (2 if kind == "adventure_discovery" else 0))


def test_old_injury_does_not_turn_scouting_into_new_injury(adventure):
    sim, hero, run = adventure
    run.state, run.injury_status, hero.injury_status = "exploring", "serious", "serious"
    sim.rng = StepRng([0.99, 0.99, 0.99])
    sim._advance_adventures(steps=1)
    assert run.state == "returning"
    assert sim.world.event_records[-1].kind == "adventure_scouted"
    assert hero.injury_status == "serious"


@pytest.mark.parametrize("manual", [False, True])
@pytest.mark.parametrize("option", [CHOICE_PRESS_ON, CHOICE_PROCEED_CAUTIOUSLY])
def test_all_progress_choices_have_facts_and_causal_links(adventure, option, manual):
    sim, hero, run = adventure
    sim.rng = StepRng([0.0])
    sim._advance_adventures(steps=1)
    arrival_id = run.related_event_ids[-1]
    assert sim.world.event_records[-1].kind == "adventure_arrived"
    run.pending_choice.default_option = option
    if manual:
        assert sim.resolve_adventure_choice(run.adventure_id, option)
    else:
        sim._advance_adventures(steps=1)
    choice = sim.world.event_records[-1]
    assert choice.kind == "adventure_choice"
    assert choice.cause_event_ids == [arrival_id]
    assert choice.render_params["selected_option"] == option
    assert choice.render_params["choice_context"] == "approach"
    assert run.related_event_ids[-1] == choice.record_id
    assert run.state == "exploring"
    assert render_event_record(choice, locale="en", strict=True) == tr_for_locale(
        "en", "detail_choice_made", name=hero.name, choice=tr_for_locale("en", f"choice_{option}"),
    )


def test_companion_subject_and_shared_history_survive_save_load(adventure, tmp_path):
    sim, hero, run = adventure
    companion = Character(name="Companion", char_id="companion", age=25, gender="Female", race="Human",
                          job="Warrior", injury_status="serious", location_id=hero.location_id)
    sim.world.add_character(companion)
    run.member_ids.append(companion.char_id)
    companion.active_adventure_id = run.adventure_id
    run.state = "returning"
    sim._advance_adventures(steps=1)
    record = sim.world.event_records[-1]
    assert record.kind == "adventure_returned_injured"
    assert record.primary_actor_id == companion.char_id
    assert record.secondary_actor_ids == [hero.char_id]
    assert record.render_params["participant_roles"] == {"hero": "leader", "companion": "companion"}
    assert record in sim.world.get_events_by_actor(hero.char_id)
    assert record in sim.world.get_events_by_actor(companion.char_id)
    path = str(tmp_path / "facts.json")
    assert save_simulation(sim, path)
    restored = load_simulation(path)
    assert restored is not None
    loaded = restored.world.get_event_by_id(record.record_id)
    assert loaded.to_dict() == record.to_dict()
    assert loaded in restored.world.get_events_by_actor(companion.char_id)
    assert restored.world.get_adventure_by_id(run.adventure_id).related_event_ids == run.related_event_ids


def test_return_keeps_term_keys_for_cross_locale_rendering(adventure):
    sim, hero, run = adventure
    run.loot_summary.append("ancient relic")
    run.state = "returning"
    sim._advance_adventures(steps=1)
    record = sim.world.event_records[-1]
    assert record.kind == "adventure_returned"
    record.description = "not the source of facts"
    record.render_params["loot"] = "stale translated text"
    assert render_event_record(record, locale="en", strict=True) == tr_for_locale(
        "en", "summary_returned_safely", name=hero.name,
        destination=sim.world.location_name(run.destination), loot=tr_term_for_locale("en", "ancient relic"),
    )


def test_death_between_steps_is_recorded_once_and_clears_pending_choice(adventure):
    sim, hero, run = adventure
    hero.alive = False
    run.state = "waiting_for_choice"
    run.pending_choice = AdventureChoice("prompt", [CHOICE_PRESS_ON], CHOICE_PRESS_ON, "approach")
    assert not sim.resolve_adventure_choice(run.adventure_id, CHOICE_PRESS_ON)
    sim._advance_adventures(steps=2)
    deaths = [record for record in sim.world.event_records if record.kind == "adventure_death"]
    assert len(deaths) == 1
    assert deaths[0].primary_actor_id == hero.char_id
    assert run.pending_choice is None and run.is_resolved
    assert hero.active_adventure_id is None


@pytest.mark.parametrize("dead", [False, True])
def test_existing_companion_injury_is_a_retreat_reason_and_death_has_its_own_subject(adventure, dead):
    sim, hero, run = adventure
    companion = Character(name="Companion", char_id="companion", age=25, gender="Female", race="Human",
                          job="Warrior", injury_status="serious", location_id=hero.location_id, alive=not dead)
    sim.world.add_character(companion)
    run.member_ids.append(companion.char_id)
    companion.active_adventure_id = run.adventure_id
    run.state = "returning" if dead else "exploring"
    sim._advance_adventures(steps=1)
    record = sim.world.event_records[-1]
    assert record.kind == ("adventure_death" if dead else "adventure_retreat_started")
    assert record.primary_actor_id == (companion.char_id if dead else hero.char_id)
    assert record.location_id == run.destination
    assert hero.injury_status == "none"


def test_resolved_step_returns_empty_typed_result_and_legacy_list(adventure):
    sim, hero, run = adventure
    run.state = "resolved"
    result = run.step_result(hero, sim.world)
    assert result.adventure_id == run.adventure_id
    assert result.facts == () and result.summaries == ()
    assert run.step(hero, sim.world) == []

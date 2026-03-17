"""
tests/test_adventure.py - Unit tests for adventure progression.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from adventure import AdventureChoice, AdventureRun, create_adventure_run
from character import Character
from simulator import Simulator
from world import World


class FakeRng:
    def __init__(self, random_values, choice_value=None):
        self.random_values = list(random_values)
        self.choice_value = choice_value

    def random(self):
        if self.random_values:
            return self.random_values.pop(0)
        return 0.99

    def choice(self, options):
        if self.choice_value is not None and self.choice_value in options:
            return self.choice_value
        return options[0]

    def randint(self, lo, hi):
        return lo

    def choices(self, population, weights=None, k=1):
        return [population[0]] * k

    def sample(self, population, k):
        return list(population[:k])


def _make_character(name="Aldric") -> Character:
    return Character(
        name=name,
        age=25,
        gender="Male",
        race="Human",
        job="Warrior",
        strength=60,
        dexterity=50,
        constitution=55,
        location="Aethoria Capital",
    )


def test_adventure_run_round_trip_serialization():
    run = AdventureRun(
        character_id="hero1",
        character_name="Aldric",
        origin="Aethoria Capital",
        destination="Whispering Woods",
        year_started=1000,
        state="waiting_for_choice",
        injury_status="injured",
        loot_summary=["an ancient relic"],
    )
    run.summary_log.append("Aldric reached the woods.")
    run.detail_log.append("Aldric paused at the ruins entrance.")
    run.pending_choice = AdventureChoice(
        prompt="Press onward?",
        options=["press_on", "retreat"],
        default_option="retreat",
        context="depth",
    )
    payload = run.to_dict()
    restored = AdventureRun.from_dict(payload)

    assert restored.character_name == "Aldric"
    assert restored.state == "waiting_for_choice"
    assert restored.injury_status == "injured"
    assert restored.loot_summary == ["an ancient relic"]
    assert restored.summary_log == ["Aldric reached the woods."]
    assert restored.pending_choice is not None
    assert restored.pending_choice.default_option == "retreat"


def test_travel_step_can_enter_waiting_for_choice_state():
    world = World()
    char = _make_character()
    world.add_character(char)
    run = create_adventure_run(char, world, rng=FakeRng([0.9]))

    summaries = run.step(char, world, rng=FakeRng([0.10]))

    assert summaries
    assert run.state == "waiting_for_choice"
    assert run.pending_choice is not None
    assert len(run.pending_choice.options) >= 2


def test_waiting_choice_defaults_automatically_on_next_step():
    world = World()
    char = _make_character()
    world.add_character(char)
    run = create_adventure_run(char, world, rng=FakeRng([0.9]))
    run.step(char, world, rng=FakeRng([0.10]))

    summaries = run.step(char, world, rng=FakeRng([0.90, 0.90]))

    assert summaries == []
    assert run.pending_choice is None
    assert run.state == "exploring"


def test_injury_outcome_uses_injury_field_without_mutating_constitution():
    world = World()
    char = _make_character()
    world.add_character(char)
    run = AdventureRun(
        character_id=char.char_id,
        character_name=char.name,
        origin=char.location,
        destination="Whispering Woods",
        year_started=world.year,
        state="exploring",
    )
    char.active_adventure_id = run.adventure_id
    before_constitution = char.constitution

    run.step(char, world, rng=FakeRng([0.10]))
    summaries = run.step(char, world, rng=FakeRng([0.90]))

    assert summaries
    assert run.outcome == "injury"
    assert char.injury_status == "injured"
    assert char.constitution == before_constitution


def test_simulator_integrates_adventures_into_normal_year_loop(monkeypatch):
    world = World()
    char = _make_character()
    world.add_character(char)
    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=4, seed=1)

    sim.rng = FakeRng([0.9, 0.0, 0.9, 0.3, 0.9])

    sim._run_year()

    assert len(world.completed_adventures) == 1
    run = world.completed_adventures[0]
    assert run.outcome == "safe_return"
    assert any("set out" in entry.lower() for entry in world.event_log)
    assert sim.get_adventure_summaries()


def test_pending_choice_persists_until_later_year(monkeypatch):
    world = World()
    char = _make_character()
    world.add_character(char)
    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=4, seed=1)

    sim.rng = FakeRng([0.9, 0.0, 0.10, 0.9, 0.9, 0.9])

    sim._run_year()

    assert len(world.active_adventures) == 1
    run = world.active_adventures[0]
    assert run.pending_choice is not None
    assert run.state == "waiting_for_choice"

    sim._run_year()

    assert world.active_adventures == []
    assert len(world.completed_adventures) == 1
    assert world.completed_adventures[0].outcome == "safe_return"

"""
tests/test_adventure.py - Unit tests for adventure progression.
"""

from adventure import (
    AdventureChoice,
    AdventureRun,
    CHOICE_PROCEED_CAUTIOUSLY,
    CHOICE_PRESS_ON,
    CHOICE_RETREAT,
    CHOICE_WITHDRAW,
    create_adventure_run,
)
from character import Character
from i18n import set_locale
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
        location_id="loc_aethoria_capital",
    )


def test_adventure_run_round_trip_serialization():
    run = AdventureRun(
        character_id="hero1",
        character_name="Aldric",
        origin="loc_aethoria_capital",
        destination="loc_thornwood",
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
    assert set(run.pending_choice.options) <= {
        CHOICE_PRESS_ON,
        CHOICE_PROCEED_CAUTIOUSLY,
        CHOICE_RETREAT,
        CHOICE_WITHDRAW,
    }


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
        origin=char.location_id,
        destination="loc_thornwood",
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


def test_choice_resolution_survives_locale_change():
    world = World()
    char = _make_character()
    world.add_character(char)
    run = create_adventure_run(char, world, rng=FakeRng([0.9]))
    run.step(char, world, rng=FakeRng([0.10]))

    set_locale("ja")
    assert run.pending_choice is not None
    assert run.pending_choice.default_option == CHOICE_PROCEED_CAUTIOUSLY

    set_locale("en")
    summaries = run.resolve_choice(world, char, option=CHOICE_RETREAT)

    assert summaries
    assert run.state == "returning"
    assert run.pending_choice is None


def test_adventure_death_clears_spouse_on_survivor():
    """When a character dies during an adventure, the surviving spouse's
    spouse_id must be cleared and the spouse must receive a history entry."""
    world = World()
    hero = _make_character("Hero")
    spouse = _make_character("Spouse")
    world.add_character(hero)
    world.add_character(spouse)

    hero.spouse_id = spouse.char_id
    spouse.spouse_id = hero.char_id

    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=4, seed=1)

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

    # Roll that triggers death in exploring state (0.18 <= roll < 0.24)
    run.step(hero, world, rng=FakeRng([0.20]))

    assert not hero.alive
    assert run.outcome == "death"

    # Simulate what the simulator does after a step kills the character
    sim.event_system.handle_death_side_effects(hero, world)

    assert spouse.spouse_id is None
    assert any("Hero" in h for h in spouse.history)


def test_adventure_death_clears_spouse_via_simulator_integration():
    """Full integration: simulator's _advance_adventures handles spouse
    cleanup when adventure step kills a character."""
    world = World()
    hero = _make_character("Hero")
    spouse = _make_character("Spouse")
    world.add_character(hero)
    world.add_character(spouse)

    hero.spouse_id = spouse.char_id
    spouse.spouse_id = hero.char_id

    sim = Simulator(world, events_per_year=0, adventure_steps_per_year=1, seed=1)

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

    # Use an rng that causes death (roll = 0.20, in 0.18..0.24 range)
    sim.rng = FakeRng([0.20])
    sim._advance_adventures()

    assert not hero.alive
    assert spouse.spouse_id is None
    assert any("Hero" in h for h in spouse.history)

"""
tests/test_simulator.py - Unit tests for the Simulator class.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from character import Character
from character_creator import CharacterCreator
from save_load import load_simulation, save_simulation
from simulator import Simulator
from world import World


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_world(n_chars: int = 6, seed_name_prefix: str = "Hero") -> World:
    """Return a fresh World with *n_chars* random adventurers."""
    world = World()
    creator = CharacterCreator()
    import random
    random.seed(42)
    locs = [loc.name for loc in world.grid.values() if loc.region_type != "dungeon"]
    for i in range(n_chars):
        c = creator.create_random(name=f"{seed_name_prefix}{i}")
        c.location = locs[i % len(locs)]
        world.add_character(c)
    return world


@pytest.fixture
def small_world() -> World:
    return _make_world(n_chars=4)


@pytest.fixture
def medium_world() -> World:
    return _make_world(n_chars=10)


@pytest.fixture
def sim_small(small_world) -> Simulator:
    return Simulator(small_world, events_per_year=4, seed=0)


@pytest.fixture
def sim_medium(medium_world) -> Simulator:
    return Simulator(medium_world, events_per_year=6, seed=7)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------

class TestSimulatorConstruction:
    def test_world_attached(self, sim_small, small_world):
        assert sim_small.world is small_world

    def test_history_empty_at_start(self, sim_small):
        assert sim_small.history == []

    def test_custom_events_per_year(self, small_world):
        s = Simulator(small_world, events_per_year=15)
        assert s.events_per_year == 15

    def test_seed_reproducibility(self, small_world):
        """Two simulators with the same seed should produce the same history."""
        w1 = _make_world(n_chars=4)
        w2 = _make_world(n_chars=4)
        # Ensure same starting state by syncing char IDs
        for c1, c2 in zip(w1.characters, w2.characters):
            c2.char_id = c1.char_id

        s1 = Simulator(w1, events_per_year=4, seed=99)
        s2 = Simulator(w2, events_per_year=4, seed=99)
        s1.run(years=3)
        s2.run(years=3)
        assert [ev.description for ev in s1.history] == [ev.description for ev in s2.history]
        assert s1.world.event_log == s2.world.event_log


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------

class TestSimulatorRun:
    def test_year_advances(self, sim_small, small_world):
        start_year = small_world.year
        sim_small.run(years=5)
        assert small_world.year == start_year + 5

    def test_history_populated(self, sim_small):
        sim_small.run(years=3)
        assert len(sim_small.history) > 0

    def test_event_log_populated(self, sim_small, small_world):
        sim_small.run(years=3)
        assert len(small_world.event_log) > 0

    def test_run_zero_years(self, sim_small, small_world):
        start_year = small_world.year
        sim_small.run(years=0)
        assert small_world.year == start_year
        assert sim_small.history == []

    def test_characters_age_during_run(self, sim_small, small_world):
        """Aging events should increment character ages over time."""
        initial_ages = {c.char_id: c.age for c in small_world.characters}
        sim_small.run(years=10)
        aged = [
            c for c in small_world.characters
            if c.age > initial_ages[c.char_id]
        ]
        assert len(aged) > 0

    def test_some_characters_may_die(self):
        """Over a long simulation, at least some characters should perish."""
        world = _make_world(n_chars=8)
        # Give them advanced ages to increase mortality
        for c in world.characters:
            c.age = 70
        s = Simulator(world, events_per_year=6, seed=1)
        s.run(years=20)
        dead = [c for c in world.characters if not c.alive]
        assert len(dead) > 0

    def test_no_chars_world_safe(self):
        """A world with no characters should not crash."""
        world = World()
        s = Simulator(world, events_per_year=4, seed=0)
        s.run(years=5)
        assert world.year == 1005

    def test_advance_years_public_api(self, sim_small, small_world):
        start_year = small_world.year
        sim_small.advance_years(2)
        assert small_world.year == start_year + 2


# ---------------------------------------------------------------------------
# get_summary()
# ---------------------------------------------------------------------------

class TestGetSummary:
    def test_returns_string(self, sim_small):
        sim_small.run(years=5)
        summary = sim_small.get_summary()
        assert isinstance(summary, str)

    def test_contains_world_name(self, sim_small):
        sim_small.run(years=2)
        summary = sim_small.get_summary()
        assert "Aethoria" in summary

    def test_contains_final_year(self, sim_small, small_world):
        sim_small.run(years=5)
        summary = sim_small.get_summary()
        assert str(small_world.year) in summary

    def test_contains_event_counts(self, sim_small):
        sim_small.run(years=3)
        summary = sim_small.get_summary()
        assert "Total events" in summary

    def test_before_run_no_crash(self, sim_small):
        summary = sim_small.get_summary()
        assert isinstance(summary, str)


# ---------------------------------------------------------------------------
# get_character_story()
# ---------------------------------------------------------------------------

class TestGetCharacterStory:
    def test_returns_string(self, sim_small, small_world):
        sim_small.run(years=5)
        char = small_world.characters[0]
        story = sim_small.get_character_story(char.char_id)
        assert isinstance(story, str)

    def test_contains_char_name(self, sim_small, small_world):
        sim_small.run(years=3)
        char = small_world.characters[0]
        story = sim_small.get_character_story(char.char_id)
        assert char.name in story

    def test_unknown_id_returns_message(self, sim_small):
        story = sim_small.get_character_story("nonexistent_id_xyz")
        assert "No character" in story

    def test_story_includes_history(self, sim_small, small_world):
        sim_small.run(years=5)
        char = small_world.characters[0]
        # History should have been populated
        story = sim_small.get_character_story(char.char_id)
        # The stat block is always present
        assert "STR" in story

    def test_all_stories_no_crash(self, sim_small):
        sim_small.run(years=3)
        all_stories = sim_small.get_all_stories()
        assert isinstance(all_stories, str)


# ---------------------------------------------------------------------------
# get_event_log()
# ---------------------------------------------------------------------------

class TestGetEventLog:
    def test_returns_list(self, sim_small):
        sim_small.run(years=3)
        log = sim_small.get_event_log()
        assert isinstance(log, list)

    def test_last_n_works(self, sim_small):
        sim_small.run(years=5)
        full = sim_small.get_event_log()
        last5 = sim_small.get_event_log(last_n=5)
        assert len(last5) <= 5
        assert last5 == full[-5:]

    def test_last_n_exceeds_log_length(self, sim_small):
        sim_small.run(years=1)
        log = sim_small.get_event_log()
        last_big = sim_small.get_event_log(last_n=9999)
        assert last_big == log


# ---------------------------------------------------------------------------
# events_by_type()
# ---------------------------------------------------------------------------

class TestEventsByType:
    def test_returns_list(self, sim_small):
        sim_small.run(years=5)
        results = sim_small.events_by_type("meeting")
        assert isinstance(results, list)

    def test_all_results_match_type(self, sim_small):
        sim_small.run(years=5)
        battles = sim_small.events_by_type("battle")
        assert all(e.event_type == "battle" for e in battles)

    def test_unknown_type_empty_list(self, sim_small):
        sim_small.run(years=3)
        results = sim_small.events_by_type("dragon_attack")
        assert results == []


# ---------------------------------------------------------------------------
# Integration: CharacterCreator → World → Simulator
# ---------------------------------------------------------------------------

class TestFullIntegration:
    def test_template_chars_survive_simulation(self):
        creator = CharacterCreator()
        world = World()
        for tmpl in ["warrior", "mage", "rogue", "healer"]:
            c = creator.create_from_template(tmpl)
            world.add_character(c)
        # Pad world with random NPCs
        for _ in range(4):
            world.add_character(creator.create_random())

        s = Simulator(world, events_per_year=5, seed=42)
        s.run(years=10)
        assert len(s.history) > 0
        # World year advanced
        assert world.year == 1010

    def test_custom_char_appears_in_story(self):
        creator = CharacterCreator()
        world = World()
        hero = creator.create_from_template("paladin", name="Sir Aldric")
        world.add_character(hero)
        for _ in range(5):
            world.add_character(creator.create_random())

        s = Simulator(world, events_per_year=6, seed=0)
        s.run(years=5)
        story = s.get_character_story(hero.char_id)
        assert "Sir Aldric" in story


class TestSimulatorSerialization:
    def test_round_trip_preserves_core_state(self):
        world = _make_world(n_chars=5)
        sim = Simulator(world, events_per_year=2, adventure_steps_per_year=4, seed=3)
        sim.run(years=2)

        restored = Simulator.from_dict(sim.to_dict())

        assert restored.world.year == sim.world.year
        assert len(restored.world.characters) == len(sim.world.characters)
        assert restored.events_per_year == sim.events_per_year
        assert restored.adventure_steps_per_year == sim.adventure_steps_per_year
        assert len(restored.history) == len(sim.history)
        assert len(restored.world.completed_adventures) == len(sim.world.completed_adventures)

    def test_save_and_load_snapshot_file(self, tmp_path):
        world = _make_world(n_chars=4)
        sim = Simulator(world, events_per_year=1, adventure_steps_per_year=2, seed=5)
        sim.run(years=1)

        path = tmp_path / "snapshot.json"
        save_simulation(sim, str(path))
        restored = load_simulation(str(path))

        assert restored.world.name == sim.world.name
        assert restored.world.event_log == sim.world.event_log
        assert [c.name for c in restored.world.characters] == [
            c.name for c in sim.world.characters
        ]


class TestInjuryRecovery:
    def test_injured_character_can_recover_during_year(self):
        world = _make_world(n_chars=1)
        char = world.characters[0]
        char.injury_status = "injured"
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=1)

        sim.rng = type(
            "FixedRng",
            (),
            {
                "random": lambda self: 0.1,
                "choice": lambda self, options: options[0],
            },
        )()
        sim._run_year()

        assert char.injury_status == "none"
        assert any("recovered from earlier adventure injuries" in entry.lower() for entry in world.event_log)
        assert any("Recovered from earlier adventure injuries." in entry for entry in char.history)

    def test_injured_character_does_not_start_adventure_before_recovery(self):
        world = _make_world(n_chars=1)
        char = world.characters[0]
        char.injury_status = "injured"
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=1)

        sim.rng = type(
            "FixedRng",
            (),
            {
                "random": lambda self: 0.9,
                "choice": lambda self, options: options[0],
            },
        )()
        sim._run_year()

        assert char.injury_status == "injured"
        assert char.active_adventure_id is None
        assert world.active_adventures == []

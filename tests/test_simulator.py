"""
tests/test_simulator.py - Unit tests for the Simulator class.
"""

from collections import Counter

import pytest

from fantasy_simulator.events import EventResult
from fantasy_simulator.adventure import (
    AdventureChoice,
    AdventureRun,
    POLICY_SWIFT,
    POLICY_TREASURE,
    RETREAT_NEVER,
    RETREAT_ON_SUPPLY,
    RETREAT_ON_TROPHY,
)
from fantasy_simulator.character import Character
from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

def _make_world(n_chars: int = 6, seed_name_prefix: str = "Hero") -> World:
    """Return a fresh World with *n_chars* random adventurers."""
    world = World()
    creator = CharacterCreator()
    import random
    random.seed(42)
    locs = [loc.id for loc in world.grid.values() if loc.region_type != "dungeon"]
    for i in range(n_chars):
        c = creator.create_random(name=f"{seed_name_prefix}{i}")
        c.location_id = locs[i % len(locs)]
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


@pytest.fixture(autouse=True)
def reset_locale():
    previous = get_locale()
    set_locale("en")
    yield
    set_locale(previous)


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
        w2.rebuild_char_index()

        s1 = Simulator(w1, events_per_year=4, seed=99)
        s2 = Simulator(w2, events_per_year=4, seed=99)
        s1.run(years=3)
        s2.run(years=3)
        assert [ev.description for ev in s1.history] == [ev.description for ev in s2.history]
        assert s1.world.event_log == s2.world.event_log

    def test_initial_generation_reproducibility_with_rng(self):
        """Using injected RNG for character creation produces identical worlds."""
        import random as _random

        def _make_seeded_world(seed):
            rng = _random.Random(seed)
            world = World()
            creator = CharacterCreator()
            locs = [loc.id for loc in world.grid.values() if loc.region_type != "dungeon"]
            for _ in range(4):
                c = creator.create_random(rng=rng)
                c.location_id = rng.choice(locs)
                world.add_character(c)
            return world

        w1 = _make_seeded_world(seed=555)
        w2 = _make_seeded_world(seed=555)

        assert len(w1.characters) == len(w2.characters)
        for c1, c2 in zip(w1.characters, w2.characters):
            assert c1.char_id == c2.char_id
            assert c1.name == c2.name
            assert c1.race == c2.race
            assert c1.job == c2.job
            assert c1.age == c2.age
            assert c1.strength == c2.strength
            assert c1.intelligence == c2.intelligence
            assert c1.location_id == c2.location_id

        # Full simulation should also match
        s1 = Simulator(w1, events_per_year=4, seed=99)
        s2 = Simulator(w2, events_per_year=4, seed=99)
        s1.run(years=3)
        s2.run(years=3)
        assert [ev.description for ev in s1.history] == [ev.description for ev in s2.history]

    def test_seed_fixed_world_generation_is_deterministic(self):
        import random as _random

        def _build_seeded_world(seed):
            rng = _random.Random(seed)
            world = World()
            creator = CharacterCreator()
            locs = [loc.id for loc in world.grid.values() if loc.region_type != "dungeon"]
            for _ in range(6):
                char = creator.create_random(rng=rng)
                char.location_id = rng.choice(locs)
                world.add_character(char)
            return world

        world1 = _build_seeded_world(42)
        world2 = _build_seeded_world(42)

        assert world1.to_dict() == world2.to_dict()

    def test_record_event_ids_do_not_consume_main_rng(self, small_world):
        sim = Simulator(small_world, events_per_year=0, seed=123)
        result = EventResult(
            description="A structured event.",
            event_type="meeting",
            year=small_world.year,
        )

        before = sim.rng.getstate()
        sim._record_event(result, location_id="loc_aethoria_capital")

        assert sim.rng.getstate() == before


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

    def test_story_resolves_relation_names(self):
        world = World()
        hero = Character("Hero", 25, "Male", "Human", "Warrior")
        friend = Character("Friend", 24, "Female", "Elf", "Mage")
        world.add_character(hero)
        world.add_character(friend)
        hero.add_relation_tag(friend.char_id, "friend")

        sim = Simulator(world, events_per_year=0, seed=1)
        story = sim.get_character_story(hero.char_id)

        assert "Friend" in story
        assert friend.char_id[:8] not in story

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

    def test_loaded_snapshot_continues_with_same_rng_sequence(self, tmp_path):
        world_a = _make_world(n_chars=5)
        world_b = _make_world(n_chars=5)
        for c1, c2 in zip(world_a.characters, world_b.characters):
            c2.char_id = c1.char_id
        world_b.rebuild_char_index()

        sim_a = Simulator(world_a, events_per_year=3, adventure_steps_per_year=2, seed=17)
        sim_b = Simulator(world_b, events_per_year=3, adventure_steps_per_year=2, seed=17)

        sim_a.run(years=2)
        sim_b.run(years=2)

        path = tmp_path / "snapshot_rng.json"
        save_simulation(sim_a, str(path))
        restored = load_simulation(str(path))

        restored.run(years=3)
        sim_b.run(years=3)

        assert restored.world.year == sim_b.world.year
        assert restored.world.event_log == sim_b.world.event_log
        assert [ev.description for ev in restored.history] == [ev.description for ev in sim_b.history]

    def test_save_and_load_preserves_locale(self, tmp_path):
        set_locale("ja")
        world = _make_world(n_chars=3)
        sim = Simulator(world, events_per_year=1, adventure_steps_per_year=1, seed=11)

        path = tmp_path / "snapshot_locale.json"
        save_simulation(sim, str(path))
        set_locale("en")
        load_simulation(str(path))

        assert get_locale() == "ja"

    def test_save_and_load_preserves_pending_choice_ids_across_locale_change(self, tmp_path):
        set_locale("ja")
        world = World()
        char = Character("Aldric", 25, "Male", "Human", "Warrior", location_id="loc_aethoria_capital")
        world.add_character(char)
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=1, seed=1)
        run = AdventureRun(
            character_id=char.char_id,
            character_name=char.name,
            origin=char.location_id,
            destination="loc_sunken_ruins",
            year_started=world.year,
            state="waiting_for_choice",
        )
        run.pending_choice = AdventureChoice(
            prompt="test",
            options=["press_on", "proceed_cautiously", "retreat"],
            default_option="proceed_cautiously",
            context="approach",
        )
        char.active_adventure_id = run.adventure_id
        world.add_adventure(run)

        path = tmp_path / "snapshot_pending_choice.json"
        save_simulation(sim, str(path))
        set_locale("en")
        restored = load_simulation(str(path))

        pending = restored.get_pending_adventure_choices()
        assert pending
        assert pending[0]["default_option"] == "proceed_cautiously"

    def test_seed_fixed_12_years_snapshot_is_deterministic(self):
        import random as _random

        def _build_seeded_world(seed):
            rng = _random.Random(seed)
            world = World()
            creator = CharacterCreator()
            locs = [loc.id for loc in world.grid.values() if loc.region_type != "dungeon"]
            for _ in range(6):
                char = creator.create_random(rng=rng)
                char.location_id = rng.choice(locs)
                world.add_character(char)
            return world

        sim1 = Simulator(_build_seeded_world(42), events_per_year=4, adventure_steps_per_year=2, seed=99)
        sim2 = Simulator(_build_seeded_world(42), events_per_year=4, adventure_steps_per_year=2, seed=99)

        for _ in range(12):
            sim1.advance_years(1)
            sim2.advance_years(1)

        assert sim1.to_dict() == sim2.to_dict()


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
                "randint": lambda self, lo, hi: lo,
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
                "randint": lambda self, lo, hi: lo,
            },
        )()
        sim._run_year()

        assert char.injury_status == "injured"
        assert char.active_adventure_id is None
        assert world.active_adventures == []


class TestAdventureSafety:
    def test_dead_character_adventure_is_not_advanced(self):
        world = World()
        char = Character("Aldric", 95, "Male", "Human", "Warrior", location_id="loc_aethoria_capital")
        world.add_character(char)
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=3, seed=1)

        sim.rng = type(
            "FixedRng",
            (),
            {
                "random": lambda self: 0.0,
                "choice": lambda self, options: options[0],
                "randint": lambda self, lo, hi: lo,
                "choices": lambda self, population, weights=None, k=1: [population[0]] * k,
                "sample": lambda self, population, k: list(population[:k]),
            },
        )()

        sim._maybe_start_adventure()
        run = world.active_adventures[0]
        run.steps_taken = 0
        sim.event_system.event_death(char, world, rng=sim.rng)

        sim._advance_adventures()

        assert world.active_adventures == []
        assert len(world.completed_adventures) == 1
        assert world.completed_adventures[0].outcome == "death"
        assert world.completed_adventures[0].steps_taken == 0

    def test_adventure_summary_uses_localized_status(self):
        set_locale("en")
        world = World()
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=1)
        run = AdventureRun(
            character_id="hero1",
            character_name="Aldric",
            origin="loc_aethoria_capital",
            destination="loc_thornwood",
            year_started=1000,
            state="waiting_for_choice",
        )
        world.add_adventure(run)

        summaries = sim.get_adventure_summaries()

        assert "[waiting_for_choice]" not in summaries[0]
        assert "[waiting for choice]" in summaries[0]

    def test_start_party_adventure_sets_retreat_rule_from_policy(self, monkeypatch):
        world = _make_world(n_chars=4)
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=7)
        monkeypatch.setattr(
            "fantasy_simulator.simulation.adventure_coordinator.select_party_policy",
            lambda members, rng: POLICY_SWIFT,
        )

        candidates = [c for c in world.characters if c.alive]
        sim._start_party_adventure(candidates)
        run = world.active_adventures[0]

        assert run.policy == POLICY_SWIFT
        assert run.retreat_rule == RETREAT_ON_SUPPLY

    def test_party_formation_prefers_same_location(self, monkeypatch):
        world = World()
        leader = Character("Leader", 25, "Male", "Human", "Warrior", location_id="loc_aethoria_capital")
        nearby = Character("Nearby", 25, "Female", "Human", "Mage", location_id="loc_aethoria_capital")
        far = Character("Far", 25, "Female", "Human", "Rogue", location_id="loc_thornwood")
        world.add_character(leader)
        world.add_character(nearby)
        world.add_character(far)
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=11)

        class FixedPartyRng:
            def random(self):
                return 0.0

            def choice(self, options):
                if leader in options:
                    return leader
                if 2 in options:
                    return 2
                return options[0]

            def sample(self, population, k):
                return list(population[:k])

            def choices(self, population, weights=None, k=1):
                return [population[0]] * k

            def randint(self, lo, hi):
                return lo

        sim.rng = FixedPartyRng()
        sim.id_rng = FixedPartyRng()
        monkeypatch.setattr(
            "fantasy_simulator.simulation.adventure_coordinator.select_party_policy",
            lambda members, rng: POLICY_TREASURE,
        )

        sim._start_party_adventure([leader, nearby, far])
        run = world.active_adventures[0]
        assert nearby.char_id in set(run.member_ids)
        assert far.char_id not in set(run.member_ids)
        assert run.retreat_rule == RETREAT_ON_TROPHY

    def test_companion_death_triggers_death_side_effects_for_companion(self):
        world = World()
        leader = Character("Leader", 25, "Male", "Human", "Warrior", location_id="loc_aethoria_capital")
        companion = Character("Companion", 25, "Female", "Human", "Mage", location_id="loc_aethoria_capital")
        companion.injury_status = "dying"
        world.add_character(leader)
        world.add_character(companion)
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=1, seed=1)

        run = AdventureRun(
            character_id=leader.char_id,
            character_name=leader.name,
            origin=leader.location_id,
            destination="loc_thornwood",
            year_started=world.year,
            state="exploring",
            member_ids=[leader.char_id, companion.char_id],
            policy="assault",
            retreat_rule=RETREAT_NEVER,
        )
        run._compute_injury_chance = lambda members: 0.1
        leader.active_adventure_id = run.adventure_id
        companion.active_adventure_id = run.adventure_id
        world.add_adventure(run)

        class FixedRng:
            def __init__(self):
                self.values = iter([0.99, 0.12])

            def random(self):
                return next(self.values, 0.99)

            def choice(self, options):
                return companion if companion in options else options[0]

            def sample(self, population, k):
                return list(population[:k])

        seen = []

        def _record_death_effects(char, _world):
            seen.append(char.char_id)

        sim.rng = FixedRng()
        sim.event_system.handle_death_side_effects = _record_death_effects
        sim._advance_adventures()

        assert companion.char_id in seen


class TestJapaneseLocaleSummary:
    @pytest.fixture(autouse=True)
    def _locale(self):
        prev = get_locale()
        set_locale("ja")
        yield
        set_locale(prev)

    def test_summary_event_types_in_japanese(self):
        world = _make_world(n_chars=4)
        sim = Simulator(world, events_per_year=4, seed=42)
        sim.run(years=5)
        summary = sim.get_summary()

        # Event type names should be in Japanese, not raw English identifiers
        assert "回" in summary
        # At least one localized event type should appear
        ja_types = ["出会い", "旅", "技能訓練", "発見", "戦闘", "加齢", "結婚", "死亡"]
        assert any(t in summary for t in ja_types)

    def test_character_story_race_job_in_japanese(self):
        world = World()
        char = Character("Aldric", 25, "Male", "Human", "Warrior", location_id="loc_aethoria_capital")
        world.add_character(char)
        sim = Simulator(world, events_per_year=0, seed=1)

        story = sim.get_character_story(char.char_id)

        assert "人間" in story
        assert "戦士" in story


class TestWorldEventRecordIntegration:
    def test_simulation_creates_event_records(self, small_world):
        sim = Simulator(small_world, seed=42)
        sim.advance_years(2)
        assert len(sim.world.event_records) > 0

    def test_legacy_history_entries_are_mirrored_into_event_records(self, small_world):
        sim = Simulator(small_world, seed=42)
        sim.advance_years(2)

        structured_keys = {
            (record.year, record.kind, record.description)
            for record in sim.world.event_records
        }
        legacy_keys = {
            (event.year, event.event_type, event.description)
            for event in sim.history
        }

        assert legacy_keys <= structured_keys

    def test_simulator_log_entries_are_mirrored_into_event_records(self):
        world = _make_world(n_chars=1)
        char = world.characters[0]
        char.injury_status = "injured"
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=4, seed=1)

        sim.rng = type(
            "FixedRng",
            (),
            {
                "random": lambda self: next(self.values),
                "choice": lambda self, options: options[0],
                "randint": lambda self, lo, hi: lo,
                "values": iter([0.9, 0.1, 0.0, 0.9, 0.3, 0.9] + [0.5] * 20),
            },
        )()

        sim._run_year()

        log_counter = Counter(
            entry.split("] ", 1)[1] if "] " in entry else entry
            for entry in world.event_log
        )
        record_counter = Counter(record.description for record in world.event_records)

        assert log_counter <= record_counter
        assert any(record.kind == "injury_recovery" for record in world.event_records)
        assert any(record.kind == "adventure_started" for record in world.event_records)

    def test_event_records_have_valid_kinds(self, small_world):
        sim = Simulator(small_world, seed=42)
        sim.advance_years(1)
        for record in sim.world.event_records:
            assert record.kind != ""
            assert record.year > 0

    def test_event_records_have_location_ids(self, small_world):
        sim = Simulator(small_world, seed=42)
        sim.advance_years(3)
        records_with_location = [r for r in sim.world.event_records if r.location_id is not None]
        assert len(records_with_location) > 0

    def test_event_records_queryable_by_year(self, small_world):
        sim = Simulator(small_world, seed=42)
        sim.advance_years(3)
        year_records = sim.world.get_events_by_year(1001)
        assert isinstance(year_records, list)

    def test_event_records_saved_and_loaded(self, small_world, tmp_path):
        sim = Simulator(small_world, seed=42)
        sim.advance_years(2)
        original_count = len(sim.world.event_records)
        assert original_count > 0

        path = tmp_path / "test.json"
        save_simulation(sim, str(path))
        restored = load_simulation(str(path))
        assert restored is not None
        assert len(restored.world.event_records) == original_count

    def test_relation_tag_sources_include_canonical_event_record_id(self, small_world):
        sim = Simulator(small_world, events_per_year=0, seed=42)
        char1, char2 = sim.world.characters[0], sim.world.characters[1]
        result = sim.event_system.event_battle(char1, char2, sim.world, rng=sim.rng)
        sim._record_event(result, location_id=char1.location_id)
        record_id = sim.world.event_records[-1].record_id
        key1 = f"{char2.char_id}:rival"
        key2 = f"{char1.char_id}:rival"
        assert record_id in char1.relation_tag_sources.get(key1, [])
        assert record_id in char2.relation_tag_sources.get(key2, [])


# ---------------------------------------------------------------------------
# Seasonal Modifiers (design §5.7)
# ---------------------------------------------------------------------------

class TestSeasonalModifiers:
    """Tarn Adams: Seasons should meaningfully affect world conditions."""

    def test_winter_mountain_increases_danger(self):
        world = World(name="TestWorld", year=1000)
        sim = Simulator(world, events_per_year=0, seed=1)
        mountain_locs = [loc for loc in world.grid.values() if loc.region_type == "mountain"]
        if not mountain_locs:
            pytest.skip("No mountain locations in default world")
        loc = mountain_locs[0]
        original_danger = loc.danger
        sim._apply_seasonal_modifiers(1)  # January = winter
        assert loc.danger > original_danger or loc.danger == 100  # clamped at 100
        sim._revert_seasonal_modifiers()
        assert loc.danger == original_danger

    def test_non_winter_no_mountain_modifier(self):
        world = World(name="TestWorld", year=1000)
        sim = Simulator(world, events_per_year=0, seed=1)
        mountain_locs = [loc for loc in world.grid.values() if loc.region_type == "mountain"]
        if not mountain_locs:
            pytest.skip("No mountain locations in default world")
        loc = mountain_locs[0]
        original_danger = loc.danger
        sim._apply_seasonal_modifiers(7)  # July = summer
        assert loc.danger == original_danger
        sim._revert_seasonal_modifiers()

    def test_summer_city_increases_traffic(self):
        world = World(name="TestWorld", year=1000)
        sim = Simulator(world, events_per_year=0, seed=1)
        city_locs = [loc for loc in world.grid.values() if loc.region_type == "city"]
        if not city_locs:
            pytest.skip("No city locations in default world")
        loc = city_locs[0]
        original_traffic = loc.traffic
        sim._apply_seasonal_modifiers(7)  # July = summer
        assert loc.traffic >= original_traffic
        sim._revert_seasonal_modifiers()
        assert loc.traffic == original_traffic

    def test_spring_village_increases_mood(self):
        world = World(name="TestWorld", year=1000)
        sim = Simulator(world, events_per_year=0, seed=1)
        village_locs = [loc for loc in world.grid.values() if loc.region_type == "village"]
        if not village_locs:
            pytest.skip("No village locations in default world")
        loc = village_locs[0]
        original_mood = loc.mood
        sim._apply_seasonal_modifiers(4)  # April = spring
        assert loc.mood >= original_mood
        sim._revert_seasonal_modifiers()
        assert loc.mood == original_mood

    def test_autumn_forest_increases_danger(self):
        world = World(name="TestWorld", year=1000)
        sim = Simulator(world, events_per_year=0, seed=1)
        forest_locs = [loc for loc in world.grid.values() if loc.region_type == "forest"]
        if not forest_locs:
            pytest.skip("No forest locations in default world")
        loc = forest_locs[0]
        original_danger = loc.danger
        sim._apply_seasonal_modifiers(10)  # October = autumn
        assert loc.danger > original_danger or loc.danger == 100
        sim._revert_seasonal_modifiers()
        assert loc.danger == original_danger

    def test_summer_sea_increases_traffic(self):
        world = World(name="TestWorld", year=1000)
        sim = Simulator(world, events_per_year=0, seed=1)
        sea_locs = [loc for loc in world.grid.values() if loc.region_type == "sea"]
        if not sea_locs:
            pytest.skip("No sea locations in default world")
        loc = sea_locs[0]
        original_traffic = loc.traffic
        sim._apply_seasonal_modifiers(7)  # July = summer
        assert loc.traffic > original_traffic or loc.traffic == 100
        sim._revert_seasonal_modifiers()
        assert loc.traffic == original_traffic

    def test_winter_forest_increases_danger(self):
        world = World(name="TestWorld", year=1000)
        sim = Simulator(world, events_per_year=0, seed=1)
        forest_locs = [loc for loc in world.grid.values() if loc.region_type == "forest"]
        if not forest_locs:
            pytest.skip("No forest locations in default world")
        loc = forest_locs[0]
        original_danger = loc.danger
        sim._apply_seasonal_modifiers(1)  # January = winter
        assert loc.danger > original_danger or loc.danger == 100
        sim._revert_seasonal_modifiers()
        assert loc.danger == original_danger

    def test_get_season_helper(self):
        assert World.get_season(1) == "winter"
        assert World.get_season(3) == "spring"
        assert World.get_season(7) == "summer"
        assert World.get_season(10) == "autumn"
        assert World.get_season(12) == "winter"

    def test_run_year_applies_seasonal_modifiers_with_event_months(self):
        world = World(name="TestWorld", year=1000)
        sim = Simulator(world, events_per_year=3, seed=123)
        applied_months = []
        original_apply = sim._apply_seasonal_modifiers

        def _tracking_apply(month):
            applied_months.append(month)
            return original_apply(month)

        sim._apply_seasonal_modifiers = _tracking_apply
        sim._run_year()
        # All 12 months should be observed since _run_year now processes every month
        assert len(applied_months) == 12
        assert set(applied_months) == set(range(1, 13))


# ---------------------------------------------------------------------------
# Recovery stages (design §8)
# ---------------------------------------------------------------------------

class TestStagedInjuryRecovery:
    """Design §8: Staged recovery serious→injured→none."""

    def test_serious_can_recover_to_injured(self):
        world = World(name="TestWorld", year=1000)
        char = Character(
            name="Wounded", age=30, gender="male", race="Human", job="Warrior",
            strength=50, dexterity=50, constitution=50,
            injury_status="serious",
        )
        world.add_character(char)
        sim = Simulator(world, events_per_year=0, seed=1)
        # Run many years to get the 30% recovery
        recovered = False
        for _ in range(50):
            sim._recover_injuries()
            if char.injury_status == "injured":
                recovered = True
                break
        assert recovered, "Expected serious→injured recovery within 50 attempts"

    def test_dying_not_recovered_by_recover_injuries(self):
        world = World(name="TestWorld", year=1000)
        char = Character(
            name="Dying", age=30, gender="male", race="Human", job="Warrior",
            strength=50, dexterity=50, constitution=50,
            injury_status="dying",
        )
        world.add_character(char)
        sim = Simulator(world, events_per_year=0, seed=1)
        sim._recover_injuries()
        assert char.injury_status == "dying"

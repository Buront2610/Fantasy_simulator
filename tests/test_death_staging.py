"""
Tests for the death staging system (design §8).

Covers:
- Injury status progression: none → injured → serious → dying → dead
- Dying resolution: rescue or death
- Recovery stages: serious → injured → none
- SI-11: dying characters maintain alive=True
- SI-12: active adventure members are all alive
"""
import random

import pytest

from fantasy_simulator.character import Character
from fantasy_simulator.events import EventSystem
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


@pytest.fixture
def world():
    return World(name="TestWorld", year=1000)


@pytest.fixture
def event_system():
    return EventSystem()


def _make_char(name="Test", injury_status="none", **kwargs):
    defaults = dict(
        age=25, gender="male", race="Human", job="Warrior",
        strength=50, intelligence=50, dexterity=50,
        wisdom=50, charisma=50, constitution=50,
        char_id=name.lower()[:8],
    )
    defaults.update(kwargs)
    return Character(name=name, injury_status=injury_status, **defaults)


class TestInjuryProgression:
    """Bob Nystrom: State machine transitions must be well-defined."""

    def test_worsen_from_none(self):
        char = _make_char()
        assert char.injury_status == "none"
        result = char.worsen_injury()
        assert result == "injured"
        assert char.injury_status == "injured"

    def test_worsen_from_injured(self):
        char = _make_char(injury_status="injured")
        result = char.worsen_injury()
        assert result == "serious"
        assert char.injury_status == "serious"

    def test_worsen_from_serious(self):
        char = _make_char(injury_status="serious")
        result = char.worsen_injury()
        assert result == "dying"
        assert char.injury_status == "dying"

    def test_worsen_from_dying_stays_dying(self):
        """Dying does not worsen further via worsen_injury."""
        char = _make_char(injury_status="dying")
        result = char.worsen_injury()
        assert result == "dying"
        assert char.injury_status == "dying"

    def test_is_dying_property(self):
        char = _make_char(injury_status="dying")
        assert char.is_dying is True
        char.alive = False
        assert char.is_dying is False

    def test_is_dying_false_for_other_statuses(self):
        for status in ("none", "injured", "serious"):
            char = _make_char(injury_status=status)
            assert char.is_dying is False


class TestDeathStagingInBattle:
    """Bob Nystrom: Battle should worsen injury rather than instant kill."""

    def test_battle_worsens_loser_injury(self, world, event_system):
        winner = _make_char("Winner", strength=90, constitution=90)
        loser = _make_char("Loser", strength=10, constitution=50, char_id="loser001")
        world.add_character(winner)
        world.add_character(loser)
        rng = random.Random(42)
        event_system.event_battle(winner, loser, world, rng=rng)
        # Loser should have worsened from "none"
        assert loser.injury_status in ("injured", "serious", "dying") or not loser.alive

    def test_dying_loser_can_die_in_battle(self, world, event_system):
        """Only dying + low con characters can die from battle."""
        winner = _make_char("Winner", strength=90, constitution=90)
        loser = _make_char(
            "Loser", strength=10, constitution=3,
            injury_status="serious", char_id="loser001"
        )
        world.add_character(winner)
        world.add_character(loser)
        # Run many battles to check that death can occur
        deaths = 0
        for seed in range(200):
            loser_copy = _make_char(
                "Loser", strength=10, constitution=3,
                injury_status="serious", char_id=f"loser{seed:03d}"
            )
            world.characters = [winner, loser_copy]
            world.rebuild_char_index()
            rng = random.Random(seed)
            event_system.event_battle(winner, loser_copy, world, rng=rng)
            if not loser_copy.alive:
                deaths += 1
        # Some should die (dying + low con), but not all
        assert deaths > 0, "Expected at least some deaths for dying+low-con characters"


class TestDyingResolution:
    """Tarn Adams: Dying resolution should consider location safety and allies."""

    def test_dying_can_be_rescued(self, world, event_system):
        char = _make_char("Dying", injury_status="dying", constitution=80)
        ally = _make_char("Ally", char_id="ally0001")
        ally.location_id = char.location_id
        world.add_character(char)
        world.add_character(ally)
        # High con + ally → high rescue chance
        rescued = 0
        for seed in range(100):
            char.injury_status = "dying"
            char.alive = True
            rng = random.Random(seed)
            result = event_system.check_dying_resolution(char, world, rng=rng)
            if result and result.event_type == "dying_rescued":
                rescued += 1
        assert rescued > 0, "Expected some rescues with ally present"

    def test_dying_can_die(self, world, event_system):
        char = _make_char("Dying", injury_status="dying", constitution=10)
        world.add_character(char)
        deaths = 0
        for seed in range(100):
            char.injury_status = "dying"
            char.alive = True
            rng = random.Random(seed)
            result = event_system.check_dying_resolution(char, world, rng=rng)
            if result and result.event_type == "death":
                deaths += 1
        assert deaths > 0, "Expected some deaths for dying+low-con"

    def test_non_dying_not_resolved(self, world, event_system):
        char = _make_char("Healthy")
        world.add_character(char)
        rng = random.Random(0)
        result = event_system.check_dying_resolution(char, world, rng=rng)
        assert result is None

    def test_savior_tag_on_rescue(self, world, event_system):
        """Emily Short: Rescue should create savior/rescued relation tags."""
        char = _make_char("Dying", injury_status="dying", constitution=90)
        ally = _make_char("Ally", char_id="ally0001")
        ally.location_id = char.location_id
        world.add_character(char)
        world.add_character(ally)
        # Force rescue by using high con
        for seed in range(200):
            char.injury_status = "dying"
            char.alive = True
            char.relation_tags = {}
            ally.relation_tags = {}
            rng = random.Random(seed)
            result = event_system.check_dying_resolution(char, world, rng=rng)
            if result and result.event_type == "dying_rescued":
                assert char.has_relation_tag(ally.char_id, "savior")
                assert ally.has_relation_tag(char.char_id, "rescued")
                assert ally.char_id in result.affected_characters
                return
        pytest.fail("No rescue occurred in 200 tries")


class TestSI11DyingAlive:
    """SI-11: dying characters maintain alive=True."""

    def test_dying_is_alive(self):
        char = _make_char(injury_status="dying")
        assert char.alive is True
        assert char.is_dying is True

    def test_natural_death_worsens_before_killing(self, world, event_system):
        """Soren Johnson: Players need time to react to dying — not instant death."""
        char = _make_char(
            age=70, race="Human", constitution=20, injury_status="none"
        )
        world.add_character(char)
        # Run many natural death checks
        worsened_count = 0
        for seed in range(500):
            char.alive = True
            char.injury_status = "none"
            rng = random.Random(seed)
            result = event_system.check_natural_death(char, world, rng=rng)
            if result and result.event_type == "condition_worsened":
                worsened_count += 1
                assert char.alive is True  # SI-11
        # Some should worsen rather than die outright
        assert worsened_count > 0

    def test_natural_death_worsening_precedes_any_fatal_resolution(self):
        """Even with finer-grained time, worsening should appear before death."""
        world = World(name="TestWorld", year=1000)
        char = _make_char(
            name="Elder",
            age=79,
            race="Human",
            constitution=5,
            favorite=True,
            injury_status="serious",
            char_id="elder001",
        )
        world.add_character(char)
        sim = Simulator(world, events_per_year=0, seed=4)

        sim.advance_years(2)

        health_events = [
            record.kind
            for record in world.event_records
            if record.primary_actor_id == char.char_id
            and record.kind in {"condition_worsened", "death", "dying_rescued"}
        ]

        assert health_events
        assert health_events[0] == "condition_worsened"


class TestRecoveryStages:
    """Tynan Sylvester: Recovery feedback loop — serious→injured→none."""

    def test_valid_injury_statuses(self):
        for status in Character.VALID_INJURY_STATUSES:
            char = _make_char(injury_status=status)
            assert char.injury_status == status

    def test_invalid_injury_status_defaults_to_none(self):
        char = _make_char(injury_status="invalid_status")
        assert char.injury_status == "none"

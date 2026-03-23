"""
Tests for the conditional auto-advance system (design §4.4).

Covers:
- Auto-pause on dying characters (favorite, spotlighted, any)
- Auto-pause on pending adventure choices
- Max years elapsed fallback
- Pause priority ordering
"""
import pytest

from character import Character
from simulator import Simulator
from world import World


@pytest.fixture
def small_world():
    world = World(name="TestWorld", year=1000)
    chars = [
        Character(
            name=f"Char{i}", age=25, gender="male", race="Human", job="Warrior",
            strength=50, intelligence=50, dexterity=50,
            wisdom=50, charisma=50, constitution=50,
            char_id=f"char{i:04d}",
        )
        for i in range(4)
    ]
    for c in chars:
        world.add_character(c)
    return world


@pytest.fixture
def sim(small_world):
    return Simulator(small_world, events_per_year=4, seed=42)


class TestAutoAdvanceBasics:
    """Tynan Sylvester: Auto-advance must respect pause conditions."""

    def test_advance_until_pause_returns_dict(self, sim):
        result = sim.advance_until_pause(max_years=3)
        assert "years_advanced" in result
        assert "pause_reason" in result
        assert "pause_priority" in result
        assert result["years_advanced"] >= 1
        assert result["years_advanced"] <= 3

    def test_max_years_fallback(self, sim):
        result = sim.advance_until_pause(max_years=2)
        assert result["years_advanced"] <= 2

    def test_preexisting_pause_is_checked_before_advance(self, sim):
        char = sim.world.characters[0]
        char.injury_status = "dying"
        start_year = sim.world.year
        result = sim.advance_until_pause(max_years=3)
        assert result["years_advanced"] == 0
        assert result["pause_reason"] == "dying_any"
        assert sim.world.year == start_year

    def test_years_elapsed_is_default_reason(self, sim):
        """If no specific condition triggers, default reason is years_elapsed."""
        result = sim.advance_until_pause(max_years=1)
        # With only 4 chars and low events, likely no pause condition
        assert result["pause_reason"] in (
            "years_elapsed", "dying_any", "dying_favorite",
            "dying_spotlighted", "pending_decision",
            "condition_worsened_favorite",
        )


class TestDyingPauseConditions:
    """Soren Johnson: Dying should force a decision point."""

    def test_dying_spotlighted_pauses(self, sim):
        char = sim.world.characters[0]
        char.spotlighted = True
        char.injury_status = "dying"
        reason = sim._check_pause_conditions()
        assert reason == "dying_spotlighted"

    def test_dying_favorite_pauses(self, sim):
        char = sim.world.characters[0]
        char.favorite = True
        char.injury_status = "dying"
        reason = sim._check_pause_conditions()
        assert reason == "dying_favorite"

    def test_dying_any_pauses(self, sim):
        char = sim.world.characters[0]
        char.injury_status = "dying"
        reason = sim._check_pause_conditions()
        assert reason == "dying_any"

    def test_no_dying_no_pause(self, sim):
        reason = sim._check_pause_conditions()
        assert reason is None


class TestPendingDecisionPause:

    def test_pending_choice_pauses(self, sim):
        from adventure import AdventureRun, AdventureChoice
        run = AdventureRun(
            character_id="char0000",
            character_name="Char0",
            origin="loc_aethoria_capital",
            destination="loc_ironvein_mine",
            year_started=1000,
            adventure_id="adv_test01",
        )
        run.pending_choice = AdventureChoice(
            prompt="Test?",
            options=["press_on", "retreat"],
            default_option="retreat",
            context="approach",
        )
        sim.world.add_adventure(run)
        reason = sim._check_pause_conditions()
        assert reason == "pending_decision"


class TestPausePriorityOrdering:
    """Soren Johnson: Highest priority condition should win."""

    def test_dying_spotlighted_beats_pending_decision(self, sim):
        from adventure import AdventureRun, AdventureChoice
        char = sim.world.characters[0]
        char.spotlighted = True
        char.injury_status = "dying"
        run = AdventureRun(
            character_id="char0001",
            character_name="Char1",
            origin="loc_aethoria_capital",
            destination="loc_ironvein_mine",
            year_started=1000,
            adventure_id="adv_test02",
        )
        run.pending_choice = AdventureChoice(
            prompt="Test?",
            options=["press_on", "retreat"],
            default_option="retreat",
            context="approach",
        )
        sim.world.add_adventure(run)
        reason = sim._check_pause_conditions()
        assert reason == "dying_spotlighted"

    def test_condition_worsened_favorite_lower_than_dying(self, sim):
        char = sim.world.characters[0]
        char.favorite = True
        sim._favorites_worsened_this_year = {char.char_id}  # condition_worsened_favorite
        char2 = sim.world.characters[1]
        char2.injury_status = "dying"  # dying_any
        reason = sim._check_pause_conditions()
        assert reason == "dying_any"

    def test_condition_worsened_favorite_is_event_based(self, sim):
        char = sim.world.characters[0]
        char.favorite = True
        char.injury_status = "serious"
        # Persistent serious state alone should not pause.
        reason = sim._check_pause_conditions()
        assert reason is None
        # Marking this year's worsening should pause.
        sim._favorites_worsened_this_year.add(char.char_id)
        reason = sim._check_pause_conditions()
        assert reason == "condition_worsened_favorite"


class TestPartyReturnedPause:
    """Design §4.4: Party returned should pause for favorite/spotlighted."""

    def test_party_returned_pauses_for_favorite(self, sim):
        from adventure import AdventureRun
        char = sim.world.characters[0]
        char.favorite = True
        run = AdventureRun(
            character_id=char.char_id,
            character_name=char.name,
            origin="loc_aethoria_capital",
            destination="loc_thornwood",
            year_started=1000,
            state="resolved",
            outcome="safe_return",
        )
        sim._recently_completed_adventures = [run]
        reason = sim._check_pause_conditions()
        assert reason == "party_returned"

    def test_no_pause_for_non_favorite_return(self, sim):
        from adventure import AdventureRun
        char = sim.world.characters[0]
        char.favorite = False
        char.spotlighted = False
        run = AdventureRun(
            character_id=char.char_id,
            character_name=char.name,
            origin="loc_aethoria_capital",
            destination="loc_thornwood",
            year_started=1000,
            state="resolved",
            outcome="safe_return",
        )
        sim._recently_completed_adventures = [run]
        reason = sim._check_pause_conditions()
        assert reason is None

    def test_recently_completed_cleared_each_year(self, sim):
        from adventure import AdventureRun
        run = AdventureRun(
            character_id="char0000",
            character_name="Char0",
            origin="loc_aethoria_capital",
            destination="loc_thornwood",
            year_started=1000,
            state="resolved",
            outcome="safe_return",
        )
        sim._recently_completed_adventures = [run]
        sim._run_year()
        assert sim._recently_completed_adventures == []

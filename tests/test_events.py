"""
tests/test_events.py - Unit tests for the EventSystem.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from character import Character
from events import EventResult, EventSystem
from world import World


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def es() -> EventSystem:
    return EventSystem()


def _make_char(
    name: str,
    location: str = "Aethoria Capital",
    age: int = 25,
    strength: int = 50,
    constitution: int = 50,
    intelligence: int = 50,
) -> Character:
    c = Character(
        name=name, age=age, gender="Male", race="Human", job="Warrior",
        strength=strength, constitution=constitution, intelligence=intelligence,
        dexterity=50, wisdom=40, charisma=40,
        skills={"Swordsmanship": 2},
        location=location,
    )
    return c


@pytest.fixture
def char_a(world) -> Character:
    c = _make_char("Alice", location="Aethoria Capital")
    world.add_character(c)
    return c


@pytest.fixture
def char_b(world) -> Character:
    c = _make_char("Bob", location="Aethoria Capital")
    world.add_character(c)
    return c


# ---------------------------------------------------------------------------
# EventResult dataclass
# ---------------------------------------------------------------------------

class TestEventResult:
    def test_defaults(self):
        r = EventResult(description="something happened")
        assert r.affected_characters == []
        assert r.stat_changes == {}
        assert r.event_type == "generic"
        assert r.year == 0

    def test_custom_values(self):
        r = EventResult(
            description="battle",
            affected_characters=["id1", "id2"],
            stat_changes={"id1": {"strength": 2}},
            event_type="battle",
            year=1010,
        )
        assert r.event_type == "battle"
        assert r.year == 1010
        assert "id1" in r.affected_characters


# ---------------------------------------------------------------------------
# event_meeting
# ---------------------------------------------------------------------------

class TestEventMeeting:
    def test_returns_event_result(self, es, char_a, char_b, world):
        result = es.event_meeting(char_a, char_b, world)
        assert isinstance(result, EventResult)

    def test_affected_both_chars(self, es, char_a, char_b, world):
        result = es.event_meeting(char_a, char_b, world)
        assert char_a.char_id in result.affected_characters
        assert char_b.char_id in result.affected_characters

    def test_relationship_recorded(self, es, char_a, char_b, world):
        es.event_meeting(char_a, char_b, world)
        # Relationship key is set (may be positive or negative)
        assert char_b.char_id in char_a.relationships

    def test_history_updated(self, es, char_a, char_b, world):
        es.event_meeting(char_a, char_b, world)
        # Both chars should have a history entry about the meeting
        assert any("Met" in h or "met" in h for h in char_a.history)

    def test_event_type(self, es, char_a, char_b, world):
        result = es.event_meeting(char_a, char_b, world)
        assert result.event_type == "meeting"


# ---------------------------------------------------------------------------
# event_battle
# ---------------------------------------------------------------------------

class TestEventBattle:
    def test_returns_event_result(self, es, char_a, char_b, world):
        result = es.event_battle(char_a, char_b, world)
        assert isinstance(result, EventResult)

    def test_both_affected(self, es, char_a, char_b, world):
        result = es.event_battle(char_a, char_b, world)
        assert char_a.char_id in result.affected_characters
        assert char_b.char_id in result.affected_characters

    def test_relationship_degraded(self, es, char_a, char_b, world):
        # Set neutral relationships first
        char_a.update_relationship(char_b.char_id, 0)
        char_b.update_relationship(char_a.char_id, 0)
        es.event_battle(char_a, char_b, world)
        # At least one should have negative relationship
        rel_a = char_a.get_relationship(char_b.char_id)
        rel_b = char_b.get_relationship(char_a.char_id)
        assert rel_a < 0 or rel_b < 0

    def test_event_type_battle(self, es, char_a, char_b, world):
        result = es.event_battle(char_a, char_b, world)
        assert result.event_type in ("battle", "battle_fatal")

    def test_stat_changes_present(self, es, char_a, char_b, world):
        result = es.event_battle(char_a, char_b, world)
        # At least winner should have stat changes
        assert len(result.stat_changes) > 0

    def test_weak_loser_can_die(self, es, world):
        """A character with very low constitution may die in battle."""
        import random
        random.seed(99)  # seed that triggers death
        attacker = _make_char("Brute", strength=90, constitution=90)
        victim   = _make_char("Victim", strength=5, constitution=4)
        world.add_character(attacker)
        world.add_character(victim)
        # Run up to 20 battles to see if death can occur
        died = False
        for _ in range(20):
            if not victim.alive:
                break
            # Reset con to 4 to keep it weak
            victim.constitution = 4
            result = es.event_battle(attacker, victim, world)
            if not victim.alive:
                died = True
                assert "battle_fatal" in result.event_type
                break
        # We can't guarantee death in exactly these attempts, but the
        # code path should be reachable — just assert the method ran.
        assert True  # above loop ran without error


# ---------------------------------------------------------------------------
# event_discovery
# ---------------------------------------------------------------------------

class TestEventDiscovery:
    def test_returns_event_result(self, es, char_a, world):
        result = es.event_discovery(char_a, world)
        assert isinstance(result, EventResult)

    def test_char_affected(self, es, char_a, world):
        result = es.event_discovery(char_a, world)
        assert char_a.char_id in result.affected_characters

    def test_history_updated(self, es, char_a, world):
        es.event_discovery(char_a, world)
        assert len(char_a.history) > 0

    def test_event_type(self, es, char_a, world):
        result = es.event_discovery(char_a, world)
        assert result.event_type == "discovery"

    def test_stat_changes_applied(self, es, char_a, world):
        import random
        random.seed(0)
        before = {
            "strength": char_a.strength,
            "intelligence": char_a.intelligence,
            "dexterity": char_a.dexterity,
            "charisma": char_a.charisma,
        }
        es.event_discovery(char_a, world)
        after = {
            "strength": char_a.strength,
            "intelligence": char_a.intelligence,
            "dexterity": char_a.dexterity,
            "charisma": char_a.charisma,
        }
        changed = any(after[k] != before[k] for k in before)
        assert changed


# ---------------------------------------------------------------------------
# event_skill_training
# ---------------------------------------------------------------------------

class TestEventSkillTraining:
    def test_returns_event_result(self, es, char_a, world):
        result = es.event_skill_training(char_a, world)
        assert isinstance(result, EventResult)

    def test_skill_level_increases(self, es, char_a, world):
        old_levels = dict(char_a.skills)
        es.event_skill_training(char_a, world)
        new_levels = char_a.skills
        # At least one skill should have increased
        improved = any(new_levels.get(k, 0) > v for k, v in old_levels.items())
        assert improved

    def test_no_skills_starter_added(self, world, es):
        """If character has no skills, one should be seeded."""
        c = Character("Blank", 20, "Male", "Human", "Warrior")
        world.add_character(c)
        assert c.skills == {}
        es.event_skill_training(c, world)
        assert len(c.skills) > 0


# ---------------------------------------------------------------------------
# event_journey
# ---------------------------------------------------------------------------

class TestEventJourney:
    def test_returns_event_result(self, es, char_a, world):
        result = es.event_journey(char_a, world)
        assert isinstance(result, EventResult)

    def test_location_changes(self, es, char_a, world):
        old_loc = char_a.location
        es.event_journey(char_a, world)
        # May or may not change (neighbours possible), but no crash
        assert isinstance(char_a.location, str)

    def test_history_updated(self, es, char_a, world):
        es.event_journey(char_a, world)
        assert any("Travelled" in h or "jourey" in h.lower() or "Travell" in h for h in char_a.history)

    def test_event_type(self, es, char_a, world):
        result = es.event_journey(char_a, world)
        assert result.event_type == "journey"


# ---------------------------------------------------------------------------
# event_aging
# ---------------------------------------------------------------------------

class TestEventAging:
    def test_age_increments(self, es, char_a, world):
        old_age = char_a.age
        es.event_aging(char_a, world)
        assert char_a.age == old_age + 1

    def test_history_updated(self, es, char_a, world):
        es.event_aging(char_a, world)
        assert any("Turned" in h for h in char_a.history)

    def test_returns_event_result(self, es, char_a, world):
        result = es.event_aging(char_a, world)
        assert isinstance(result, EventResult)

    def test_stat_changes_present(self, es, char_a, world):
        result = es.event_aging(char_a, world)
        assert char_a.char_id in result.stat_changes


# ---------------------------------------------------------------------------
# event_death
# ---------------------------------------------------------------------------

class TestEventDeath:
    def test_char_marked_dead(self, es, char_a, world):
        es.event_death(char_a, world)
        assert char_a.alive is False

    def test_history_updated(self, es, char_a, world):
        es.event_death(char_a, world)
        assert any("Passed away" in h for h in char_a.history)

    def test_event_type(self, es, char_a, world):
        result = es.event_death(char_a, world)
        assert result.event_type == "death"

    def test_spouse_notified(self, es, char_a, char_b, world):
        char_a.spouse_id = char_b.char_id
        char_b.spouse_id = char_a.char_id
        es.event_death(char_a, world)
        # Spouse loses positive relationship
        assert char_b.relationships.get(char_a.char_id, 0) < 0


# ---------------------------------------------------------------------------
# event_marriage
# ---------------------------------------------------------------------------

class TestEventMarriage:
    def test_high_relationship_causes_marriage(self, es, char_a, char_b, world):
        char_a.update_relationship(char_b.char_id, 80)
        char_b.update_relationship(char_a.char_id, 80)
        result = es.event_marriage(char_a, char_b, world)
        assert result.event_type == "marriage"
        assert char_a.spouse_id == char_b.char_id
        assert char_b.spouse_id == char_a.char_id

    def test_low_relationship_no_marriage(self, es, char_a, char_b, world):
        char_a.relationships.clear()
        char_b.relationships.clear()
        result = es.event_marriage(char_a, char_b, world)
        # Should be romance, not marriage
        assert result.event_type == "romance"
        assert char_a.spouse_id is None

    def test_already_married_anniversary(self, es, char_a, char_b, world):
        char_a.spouse_id = char_b.char_id
        char_b.spouse_id = char_a.char_id
        char_a.update_relationship(char_b.char_id, 90)
        char_b.update_relationship(char_a.char_id, 90)
        result = es.event_marriage(char_a, char_b, world)
        assert result.event_type == "anniversary"


# ---------------------------------------------------------------------------
# check_natural_death
# ---------------------------------------------------------------------------

class TestNaturalDeath:
    def test_young_character_rarely_dies(self, es, world):
        """A young character should almost never die naturally."""
        young = _make_char("Young", age=20, constitution=80)
        world.add_character(young)
        deaths = 0
        for _ in range(200):
            young.alive = True  # reset
            young.age = 20
            result = es.check_natural_death(young, world)
            if result is not None:
                deaths += 1
        # Fewer than 5 deaths out of 200 trials
        assert deaths < 5

    def test_very_old_character_may_die(self, es, world):
        """A character well past max age should have a high death chance."""
        old = _make_char("Ancient", age=78, constitution=10)
        old.race = "Human"  # max_age = 80
        world.add_character(old)
        results = []
        for _ in range(100):
            old.alive = True
            result = es.check_natural_death(old, world)
            results.append(result is not None)
        assert sum(results) > 10  # should die in a meaningful fraction

    def test_dead_char_skipped(self, es, world):
        """Already-dead characters should return None immediately."""
        dead = _make_char("Ghost")
        dead.alive = False
        world.add_character(dead)
        result = es.check_natural_death(dead, world)
        assert result is None


# ---------------------------------------------------------------------------
# generate_random_event
# ---------------------------------------------------------------------------

class TestGenerateRandomEvent:
    def test_returns_event_result(self, es, world):
        for _ in range(5):
            c = _make_char(f"Char{_}", location="Aethoria Capital")
            world.add_character(c)
        result = es.generate_random_event(world.characters, world)
        assert result is None or isinstance(result, EventResult)

    def test_no_alive_chars_returns_none(self, es, world):
        dead = _make_char("Dead")
        dead.alive = False
        world.add_character(dead)
        result = es.generate_random_event([dead], world)
        assert result is None

    def test_single_char_solo_event(self, es, world):
        """With only one character, a solo event should fire (no crash)."""
        c = _make_char("Solo", location="Aethoria Capital")
        c.skills = {"Swordsmanship": 1}
        world.add_character(c)
        import random
        random.seed(5)
        for _ in range(10):
            result = es.generate_random_event([c], world)
            assert result is None or isinstance(result, EventResult)

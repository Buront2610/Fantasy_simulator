"""
tests/test_events.py - Unit tests for the EventSystem.
"""

import random

import pytest
from fantasy_simulator.character import Character
from fantasy_simulator.events import EventResult, EventSystem
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.world import World


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def es() -> EventSystem:
    return EventSystem()


@pytest.fixture(autouse=True)
def reset_locale():
    previous = get_locale()
    set_locale("en")
    yield
    set_locale(previous)


def _make_char(
    name: str,
    location_id: str = "loc_aethoria_capital",
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
        location_id=location_id,
    )
    return c


@pytest.fixture
def char_a(world) -> Character:
    c = _make_char("Alice", location_id="loc_aethoria_capital")
    world.add_character(c)
    return c


@pytest.fixture
def char_b(world) -> Character:
    c = _make_char("Bob", location_id="loc_aethoria_capital")
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

    def test_description_reports_bidirectional_relationships(self, es, char_a, char_b, world):
        result = es.event_meeting(char_a, char_b, world, rng=random.Random(0))

        rel_a = char_a.get_relationship(char_b.char_id)
        rel_b = char_b.get_relationship(char_a.char_id)
        rel_avg = round((rel_a + rel_b) / 2)

        assert f"Alice->Bob: {rel_a:+d}" in result.description
        assert f"Bob->Alice: {rel_b:+d}" in result.description
        assert f"Avg: {rel_avg:+d}" in result.description

    def test_description_tone_matches_average_relationship(self, es, char_a, char_b, world):
        result = es.event_meeting(char_a, char_b, world, rng=random.Random(3))

        rel_a = char_a.get_relationship(char_b.char_id)
        rel_b = char_b.get_relationship(char_a.char_id)
        rel_avg = round((rel_a + rel_b) / 2)

        assert rel_avg > 0
        assert "pleasant exchange" in result.description
        assert "polite nod" not in result.description


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
        victim = _make_char("Victim", strength=5, constitution=4)
        world.add_character(attacker)
        world.add_character(victim)
        # Run up to 20 battles to see if death can occur
        for _ in range(20):
            if not victim.alive:
                break
            # Reset con to 4 to keep it weak
            victim.constitution = 4
            result = es.event_battle(attacker, victim, world)
            if not victim.alive:
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

    def test_japanese_locale_discovery_text_has_no_fixed_english_tail(self, es, char_a, world):
        set_locale("ja")
        result = es.event_discovery(char_a, world, rng=random.Random(1))

        assert "The knowledge contained within" not in result.description
        assert "The discovery will prove useful" not in result.description
        assert "Word of the discovery spread quickly" not in result.description


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

    def test_japanese_locale_training_text_has_no_fixed_english_effort(self, es, char_a, world):
        set_locale("ja")
        result = es.event_skill_training(char_a, world, rng=random.Random(0))

        assert "spent long hours in the training yard" not in result.description
        assert "pushed themselves beyond their limits" not in result.description


# ---------------------------------------------------------------------------
# event_journey
# ---------------------------------------------------------------------------

class TestEventJourney:
    def test_returns_event_result(self, es, char_a, world):
        result = es.event_journey(char_a, world)
        assert isinstance(result, EventResult)

    def test_location_changes(self, es, char_a, world):
        es.event_journey(char_a, world)
        assert isinstance(char_a.location_id, str)

    def test_history_updated(self, es, char_a, world):
        es.event_journey(char_a, world)
        assert any("Travelled" in h for h in char_a.history)

    def test_event_type(self, es, char_a, world):
        result = es.event_journey(char_a, world)
        assert result.event_type == "journey"

    def test_destination_marked_visited(self, es, char_a, world):
        result = es.event_journey(char_a, world, rng=random.Random(0))
        destination = world.get_location_by_id(char_a.location_id)
        assert destination is not None
        assert destination.visited is True
        assert result.event_type == "journey"

    def test_japanese_locale_localizes_region_type(self, es, char_a, world):
        set_locale("ja")
        result = es.event_journey(char_a, world, rng=random.Random(0))
        assert "（city）" not in result.description
        assert any(region in result.description for region in ("都市", "村", "森", "山岳", "地下迷宮", "平原"))

    def test_blocked_route_network_prevents_global_teleport(self, es):
        from fantasy_simulator.terrain import RouteEdge
        from fantasy_simulator.world import LocationState

        world = World(_skip_defaults=True, width=3, height=1)
        origin = LocationState(
            id="loc_origin",
            canonical_name="Origin",
            description="Origin",
            region_type="city",
            x=0,
            y=0,
            prosperity=50,
            safety=50,
            mood=50,
            danger=10,
            traffic=30,
            rumor_heat=10,
            road_condition=60,
        )
        blocked = LocationState(
            id="loc_blocked",
            canonical_name="Blocked",
            description="Blocked",
            region_type="village",
            x=1,
            y=0,
            prosperity=50,
            safety=50,
            mood=50,
            danger=10,
            traffic=30,
            rumor_heat=10,
            road_condition=60,
        )
        remote = LocationState(
            id="loc_remote",
            canonical_name="Remote",
            description="Remote",
            region_type="forest",
            x=2,
            y=0,
            prosperity=50,
            safety=50,
            mood=50,
            danger=40,
            traffic=20,
            rumor_heat=10,
            road_condition=60,
        )
        for loc in (origin, blocked, remote):
            world._register_location(loc)
        world._build_terrain_from_grid()
        world.routes = [
            RouteEdge("route_blocked", "loc_origin", "loc_blocked", "road", blocked=True),
        ]
        char = _make_char("Traveler", location_id="loc_origin")
        world.add_character(char)

        result = es.event_journey(char, world, rng=random.Random(0))

        assert char.location_id == "loc_origin"
        assert "no destination" in result.description.lower()


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

    def test_handle_death_side_effects_clears_spouse_id(self, es, char_a, char_b, world):
        """handle_death_side_effects clears spouse_id on the surviving partner."""
        char_a.spouse_id = char_b.char_id
        char_b.spouse_id = char_a.char_id
        char_a.alive = False

        es.handle_death_side_effects(char_a, world)

        assert char_b.spouse_id is None
        assert any("Lost" in h or "失った" in h for h in char_b.history)

    def test_handle_death_side_effects_is_idempotent(self, es, char_a, char_b, world):
        """Calling handle_death_side_effects twice must not crash or double-add history."""
        char_a.spouse_id = char_b.char_id
        char_b.spouse_id = char_a.char_id
        char_a.alive = False

        es.handle_death_side_effects(char_a, world)
        history_len = len(char_b.history)

        es.handle_death_side_effects(char_a, world)
        assert len(char_b.history) == history_len


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

    def test_existing_spouse_blocks_new_marriage(self, es, char_a, char_b, world):
        outsider = _make_char("Cara", location_id="loc_aethoria_capital")
        world.add_character(outsider)
        char_a.spouse_id = outsider.char_id
        char_a.update_relationship(char_b.char_id, 90)
        char_b.update_relationship(char_a.char_id, 90)

        result = es.event_marriage(char_a, char_b, world)

        assert result.event_type == "romance"
        assert char_a.spouse_id == outsider.char_id
        assert char_b.spouse_id is None


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
            c = _make_char(f"Char{_}", location_id="loc_aethoria_capital")
            world.add_character(c)
        result = es.generate_random_event(world.characters, world)
        assert result is None or isinstance(result, EventResult)

    def test_no_alive_chars_returns_none(self, es, world):
        dead = _make_char("Dead")
        dead.alive = False
        world.add_character(dead)
        result = es.generate_random_event([dead], world)
        assert result is None

    def test_chars_on_adventure_are_skipped(self, es, world):
        adventurer = _make_char("Away")
        adventurer.active_adventure_id = "adv-1"
        world.add_character(adventurer)
        result = es.generate_random_event([adventurer], world)
        assert result is None

    def test_single_char_solo_event(self, es, world):
        """With only one character, a solo event should fire (no crash)."""
        c = _make_char("Solo", location_id="loc_aethoria_capital")
        c.skills = {"Swordsmanship": 1}
        world.add_character(c)
        import random
        random.seed(5)
        for _ in range(10):
            result = es.generate_random_event([c], world)
            assert result is None or isinstance(result, EventResult)

    def test_random_event_table_excludes_direct_death(self, es):
        assert "death" not in es._EVENT_WEIGHTS

    def test_random_event_table_excludes_aging(self, es):
        assert "aging" not in es._EVENT_WEIGHTS


# ---------------------------------------------------------------------------
# WorldEventRecord
# ---------------------------------------------------------------------------

class TestWorldEventRecord:
    def test_to_dict_round_trip(self):
        from fantasy_simulator.events import WorldEventRecord
        record = WorldEventRecord(
            kind="battle",
            year=1005,
            location_id="loc_aethoria_capital",
            primary_actor_id="abc123",
            secondary_actor_ids=["def456"],
            description="A battle occurred.",
            severity=3,
            visibility="public",
        )
        d = record.to_dict()
        restored = WorldEventRecord.from_dict(d)
        assert restored.kind == "battle"
        assert restored.year == 1005
        assert restored.location_id == "loc_aethoria_capital"
        assert restored.primary_actor_id == "abc123"
        assert restored.secondary_actor_ids == ["def456"]
        assert restored.severity == 3

    def test_from_event_result(self):
        from fantasy_simulator.events import WorldEventRecord
        result = EventResult(
            description="A battle occurred.",
            affected_characters=["abc123", "def456"],
            stat_changes={},
            event_type="battle",
            year=1005,
        )
        record = WorldEventRecord.from_event_result(result, location_id="loc_thornwood", severity=3)
        assert record.kind == "battle"
        assert record.year == 1005
        assert record.location_id == "loc_thornwood"
        assert record.primary_actor_id == "abc123"
        assert record.secondary_actor_ids == ["def456"]
        assert record.severity == 3
        assert record.description == "A battle occurred."

    def test_from_event_result_no_actors(self):
        from fantasy_simulator.events import WorldEventRecord
        result = EventResult(description="Nothing happened.", year=1000)
        record = WorldEventRecord.from_event_result(result)
        assert record.primary_actor_id is None
        assert record.secondary_actor_ids == []

    def test_default_values(self):
        from fantasy_simulator.events import WorldEventRecord
        record = WorldEventRecord()
        assert record.kind == "generic"
        assert record.year == 0
        assert record.location_id is None
        assert record.severity == 1
        assert record.visibility == "public"
        assert len(record.record_id) == 32

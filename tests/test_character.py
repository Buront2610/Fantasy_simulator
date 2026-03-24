"""
tests/test_character.py - Unit tests for the Character class.
"""

import pytest
from fantasy_simulator.character import Character, random_stats
from fantasy_simulator.i18n import get_locale, set_locale


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def hero() -> Character:
    """A basic human warrior for general-purpose testing."""
    return Character(
        name="Aldric Ashwood",
        age=25,
        gender="Male",
        race="Human",
        job="Warrior",
        strength=60,
        intelligence=30,
        dexterity=50,
        wisdom=35,
        charisma=40,
        constitution=65,
        skills={"Swordsmanship": 2, "Shield Block": 1},
        location_id="loc_aethoria_capital",
    )


@pytest.fixture
def mage() -> Character:
    """An elven mage."""
    return Character(
        name="Aelindra Moonwhisper",
        age=120,
        gender="Female",
        race="Elf",
        job="Mage",
        strength=20,
        intelligence=85,
        dexterity=55,
        wisdom=70,
        charisma=50,
        constitution=25,
        skills={"Fireball": 4, "Mana Control": 3},
    )


@pytest.fixture(autouse=True)
def reset_locale():
    previous = get_locale()
    set_locale("en")
    yield
    set_locale(previous)


# ---------------------------------------------------------------------------
# Construction & attributes
# ---------------------------------------------------------------------------

class TestCharacterConstruction:
    def test_basic_attributes(self, hero):
        assert hero.name == "Aldric Ashwood"
        assert hero.age == 25
        assert hero.gender == "Male"
        assert hero.race == "Human"
        assert hero.job == "Warrior"
        assert hero.alive is True

    def test_stat_clamping_high(self):
        c = Character("Test", 20, "Male", "Human", "Warrior", strength=200)
        assert c.strength == 100

    def test_stat_clamping_low(self):
        c = Character("Test", 20, "Male", "Human", "Warrior", constitution=-50)
        assert c.constitution == 1

    def test_default_location(self):
        c = Character("Test", 20, "Male", "Human", "Warrior")
        assert c.location_id == "loc_aethoria_capital"

    def test_auto_generated_id(self, hero):
        assert hero.char_id is not None
        assert len(hero.char_id) > 0

    def test_unique_ids(self):
        c1 = Character("A", 20, "Male", "Human", "Warrior")
        c2 = Character("B", 20, "Male", "Human", "Warrior")
        assert c1.char_id != c2.char_id

    def test_explicit_char_id(self):
        c = Character("Test", 20, "Male", "Human", "Warrior", char_id="abc123")
        assert c.char_id == "abc123"

    def test_skills_default_empty(self):
        c = Character("Test", 20, "Male", "Human", "Warrior")
        assert c.skills == {}

    def test_relationships_default_empty(self):
        c = Character("Test", 20, "Male", "Human", "Warrior")
        assert c.relationships == {}

    def test_history_default_empty(self):
        c = Character("Test", 20, "Male", "Human", "Warrior")
        assert c.history == []

    def test_spouse_id_default_none(self):
        c = Character("Test", 20, "Male", "Human", "Warrior")
        assert c.spouse_id is None


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------

class TestCharacterProperties:
    def test_combat_power_positive(self, hero):
        assert hero.combat_power > 0

    def test_combat_power_formula(self, hero):
        expected = (hero.strength * 2 + hero.dexterity + hero.constitution) // 4
        assert hero.combat_power == expected

    def test_max_age_human(self, hero):
        assert hero.max_age == 80

    def test_max_age_elf(self, mage):
        assert mage.max_age == 600

    def test_max_age_unknown_race(self):
        c = Character("Test", 20, "Male", "Gnome", "Warrior")
        assert c.max_age == 80  # fallback


# ---------------------------------------------------------------------------
# Methods
# ---------------------------------------------------------------------------

class TestLevelUpSkill:
    def test_increase_existing_skill(self, hero):
        hero.level_up_skill("Swordsmanship", 1)
        assert hero.skills["Swordsmanship"] == 3

    def test_create_new_skill(self, hero):
        hero.level_up_skill("Archery", 2)
        assert hero.skills["Archery"] == 2

    def test_cap_at_10(self, hero):
        hero.skills["Swordsmanship"] = 9
        hero.level_up_skill("Swordsmanship", 5)
        assert hero.skills["Swordsmanship"] == 10

    def test_already_max_message(self, hero):
        hero.skills["Swordsmanship"] = 10
        msg = hero.level_up_skill("Swordsmanship", 1)
        assert "Swordsmanship" in msg
        assert hero.skills["Swordsmanship"] == 10

    def test_return_message_contains_name(self, hero):
        msg = hero.level_up_skill("Swordsmanship")
        assert hero.name in msg

    def test_skill_message_localizes_in_japanese(self, hero):
        set_locale("ja")
        msg = hero.level_up_skill("Swordsmanship")
        assert "レベル" in msg


class TestUpdateRelationship:
    def test_positive_delta(self, hero, mage):
        hero.update_relationship(mage.char_id, 30)
        assert hero.relationships[mage.char_id] == 30

    def test_negative_delta(self, hero, mage):
        hero.update_relationship(mage.char_id, -40)
        assert hero.relationships[mage.char_id] == -40

    def test_clamp_max(self, hero, mage):
        hero.update_relationship(mage.char_id, 80)
        hero.update_relationship(mage.char_id, 80)  # would exceed 100
        assert hero.relationships[mage.char_id] == 100

    def test_clamp_min(self, hero, mage):
        hero.update_relationship(mage.char_id, -80)
        hero.update_relationship(mage.char_id, -80)
        assert hero.relationships[mage.char_id] == -100

    def test_get_relationship_default(self, hero, mage):
        assert hero.get_relationship(mage.char_id) == 0

    def test_get_relationship_after_update(self, hero, mage):
        hero.update_relationship(mage.char_id, 50)
        assert hero.get_relationship(mage.char_id) == 50


class TestAddHistory:
    def test_append_event(self, hero):
        hero.add_history("Year 1: Slew a goblin.")
        assert "Year 1: Slew a goblin." in hero.history

    def test_multiple_events_ordered(self, hero):
        hero.add_history("Event A")
        hero.add_history("Event B")
        assert hero.history[-1] == "Event B"
        assert hero.history[-2] == "Event A"


class TestApplyStatDelta:
    def test_positive_delta(self, hero):
        old = hero.strength
        hero.apply_stat_delta({"strength": 10})
        assert hero.strength == old + 10

    def test_negative_delta(self, hero):
        hero.apply_stat_delta({"constitution": -5})
        assert hero.constitution == 60  # 65 - 5

    def test_clamped_below_one(self):
        c = Character("Test", 20, "Male", "Human", "Warrior", strength=2)
        c.apply_stat_delta({"strength": -50})
        assert c.strength == 1

    def test_clamped_above_hundred(self, hero):
        hero.apply_stat_delta({"intelligence": 200})
        assert hero.intelligence == 100

    def test_ignores_unknown_stats(self, hero):
        # Should not raise
        hero.apply_stat_delta({"luck": 10, "mana": 5})


class TestStatBlockRelations:
    def test_stat_block_resolves_relation_names_when_lookup_provided(self, hero, mage):
        hero.add_relation_tag(mage.char_id, "friend")
        block = hero.stat_block(char_name_lookup={mage.char_id: mage.name})

        assert mage.name in block
        assert mage.char_id[:8] not in block


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_contains_all_fields(self, hero):
        d = hero.to_dict()
        expected_keys = {
            "char_id", "name", "age", "gender", "race", "job",
            "strength", "intelligence", "dexterity", "wisdom",
            "charisma", "constitution", "skills", "relationships",
            "alive", "location_id", "favorite", "spotlighted", "playable",
            "history", "spouse_id",
            "injury_status", "active_adventure_id",
        }
        assert expected_keys.issubset(set(d.keys()))

    def test_round_trip(self, hero):
        d = hero.to_dict()
        restored = Character.from_dict(d)
        assert restored.name == hero.name
        assert restored.char_id == hero.char_id
        assert restored.strength == hero.strength
        assert restored.skills == hero.skills
        assert restored.alive == hero.alive

    def test_from_dict_minimal(self):
        data = {
            "name": "Test",
            "age": 30,
            "gender": "Male",
            "race": "Human",
            "job": "Warrior",
        }
        c = Character.from_dict(data)
        assert c.name == "Test"
        assert c.age == 30

    def test_to_dict_alive_false(self, hero):
        hero.alive = False
        d = hero.to_dict()
        assert d["alive"] is False

    def test_to_dict_spouse_id(self, hero, mage):
        hero.spouse_id = mage.char_id
        d = hero.to_dict()
        assert d["spouse_id"] == mage.char_id

    def test_favorite_flag_round_trip(self):
        char = Character("Test", 20, "Male", "Human", "Warrior", favorite=True)
        restored = Character.from_dict(char.to_dict())
        assert restored.favorite is True
        assert restored.spotlighted is False
        assert restored.playable is False

    def test_flags_default_false_on_old_save(self):
        data = {
            "name": "Legacy",
            "age": 30,
            "gender": "Male",
            "race": "Human",
            "job": "Warrior",
            "location": "Aethoria Capital",
        }
        restored = Character.from_dict(data)
        assert restored.favorite is False
        assert restored.spotlighted is False
        assert restored.playable is False


# ---------------------------------------------------------------------------
# random_stats helper
# ---------------------------------------------------------------------------

class TestRandomStats:
    def test_returns_all_six_stats(self):
        stats = random_stats()
        assert set(stats.keys()) == {
            "strength", "intelligence", "dexterity",
            "wisdom", "charisma", "constitution",
        }

    def test_values_in_range(self):
        for _ in range(50):
            stats = random_stats(base=10, spread=20)
            for v in stats.values():
                assert 1 <= v <= 100

    def test_race_bonuses_applied(self):
        import random as _random
        _random.seed(42)
        stats_no_bonus = random_stats(base=50, spread=0)
        _random.seed(42)
        stats_with_bonus = random_stats(base=50, spread=0, race_bonuses={"strength": 10})
        assert stats_with_bonus["strength"] == stats_no_bonus["strength"] + 10

    def test_rng_injection_reproducibility(self):
        import random as _random
        rng1 = _random.Random(123)
        rng2 = _random.Random(123)
        stats1 = random_stats(rng=rng1)
        stats2 = random_stats(rng=rng2)
        assert stats1 == stats2

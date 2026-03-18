"""
tests/test_character_creator.py - Unit tests for CharacterCreator.
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from character_creator import CharacterCreator


class TestCharacterCreator:
    def test_random_character_history_has_no_year_zero_prefix(self):
        creator = CharacterCreator()
        char = creator.create_random(name="Aldric")
        assert not any(entry.startswith("Year 0:") for entry in char.history)

    def test_template_character_history_has_no_year_zero_prefix(self):
        creator = CharacterCreator()
        char = creator.create_from_template("warrior", name="Aldric")
        assert not any(entry.startswith("Year 0:") for entry in char.history)


class TestCreateRandomReproducibility:
    def test_same_seed_produces_same_character(self):
        creator = CharacterCreator()
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        c1 = creator.create_random(rng=rng1)
        c2 = creator.create_random(rng=rng2)
        assert c1.char_id == c2.char_id
        assert c1.name == c2.name
        assert c1.gender == c2.gender
        assert c1.race == c2.race
        assert c1.job == c2.job
        assert c1.age == c2.age
        assert c1.strength == c2.strength
        assert c1.intelligence == c2.intelligence
        assert c1.skills == c2.skills

    def test_different_seed_produces_different_character(self):
        creator = CharacterCreator()
        rng1 = random.Random(1)
        rng2 = random.Random(9999)
        c1 = creator.create_random(rng=rng1)
        c2 = creator.create_random(rng=rng2)
        # At least one attribute should differ with very high probability
        differs = (
            c1.name != c2.name
            or c1.race != c2.race
            or c1.job != c2.job
            or c1.strength != c2.strength
        )
        assert differs


class TestCreateFromTemplateReproducibility:
    def test_same_seed_produces_same_template_character(self):
        creator = CharacterCreator()
        rng1 = random.Random(77)
        rng2 = random.Random(77)
        c1 = creator.create_from_template("warrior", rng=rng1)
        c2 = creator.create_from_template("warrior", rng=rng2)
        assert c1.char_id == c2.char_id
        assert c1.name == c2.name
        assert c1.gender == c2.gender
        assert c1.age == c2.age
        assert c1.strength == c2.strength
        assert c1.intelligence == c2.intelligence

"""
tests/test_character_creator.py - Unit tests for CharacterCreator.
"""

import random
from types import SimpleNamespace

from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.i18n import get_locale, set_locale, tr, tr_term


def setup_function():
    setup_function.previous_locale = get_locale()


def teardown_function():
    set_locale(setup_function.previous_locale)


class TestCharacterCreator:
    def test_random_character_history_has_no_year_zero_prefix(self):
        creator = CharacterCreator()
        char = creator.create_random(name="Aldric")
        assert not any(entry.startswith("Year 0:") for entry in char.history)

    def test_template_character_history_has_no_year_zero_prefix(self):
        creator = CharacterCreator()
        char = creator.create_from_template("warrior", name="Aldric")
        assert not any(entry.startswith("Year 0:") for entry in char.history)

    def test_random_character_history_is_localized_in_japanese(self):
        set_locale("ja")
        creator = CharacterCreator()
        char = creator.create_random(name="Aldric", rng=random.Random(42))
        assert char.history[0] == tr(
            "history_born_into_world",
            race=tr_term(char.race),
            job=tr_term(char.job),
        )
        assert "Human" not in char.history[0]
        assert "Warrior" not in char.history[0]
        assert "Born into the world" not in char.history[0]

    def test_template_character_history_is_localized_in_english(self):
        set_locale("en")
        creator = CharacterCreator()
        char = creator.create_from_template("warrior", name="Aldric", rng=random.Random(42))
        assert char.history[0] == tr(
            "history_born_into_world",
            race=tr_term(char.race),
            job=tr_term(char.job),
        )


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


class TestInteractiveStatAllocation:
    def test_manual_distribution_allows_values_above_ten(self):
        creator = CharacterCreator()

        class ScriptedInput:
            def __init__(self, responses):
                self._responses = iter(responses)

            def read_line(self, prompt: str = "") -> str:
                return next(self._responses)

        class BufferOut:
            def __init__(self):
                self.lines = []

            def print_line(self, text: str = "") -> None:
                self.lines.append(text)

        ctx = SimpleNamespace(
            inp=ScriptedInput(["y", "20", "10", "10", "10", "10", "10"]),
            out=BufferOut(),
        )

        stats = creator._allocate_stats(ctx=ctx)

        assert stats["strength"] == 20
        assert sum(stats.values()) == 70

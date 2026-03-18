"""
tests/test_character_creator.py - Unit tests for CharacterCreator.
"""

import os
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

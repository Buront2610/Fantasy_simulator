"""
tests/test_character_creator.py - Unit tests for CharacterCreator.
"""

import random
from types import SimpleNamespace

import fantasy_simulator.character_creator as character_creator_module
from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.content.setting_bundle import JobDefinition, RaceDefinition, default_aethoria_bundle
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

    def test_custom_bundle_naming_rules_are_used_at_runtime(self):
        bundle = default_aethoria_bundle()
        bundle.world_definition.races = [
            RaceDefinition(
                name="Clockfolk",
                description="Precise and patient.",
                stat_bonuses={"strength": 0, "intelligence": 2},
            )
        ]
        bundle.world_definition.jobs = [
            JobDefinition(
                name="Scribe",
                description="Records the world.",
                primary_skills=["Lore Mastery"],
            )
        ]
        bundle.world_definition.naming_rules.first_names_male = ["Custom"]
        bundle.world_definition.naming_rules.first_names_female = ["Custom"]
        bundle.world_definition.naming_rules.first_names_non_binary = ["Custom"]
        bundle.world_definition.naming_rules.last_names = ["Name"]

        creator = CharacterCreator(setting_bundle=bundle)
        character = creator.create_random(rng=random.Random(1))

        assert character.name == "Custom Name"
        assert character.race == "Clockfolk"
        assert character.job == "Scribe"

    def test_empty_bundle_naming_rules_fall_back_to_default_names(self):
        bundle = default_aethoria_bundle()
        bundle.world_definition.naming_rules = bundle.world_definition.naming_rules.__class__()

        default_name = CharacterCreator().create_random(rng=random.Random(7)).name
        fallback_name = CharacterCreator(setting_bundle=bundle).create_random(rng=random.Random(7)).name

        assert fallback_name == default_name

    def test_random_character_defaults_to_empty_location_until_added_to_world(self):
        creator = CharacterCreator()

        character = creator.create_random(rng=random.Random(7))

        assert character.location_id == ""


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

    def test_templates_are_unavailable_for_non_aethoria_compatible_bundles(self):
        bundle = default_aethoria_bundle()
        bundle.world_definition.races = [
            RaceDefinition(
                name="Clockfolk",
                description="Precise and patient.",
                stat_bonuses={"intelligence": 2},
            )
        ]
        bundle.world_definition.jobs = [
            JobDefinition(
                name="Scribe",
                description="Records the world.",
                primary_skills=["Lore Mastery"],
            )
        ]
        creator = CharacterCreator(setting_bundle=bundle)

        assert creator.list_templates() == []
        try:
            creator.create_from_template("warrior", rng=random.Random(3))
        except ValueError as exc:
            assert "Aethoria-compatible bundles" in str(exc)
        else:
            raise AssertionError("Expected ValueError for unsupported template bundle")

    def test_templates_remain_available_when_bundle_uses_legacy_race_job_fallbacks(self):
        bundle = default_aethoria_bundle()
        bundle.world_definition.races = []
        bundle.world_definition.jobs = []

        creator = CharacterCreator(setting_bundle=bundle)

        assert "warrior" in creator.list_templates()

    def test_empty_bundle_race_job_lists_fall_back_to_default_bundle_entries(self):
        bundle = default_aethoria_bundle()
        bundle.world_definition.races = []
        bundle.world_definition.jobs = []

        creator = CharacterCreator(setting_bundle=bundle)

        assert creator.race_entries
        assert creator.job_entries
        assert "Human" in {name for name, _desc, _bonus in creator.race_entries}
        assert "Warrior" in {name for name, _desc, _skills in creator.job_entries}

    def test_templates_are_unavailable_for_non_aethoria_world_key_even_with_matching_names(self):
        bundle = default_aethoria_bundle()
        bundle.world_definition.world_key = "clockwork"
        creator = CharacterCreator(setting_bundle=bundle)

        assert creator.list_templates() == []

    def test_non_aethoria_empty_race_job_catalogs_do_not_fallback_to_aethoria_defaults(self):
        bundle = default_aethoria_bundle()
        bundle.world_definition.world_key = "clockwork"
        bundle.world_definition.races = []
        bundle.world_definition.jobs = []
        creator = CharacterCreator(setting_bundle=bundle)

        assert creator.race_entries == []
        assert creator.job_entries == []
        try:
            creator.create_random(rng=random.Random(1))
        except ValueError as exc:
            assert "at least one race" in str(exc)
        else:
            raise AssertionError("Expected ValueError when non-Aethoria bundle has empty race/job catalogs")

    def test_default_bundle_fallback_is_cached_per_creator_instance(self, monkeypatch):
        call_count = {"count": 0}
        original = character_creator_module.default_aethoria_bundle

        def _counted_default_bundle():
            call_count["count"] += 1
            return original()

        monkeypatch.setattr(character_creator_module, "default_aethoria_bundle", _counted_default_bundle)
        creator = CharacterCreator()

        _ = creator.naming_rules
        _ = creator.race_entries
        _ = creator.job_entries

        assert call_count["count"] == 1


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

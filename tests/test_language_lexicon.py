"""Contract tests for deterministic language lexicon generation."""

from fantasy_simulator.content.setting_bundle import LanguageDefinition
from fantasy_simulator.language.lexicon import LanguageLexiconGenerator
from fantasy_simulator.language.naming import tidy_word


def _language_index(*languages: LanguageDefinition):
    return {language.language_key: language for language in languages}


def _resolved_list(language_index):
    def resolve(language: LanguageDefinition, attribute: str, default: list[str]) -> list[str]:
        values = list(getattr(language, attribute))
        if values:
            return values
        if language.parent_key:
            return resolve(language_index[language.parent_key], attribute, default)
        return list(default)

    return resolve


def _generator(language_index):
    return LanguageLexiconGenerator(
        evolve_surface_form=lambda _language_key, text: tidy_word(text),
        resolved_list=_resolved_list(language_index),
    )


def test_lexicon_generation_is_deterministic_for_language_key():
    language = LanguageDefinition(
        language_key="root",
        display_name="Root",
        seed_syllables=["ka", "ka", "lo"],
        consonants=["k", "l"],
        vowels=["a", "o"],
        syllable_templates=["CV"],
        lexicon_size=8,
    )
    language_index = _language_index(language)
    generator = _generator(language_index)

    assert generator.build_lexicon(language) == [
        "ka",
        "lo",
        "ko",
        "kolo",
        "lalo",
        "kola",
        "loloko",
        "kalako",
    ]
    assert generator.build_lexicon(language) == generator.build_lexicon(language)


def test_child_lexicon_starts_with_parent_roots_then_child_seeds():
    proto = LanguageDefinition(
        language_key="proto",
        display_name="Proto",
        seed_syllables=["ata", "sela"],
        lexicon_size=4,
    )
    child = LanguageDefinition(
        language_key="child",
        display_name="Child",
        parent_key="proto",
        seed_syllables=["tana"],
        sound_shifts={"t": "d"},
        lexicon_size=6,
    )
    language_index = _language_index(proto, child)
    generator = LanguageLexiconGenerator(
        evolve_surface_form=lambda language_key, text: tidy_word(text.replace("t", "d"))
        if language_key == "child"
        else tidy_word(text),
        resolved_list=_resolved_list(language_index),
    )
    parent_lexicon = generator.build_lexicon(proto)

    assert generator.build_lexicon(child, parent_lexicon=parent_lexicon)[:5] == [
        "ada",
        "sela",
        "indo",
        "igrae",
        "dana",
    ]


def test_lexicon_uses_fallback_words_when_no_unique_forms_can_be_generated():
    language = LanguageDefinition(
        language_key="silent",
        display_name="Silent",
        syllable_templates=[""],
        lexicon_size=3,
    )
    language_index = _language_index(language)
    generator = _generator(language_index)

    assert generator.build_lexicon(language) == ["aran", "sela", "torin"]

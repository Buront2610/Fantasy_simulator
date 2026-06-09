"""Language family atlas read model tests."""

from fantasy_simulator.content.language_families import build_language_atlas_view, language_atlas_lines
from fantasy_simulator.content.setting_bundle import (
    LanguageDefinition,
    LanguageFamilyDefinition,
    WorldDefinition,
)


def test_language_atlas_groups_languages_by_authored_family() -> None:
    world_definition = WorldDefinition(
        world_key="families",
        display_name="Families",
        lore_text="Family atlas test.",
        languages=[
            LanguageDefinition("proto", "Proto", family_key="court"),
            LanguageDefinition("child", "Child", parent_key="proto", family_key="court"),
            LanguageDefinition("wanderer", "Wanderer"),
        ],
        language_families=[
            LanguageFamilyDefinition(
                family_key="court",
                display_name="Court Speech",
                proto_language_key="proto",
                origin_region_ids=["loc_court"],
                cultural_tags=["court"],
                semantic_domain_tags=["law"],
            )
        ],
    )

    view = build_language_atlas_view(world_definition)

    assert view.family_count == 1
    assert view.language_count == 3
    assert view.families[0].family_key == "court"
    assert view.families[0].language_keys == ["child", "proto"]
    assert view.language_keys_without_family == ["wanderer"]


def test_language_atlas_lines_are_stable() -> None:
    world_definition = WorldDefinition(
        world_key="families",
        display_name="Families",
        lore_text="Family atlas test.",
        languages=[
            LanguageDefinition("a", "A", family_key="fam"),
            LanguageDefinition("b", "B", family_key="fam"),
        ],
        language_families=[
            LanguageFamilyDefinition(
                family_key="fam",
                display_name="Family",
                proto_language_key="a",
                origin_region_ids=["loc_one", "loc_two"],
            )
        ],
    )

    assert language_atlas_lines(world_definition) == [
        "language families: 1",
        "languages: 2",
        "fam: a, b | proto=a | origins=loc_one, loc_two",
    ]

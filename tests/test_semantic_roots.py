"""Semantic-root authoring read model tests."""

from fantasy_simulator.content.semantic_roots import (
    build_semantic_root_preview,
    semantic_root_coverage_lines,
)
from fantasy_simulator.content.setting_bundle import (
    LanguageDefinition,
    LanguageRootRealization,
    SemanticRootDefinition,
    WorldDefinition,
)


def test_semantic_root_preview_composes_language_surfaces_in_order() -> None:
    world_definition = WorldDefinition(
        world_key="roots",
        display_name="Roots",
        lore_text="Root preview test.",
        languages=[LanguageDefinition(language_key="thornic", display_name="Thornic")],
        semantic_roots=[
            SemanticRootDefinition("dark", "dark", "dark"),
            SemanticRootDefinition("pass", "pass", "pass"),
        ],
        language_root_realizations=[
            LanguageRootRealization("thornic", "dark", "kar"),
            LanguageRootRealization("thornic", "pass", "um"),
        ],
    )

    preview = build_semantic_root_preview(world_definition, "thornic", ["dark", "pass"])

    assert preview.surface == "Karum"
    assert preview.component_surfaces == ["kar", "um"]
    assert preview.missing_root_keys == []


def test_semantic_root_preview_reports_missing_roots_without_guessing() -> None:
    world_definition = WorldDefinition(
        world_key="roots",
        display_name="Roots",
        lore_text="Root preview test.",
        languages=[LanguageDefinition(language_key="thornic", display_name="Thornic")],
        semantic_roots=[SemanticRootDefinition("dark", "dark", "dark")],
        language_root_realizations=[LanguageRootRealization("thornic", "dark", "kar")],
    )

    preview = build_semantic_root_preview(world_definition, "thornic", ["dark", "pass"])

    assert preview.surface == "Kar"
    assert preview.component_surfaces == ["kar"]
    assert preview.missing_root_keys == ["pass"]


def test_semantic_root_coverage_lines_are_stable() -> None:
    world_definition = WorldDefinition(
        world_key="roots",
        display_name="Roots",
        lore_text="Root preview test.",
        languages=[
            LanguageDefinition(language_key="a", display_name="A"),
            LanguageDefinition(language_key="b", display_name="B"),
        ],
        semantic_roots=[
            SemanticRootDefinition("dark", "dark", "dark"),
            SemanticRootDefinition("pass", "pass", "pass"),
        ],
        language_root_realizations=[
            LanguageRootRealization("b", "dark", "bar"),
            LanguageRootRealization("a", "dark", "kar"),
            LanguageRootRealization("a", "pass", "um"),
        ],
    )

    assert semantic_root_coverage_lines(world_definition) == [
        "semantic roots: 2",
        "a: 2/2 roots",
        "b: 1/2 roots",
    ]

"""Contract tests for language fallback resolution and debug status output."""

import pytest

from fantasy_simulator.content.setting_bundle import (
    LanguageCommunityDefinition,
    LanguageDefinition,
    NamingRulesDefinition,
    WorldDefinition,
)
from fantasy_simulator.language.engine import LanguageEngine
from fantasy_simulator.language.schema import SoundChangeRuleDefinition
from fantasy_simulator.language.state import LanguageEvolutionRecord, LanguageRuntimeState
from fantasy_simulator.world_language import language_status


def _world_definition(*, languages, communities=None):
    return WorldDefinition(
        world_key="contract_world",
        display_name="Contract World",
        lore_text="Contract coverage.",
        naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
        languages=list(languages),
        language_communities=list(communities or []),
    )


def test_resolve_language_prefers_exact_match_before_partial_match():
    world_definition = _world_definition(
        languages=[
            LanguageDefinition(language_key="common", display_name="Common"),
            LanguageDefinition(language_key="sindral", display_name="Sindral"),
            LanguageDefinition(language_key="elfic", display_name="Elfic"),
        ],
        communities=[
            LanguageCommunityDefinition(
                community_key="elfic",
                display_name="Elfic",
                language_key="elfic",
                races=["Elf"],
                priority=10,
            ),
            LanguageCommunityDefinition(
                community_key="sindral",
                display_name="Sindral",
                language_key="sindral",
                races=["Elf"],
                regions=["thornwood"],
                priority=1,
            ),
            LanguageCommunityDefinition(
                community_key="common",
                display_name="Common",
                language_key="common",
                is_lingua_franca=True,
                priority=0,
            ),
        ],
    )

    engine = LanguageEngine(world_definition)

    assert engine.resolve_language(race="Elf", region="thornwood").language_key == "sindral"


def test_resolve_language_uses_partial_best_match_with_incomplete_identity():
    world_definition = _world_definition(
        languages=[
            LanguageDefinition(language_key="common", display_name="Common"),
            LanguageDefinition(language_key="elfic", display_name="Elfic"),
            LanguageDefinition(language_key="woodspeech", display_name="Woodspeech"),
        ],
        communities=[
            LanguageCommunityDefinition(
                community_key="elfic",
                display_name="Elfic",
                language_key="elfic",
                races=["Elf"],
                priority=2,
            ),
            LanguageCommunityDefinition(
                community_key="woodspeech",
                display_name="Woodspeech",
                language_key="woodspeech",
                regions=["thornwood"],
                priority=1,
            ),
            LanguageCommunityDefinition(
                community_key="common",
                display_name="Common",
                language_key="common",
                is_lingua_franca=True,
                priority=0,
            ),
        ],
    )

    engine = LanguageEngine(world_definition)

    assert engine.resolve_language(race="Elf").language_key == "elfic"
    assert engine.resolve_language(region="thornwood").language_key == "woodspeech"
    assert engine.resolve_language(race="Elf", region="unknown").language_key == "elfic"


def test_resolve_language_falls_back_to_lingua_franca_before_none():
    world_definition = _world_definition(
        languages=[
            LanguageDefinition(language_key="common", display_name="Common"),
            LanguageDefinition(language_key="elfic", display_name="Elfic"),
        ],
        communities=[
            LanguageCommunityDefinition(
                community_key="common",
                display_name="Common",
                language_key="common",
                is_lingua_franca=True,
                priority=5,
            ),
            LanguageCommunityDefinition(
                community_key="elfic",
                display_name="Elfic",
                language_key="elfic",
                races=["Elf"],
            ),
        ],
    )

    engine = LanguageEngine(world_definition)

    assert engine.resolve_language().language_key == "common"
    assert engine.resolve_language(race="Human").language_key == "common"


def test_resolve_language_falls_back_to_single_language_when_no_community_matches():
    world_definition = _world_definition(
        languages=[LanguageDefinition(language_key="only", display_name="Only Tongue")],
    )

    engine = LanguageEngine(world_definition)

    assert engine.resolve_language(race="Human").language_key == "only"


def test_resolve_language_returns_none_when_no_fallback_applies():
    world_definition = _world_definition(
        languages=[
            LanguageDefinition(language_key="common", display_name="Common"),
            LanguageDefinition(language_key="elfic", display_name="Elfic"),
        ],
        communities=[
            LanguageCommunityDefinition(
                community_key="elfic",
                display_name="Elfic",
                language_key="elfic",
                races=["Elf"],
            ),
        ],
    )

    engine = LanguageEngine(world_definition)

    assert engine.resolve_language(race="Human") is None


def test_language_status_exposes_debug_fallback_and_runtime_details():
    world_definition = _world_definition(
        languages=[
            LanguageDefinition(
                language_key="proto",
                display_name="Proto",
                seed_syllables=["ata", "sela"],
                sound_shifts={"a": "e"},
            ),
            LanguageDefinition(
                language_key="child",
                display_name="Child",
                parent_key="proto",
                seed_syllables=["tana"],
                sound_change_rules=[
                    SoundChangeRuleDefinition(
                        rule_key="child.lenition",
                        source="t",
                        target="d",
                        after="vowel",
                        description="Intervocalic lenition.",
                    )
                ],
            ),
        ],
    )
    runtime_state = LanguageRuntimeState(
        language_key="child",
        applied_rules=[
            SoundChangeRuleDefinition(
                rule_key="runtime.s_to_sh",
                source="s",
                target="sh",
                position="initial",
                description="Initial palatalization.",
            )
        ],
        derived_name_stems=["dar"],
        derived_toponym_suffixes=["eth"],
    )
    engine = LanguageEngine(world_definition, runtime_states={"child": runtime_state})
    evolution_history = [
        LanguageEvolutionRecord(
            year=1200,
            language_key="child",
            source_token="s",
            target_token="sh",
            rule_key="runtime.s_to_sh",
            rule_position="initial",
            rule_description="Initial palatalization.",
        )
    ]

    status = language_status(world_definition, engine, evolution_history)
    child_status = next(item for item in status if item["language_key"] == "child")

    assert child_status["lineage"] == ["Proto", "Child"]
    assert child_status["applied_rules"] == [
        {
            "rule_key": "runtime.s_to_sh",
            "source": "s",
            "target": "sh",
            "before": "",
            "after": "",
            "position": "initial",
            "description": "Initial palatalization.",
            "weight": 1,
        }
    ]
    assert [rule["rule_key"] for rule in child_status["effective_rules"]] == [
        "legacy:proto:a>e",
        "child.lenition",
        "runtime.s_to_sh",
    ]
    assert child_status["runtime_state"] == {
        "applied_rule_count": 1,
        "derived_name_stems": ["dar"],
        "derived_toponym_suffixes": ["eth"],
    }
    assert child_status["recent_evolution_records"] == [evolution_history[0].to_dict()]
    assert set(child_status["sample_forms"]) == {"given_names", "surnames", "lexicon", "toponym"}
    assert child_status["sample_forms"]["lexicon"]


def test_child_surface_forms_apply_lineage_sound_changes():
    world_definition = _world_definition(
        languages=[
            LanguageDefinition(
                language_key="proto",
                display_name="Proto",
                sound_shifts={"a": "e"},
            ),
            LanguageDefinition(
                language_key="child",
                display_name="Child",
                parent_key="proto",
            ),
        ],
    )
    engine = LanguageEngine(world_definition)

    assert engine.evolve_surface_form("child", "ata") == "ete"


def test_child_effective_sound_shift_map_includes_lineage_shifts():
    world_definition = _world_definition(
        languages=[
            LanguageDefinition(
                language_key="proto",
                display_name="Proto",
                sound_shifts={"a": "e"},
            ),
            LanguageDefinition(
                language_key="child",
                display_name="Child",
                parent_key="proto",
                sound_shifts={"t": "d"},
            ),
        ],
    )
    engine = LanguageEngine(world_definition)

    assert engine.effective_sound_shift_map("child") == {"a": "e", "t": "d"}


def test_language_runtime_state_rejects_string_stem_payloads():
    with pytest.raises(ValueError, match="derived_name_stems"):
        LanguageRuntimeState.from_dict(
            {
                "language_key": "child",
                "derived_name_stems": "dar",
                "derived_toponym_suffixes": [],
            }
        )

    with pytest.raises(ValueError, match="derived_toponym_suffixes"):
        LanguageRuntimeState.from_dict(
            {
                "language_key": "child",
                "derived_name_stems": [],
                "derived_toponym_suffixes": "eth",
            }
        )

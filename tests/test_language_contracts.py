from __future__ import annotations

from fantasy_simulator.content.setting_bundle import (
    LanguageCommunityDefinition,
    LanguageDefinition,
    NamingRulesDefinition,
    SettingBundle,
    SiteSeedDefinition,
    WorldDefinition,
)
from fantasy_simulator.language.engine import LanguageEngine
from fantasy_simulator.world import World


def _contract_bundle(*, include_lingua_franca: bool = True) -> SettingBundle:
    communities = [
        LanguageCommunityDefinition(
            community_key="human_common",
            display_name="Human Common",
            language_key="common",
            races=["Human"],
            priority=10,
        ),
        LanguageCommunityDefinition(
            community_key="frontier_region",
            display_name="Frontier Region",
            language_key="frontier",
            regions=["loc_frontier"],
            priority=20,
        ),
        LanguageCommunityDefinition(
            community_key="high_court",
            display_name="High Court",
            language_key="court",
            races=["Human"],
            regions=["loc_capital"],
            priority=30,
        ),
    ]
    if include_lingua_franca:
        communities.append(
            LanguageCommunityDefinition(
                community_key="trade_speech",
                display_name="Trade Speech",
                language_key="trade",
                priority=5,
                is_lingua_franca=True,
            )
        )
    return SettingBundle(
        schema_version=1,
        world_definition=WorldDefinition(
            world_key="contracts",
            display_name="Contracts",
            lore_text="Contract world",
            site_seeds=[
                SiteSeedDefinition(
                    location_id="loc_capital",
                    name="Capital",
                    description="Seat of power.",
                    region_type="city",
                    x=0,
                    y=0,
                ),
                SiteSeedDefinition(
                    location_id="loc_frontier",
                    name="Frontier",
                    description="Border town.",
                    region_type="village",
                    x=1,
                    y=0,
                ),
            ],
            languages=[
                LanguageDefinition(language_key="common", display_name="Common"),
                LanguageDefinition(language_key="frontier", display_name="Frontier"),
                LanguageDefinition(language_key="court", display_name="Court"),
                LanguageDefinition(language_key="trade", display_name="Trade"),
            ],
            language_communities=communities,
            naming_rules=NamingRulesDefinition(
                first_names_male=["Fallback"],
                first_names_female=["Fallbacka"],
                last_names=["Fallbackson"],
            ),
        ),
    )


def _language_world() -> World:
    world = World(name="Contracts", year=1000)
    world.setting_bundle = SettingBundle(
        schema_version=1,
        world_definition=WorldDefinition(
            world_key="contracts",
            display_name="Contracts",
            lore_text="Contract world",
            site_seeds=[
                SiteSeedDefinition(
                    location_id="loc_custom",
                    name="Custom",
                    description="Custom site.",
                    region_type="city",
                    x=0,
                    y=0,
                    language_key="child_lang",
                ),
            ],
            languages=[
                LanguageDefinition(
                    language_key="proto_lang",
                    display_name="Proto Lang",
                    seed_syllables=["ata", "tan"],
                    sound_shifts={"a": "e"},
                    evolution_interval_years=1,
                ),
                LanguageDefinition(
                    language_key="child_lang",
                    display_name="Child Lang",
                    parent_key="proto_lang",
                    seed_syllables=["ata", "tan"],
                    sound_change_rules=[],
                    evolution_interval_years=1,
                ),
            ],
            naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
        ),
    )
    return world


def test_resolve_language_prefers_exact_match_before_partial_matches() -> None:
    engine = LanguageEngine(_contract_bundle().world_definition)

    assert engine.resolve_language(race="Human", region="loc_capital").display_name == "Court"


def test_resolve_language_uses_partial_best_match_for_race_only() -> None:
    engine = LanguageEngine(_contract_bundle().world_definition)

    assert engine.resolve_language(race="Human").display_name == "Common"


def test_resolve_language_uses_partial_best_match_for_region_only() -> None:
    engine = LanguageEngine(_contract_bundle().world_definition)

    assert engine.resolve_language(region="loc_frontier").display_name == "Frontier"


def test_resolve_language_prefers_best_partial_match_before_lingua_franca() -> None:
    engine = LanguageEngine(_contract_bundle().world_definition)

    assert engine.resolve_language(race="Human", region="loc_frontier").display_name == "Frontier"


def test_resolve_language_uses_lingua_franca_when_no_selectors_match() -> None:
    engine = LanguageEngine(_contract_bundle().world_definition)

    assert engine.resolve_language(race="Dwarf").display_name == "Trade"


def test_resolve_language_uses_lingua_franca_for_selectorless_lookup() -> None:
    engine = LanguageEngine(_contract_bundle().world_definition)

    assert engine.resolve_language().display_name == "Trade"


def test_resolve_language_uses_single_language_when_it_is_the_only_option() -> None:
    world_definition = WorldDefinition(
        world_key="single",
        display_name="Single",
        lore_text="Single",
        languages=[LanguageDefinition(language_key="only", display_name="Only")],
        naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
    )
    engine = LanguageEngine(world_definition)

    assert engine.resolve_language(race="Human").display_name == "Only"


def test_advance_time_two_years_matches_two_single_year_steps_for_languages() -> None:
    direct = _language_world()
    stepped = _language_world()

    direct.advance_time(2)
    stepped.advance_time(1)
    stepped.advance_time(1)

    assert direct.language_status() == stepped.language_status()
    assert direct.language_evolution_history == stepped.language_evolution_history
    assert direct.location_endonym("loc_custom") == stepped.location_endonym("loc_custom")


def test_save_load_round_trip_preserves_language_status_snapshot() -> None:
    world = _language_world()
    world.advance_time(2)

    restored = World.from_dict(world.to_dict())

    assert restored.language_status() == world.language_status()
    assert restored.location_endonym("loc_custom") == world.location_endonym("loc_custom")


def test_history_replay_restores_same_language_state_without_runtime_snapshot() -> None:
    world = _language_world()
    world.advance_time(2)
    payload = world.to_dict()
    payload["language_runtime_states"] = {}

    restored = World.from_dict(payload)

    assert restored.language_status() == world.language_status()
    assert restored.location_endonym("loc_custom") == world.location_endonym("loc_custom")


def test_non_language_bundle_change_preserves_language_runtime_state() -> None:
    world = _language_world()
    world.advance_time(1)
    before_status = world.language_status()
    before_origin_year = world.language_origin_year
    before_history = list(world.language_evolution_history)

    updated_bundle = SettingBundle.from_dict(world.setting_bundle.to_dict())
    updated_bundle.world_definition.lore_text = "Updated lore only."
    updated_bundle.world_definition.site_seeds[0].description = "Updated site text."
    world.setting_bundle = updated_bundle

    assert world.language_origin_year == before_origin_year
    assert world.language_evolution_history == before_history
    assert world.language_status() == before_status

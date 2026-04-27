"""Tests for the minimal PR-I SettingBundle foundation."""

from __future__ import annotations

import json

from fantasy_simulator.content.setting_bundle import (
    CalendarDefinition,
    DEFAULT_AETHORIA_BUNDLE_PATH,
    GlossaryEntryDefinition,
    LanguageCommunityDefinition,
    LanguageDefinition,
    SettingBundle,
    SettingEntryInspection,
    SiteSeedDefinition,
    WorldDefinition,
    build_setting_bundle_authoring_summary,
    bundle_from_dict_validated,
    default_aethoria_bundle,
    load_setting_bundle,
)
from fantasy_simulator.language.schema import SoundChangeRuleDefinition
from fantasy_simulator.world import World


def test_world_definition_round_trip():
    world_def = WorldDefinition(
        world_key="custom",
        display_name="Custom Realm",
        lore_text="Custom lore",
        era="Second Dawn",
        cultures=["Skyfolk"],
        factions=["Wardens"],
        languages=[
            LanguageDefinition(
                language_key="proto",
                display_name="Proto",
                seed_syllables=["ar", "bel"],
            ),
            LanguageDefinition(
                language_key="child",
                display_name="Child",
                parent_key="proto",
                sound_shifts={"b": "v"},
            ),
        ],
        language_communities=[
            LanguageCommunityDefinition(
                community_key="skyfolk",
                display_name="Skyfolk Speech",
                language_key="child",
                races=["Skyfolk"],
                priority=5,
            )
        ],
    )

    restored = WorldDefinition.from_dict(world_def.to_dict())

    assert restored == world_def


def test_setting_bundle_round_trip():
    bundle = SettingBundle(
        schema_version=2,
        world_definition=WorldDefinition(
            world_key="custom",
            display_name="Custom Realm",
            lore_text="Custom lore",
        ),
    )

    restored = SettingBundle.from_dict(bundle.to_dict())

    assert restored == bundle


def test_world_definition_exposes_typed_culture_and_faction_inspection_entries():
    world_def = WorldDefinition(
        world_key="custom",
        display_name="Custom Realm",
        lore_text="Custom lore",
        cultures=["Skyfolk", "River Clans"],
        factions=["Wardens", "Dawn-Court"],
    )

    assert world_def.culture_entries() == [
        SettingEntryInspection("culture", "skyfolk", "Skyfolk"),
        SettingEntryInspection("culture", "river_clans", "River Clans"),
    ]
    assert world_def.faction_entries() == [
        SettingEntryInspection("faction", "wardens", "Wardens"),
        SettingEntryInspection("faction", "dawn_court", "Dawn-Court"),
    ]


def test_world_definition_round_trips_optional_glossary_entries():
    world_def = WorldDefinition(
        world_key="custom",
        display_name="Custom Realm",
        lore_text="Custom lore",
        glossary=[
            GlossaryEntryDefinition(
                term="Star-Road",
                definition="A navigable ley path used by skyfarers.",
                category="cosmology",
            )
        ],
    )

    restored = WorldDefinition.from_dict(world_def.to_dict())

    assert restored == world_def
    assert restored.glossary_entries() == [
        SettingEntryInspection("glossary", "star_road", "Star-Road"),
    ]


def test_setting_bundle_authoring_summary_includes_culture_and_faction_keys():
    bundle = SettingBundle(
        schema_version=1,
        world_definition=WorldDefinition(
            world_key="custom",
            display_name="Custom Realm",
            lore_text="Custom lore",
            cultures=["Skyfolk", "River Clans"],
            factions=["Wardens", "Dawn-Court"],
        ),
    )

    summary = build_setting_bundle_authoring_summary(bundle)

    assert summary.culture_count == 2
    assert summary.faction_count == 2
    assert summary.culture_keys == ["river_clans", "skyfolk"]
    assert summary.faction_keys == ["dawn_court", "wardens"]


def test_setting_bundle_authoring_summary_includes_glossary_keys():
    bundle = SettingBundle(
        schema_version=1,
        world_definition=WorldDefinition(
            world_key="custom",
            display_name="Custom Realm",
            lore_text="Custom lore",
            glossary=[
                GlossaryEntryDefinition(term="Star-Road"),
                GlossaryEntryDefinition(term="Ember Crown"),
            ],
        ),
    )

    summary = build_setting_bundle_authoring_summary(bundle)

    assert summary.glossary_count == 2
    assert summary.glossary_keys == ["ember_crown", "star_road"]


def test_setting_bundle_authoring_summary_includes_sites_with_native_names():
    bundle = SettingBundle(
        schema_version=1,
        world_definition=WorldDefinition(
            world_key="custom",
            display_name="Custom Realm",
            lore_text="Custom lore",
            languages=[
                LanguageDefinition(
                    language_key="river",
                    display_name="River Speech",
                ),
            ],
            site_seeds=[
                SiteSeedDefinition(
                    location_id="loc_delta",
                    name="Delta",
                    description="",
                    region_type="river",
                    x=1,
                    y=0,
                    language_key="river",
                    native_name="Darun",
                ),
                SiteSeedDefinition(
                    location_id="loc_bluff",
                    name="Bluff",
                    description="",
                    region_type="hill",
                    x=0,
                    y=0,
                    language_key="river",
                    native_name="Brenn",
                ),
                SiteSeedDefinition(
                    location_id="loc_plain",
                    name="Plain",
                    description="",
                    region_type="plain",
                    x=2,
                    y=0,
                    native_name="   ",
                ),
            ],
        ),
    )

    summary = build_setting_bundle_authoring_summary(bundle)

    assert summary.sites_with_native_names == ["loc_bluff", "loc_delta"]


def test_setting_bundle_authoring_summary_reports_site_language_coverage_gaps():
    bundle = SettingBundle(
        schema_version=1,
        world_definition=WorldDefinition(
            world_key="custom",
            display_name="Custom Realm",
            lore_text="Custom lore",
            languages=[
                LanguageDefinition(
                    language_key="river",
                    display_name="River Speech",
                ),
                LanguageDefinition(
                    language_key="hill",
                    display_name="Hill Speech",
                ),
            ],
            site_seeds=[
                SiteSeedDefinition(
                    location_id="loc_delta",
                    name="Delta",
                    description="",
                    region_type="river",
                    x=1,
                    y=0,
                    language_key="river",
                ),
                SiteSeedDefinition(
                    location_id="loc_bluff",
                    name="Bluff",
                    description="",
                    region_type="hill",
                    x=0,
                    y=0,
                    language_key="hill",
                ),
                SiteSeedDefinition(
                    location_id="loc_plain",
                    name="Plain",
                    description="",
                    region_type="plain",
                    x=2,
                    y=0,
                ),
            ],
            language_communities=[
                LanguageCommunityDefinition(
                    community_key="river_folk",
                    display_name="River Folk",
                    language_key="river",
                    regions=["loc_delta"],
                ),
                LanguageCommunityDefinition(
                    community_key="hill_diaspora",
                    display_name="Hill Diaspora",
                    language_key="hill",
                    races=["Human"],
                ),
            ],
        ),
    )

    summary = build_setting_bundle_authoring_summary(bundle)

    assert summary.language_community_count == 2
    assert summary.site_ids_without_language_key == ["loc_plain"]
    assert summary.site_ids_without_language_community == ["loc_bluff", "loc_plain"]
    assert summary.site_ids_without_matching_language_community == ["loc_bluff"]


def test_default_aethoria_bundle_has_minimal_phase_i_slots():
    bundle = default_aethoria_bundle()

    assert bundle.schema_version == 1
    assert bundle.world_definition.world_key == "aethoria"
    assert bundle.world_definition.era == "Age of Embers"
    assert bundle.world_definition.culture_entries()
    assert bundle.world_definition.faction_entries()
    assert bundle.world_definition.races
    assert bundle.world_definition.jobs
    assert bundle.world_definition.site_seeds
    assert bundle.world_definition.route_seeds
    assert bundle.world_definition.naming_rules.last_names
    assert bundle.world_definition.languages
    assert bundle.world_definition.language_communities
    assert bundle.world_definition.glossary
    capital_seed = next(
        seed for seed in bundle.world_definition.site_seeds
        if seed.location_id == "loc_aethoria_capital"
    )
    assert "capital" in capital_seed.tags
    assert "default_resident" in capital_seed.tags


def test_aethoria_bundle_has_expected_authored_native_names():
    summary = build_setting_bundle_authoring_summary(default_aethoria_bundle())

    assert summary.sites_with_native_names == [
        "loc_aethoria_capital",
        "loc_coral_cove",
        "loc_dawnport",
        "loc_frostpeak_summit",
        "loc_sandstone_outpost",
        "loc_silverbrook",
        "loc_skyveil_monastery",
        "loc_sunken_ruins",
        "loc_thornwood",
    ]


def test_bundle_validation_rejects_route_seed_with_unknown_site() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "bad_route",
            "display_name": "Bad Route",
            "lore_text": "Malformed",
            "site_seeds": [
                {
                    "location_id": "loc_one",
                    "name": "One",
                    "description": "",
                    "region_type": "city",
                    "x": 0,
                    "y": 0,
                }
            ],
            "route_seeds": [
                {
                    "route_id": "route_missing",
                    "from_site_id": "loc_one",
                    "to_site_id": "loc_two",
                    "route_type": "road",
                }
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "unknown site seed" in str(exc)
    else:
        raise AssertionError("Expected malformed route seed payload to fail fast")


def test_bundle_validation_preserves_explicitly_empty_route_seeds() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "isolated",
            "display_name": "Isolated",
            "lore_text": "Disconnected",
            "site_seeds": [
                {
                    "location_id": "loc_one",
                    "name": "One",
                    "description": "",
                    "region_type": "city",
                    "x": 0,
                    "y": 0,
                },
                {
                    "location_id": "loc_two",
                    "name": "Two",
                    "description": "",
                    "region_type": "village",
                    "x": 1,
                    "y": 0,
                },
            ],
            "route_seeds": [],
        },
    }

    bundle = bundle_from_dict_validated(payload, source="test bundle")

    assert bundle.world_definition.route_seeds == []


def test_aethoria_source_bundle_authors_glossary_and_routes() -> None:
    data = json.loads(DEFAULT_AETHORIA_BUNDLE_PATH.read_text(encoding="utf-8"))
    world_data = data["world_definition"]

    assert len(world_data.get("glossary", [])) >= 6
    assert len(world_data.get("route_seeds", [])) == 40
    assert world_data["route_seeds"][0] == {
        "route_id": "route_001",
        "from_site_id": "loc_frostpeak_summit",
        "to_site_id": "loc_the_grey_pass",
        "route_type": "mountain_pass",
        "distance": 1,
        "blocked": False,
    }


def test_aethoria_source_route_seeds_match_legacy_backfill() -> None:
    data = json.loads(DEFAULT_AETHORIA_BUNDLE_PATH.read_text(encoding="utf-8"))
    authored_routes = data["world_definition"]["route_seeds"]
    legacy_data = json.loads(json.dumps(data))
    legacy_data["world_definition"].pop("route_seeds")

    legacy_bundle = bundle_from_dict_validated(legacy_data, source="legacy aethoria bundle")

    assert authored_routes == [
        route.to_dict() for route in legacy_bundle.world_definition.route_seeds
    ]


def test_bundle_validation_rejects_non_boolean_route_seed_blocked() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "bad_blocked",
            "display_name": "Bad Blocked",
            "lore_text": "Malformed",
            "site_seeds": [
                {
                    "location_id": "loc_one",
                    "name": "One",
                    "description": "",
                    "region_type": "city",
                    "x": 0,
                    "y": 0,
                },
                {
                    "location_id": "loc_two",
                    "name": "Two",
                    "description": "",
                    "region_type": "village",
                    "x": 1,
                    "y": 0,
                },
            ],
            "route_seeds": [
                {
                    "route_id": "route_bad",
                    "from_site_id": "loc_one",
                    "to_site_id": "loc_two",
                    "blocked": "false",
                }
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "blocked" in str(exc)
    else:
        raise AssertionError("Expected malformed blocked payload to fail fast")


def test_load_setting_bundle_from_json(tmp_path):
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": 3,
                "world_definition": {
                    "world_key": "archive",
                    "display_name": "Archive",
                    "lore_text": "Stored lore",
                    "era": "Long Quiet",
                    "cultures": ["Archivists"],
                    "factions": ["Keepers"],
                    "races": [
                        {
                            "name": "Archivist",
                            "description": "Careful keepers of memory.",
                            "stat_bonuses": {"intelligence": 3},
                        }
                    ],
                    "jobs": [
                        {
                            "name": "Curator",
                            "description": "Maintains lost knowledge.",
                            "primary_skills": ["Lore Mastery"],
                        }
                    ],
                    "site_seeds": [
                        {
                            "location_id": "loc_archive",
                            "name": "Archive",
                            "description": "A vault of stories.",
                            "region_type": "city",
                            "x": 1,
                            "y": 2,
                        }
                    ],
                    "naming_rules": {
                        "first_names_male": ["Aren"],
                        "first_names_female": ["Lysa"],
                        "first_names_non_binary": ["Quill"],
                        "last_names": ["Shelfkeeper"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    bundle = load_setting_bundle(bundle_path)

    assert bundle.schema_version == 3
    assert bundle.world_definition.display_name == "Archive"
    assert bundle.world_definition.cultures == ["Archivists"]
    assert bundle.world_definition.site_seeds[0].location_id == "loc_archive"
    assert bundle.world_definition.naming_rules.last_names == ["Shelfkeeper"]


def test_bundle_validation_rejects_unknown_parent_language():
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "lang",
            "display_name": "Lang",
            "lore_text": "Lang lore",
            "languages": [
                {
                    "language_key": "child",
                    "display_name": "Child",
                    "parent_key": "missing",
                }
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "unknown parent language" in str(exc)
    else:
        raise AssertionError("Expected invalid parent language to fail fast")


def test_bundle_validation_rejects_language_cycles():
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "lang",
            "display_name": "Lang",
            "lore_text": "Lang lore",
            "languages": [
                {
                    "language_key": "a",
                    "display_name": "A",
                    "parent_key": "b",
                },
                {
                    "language_key": "b",
                    "display_name": "B",
                    "parent_key": "a",
                },
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "cyclic language inheritance" in str(exc)
    else:
        raise AssertionError("Expected cyclic language inheritance to fail fast")


def test_bundle_validation_rejects_unknown_language_community_target():
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "lang",
            "display_name": "Lang",
            "lore_text": "Lang lore",
            "languages": [
                {
                    "language_key": "root",
                    "display_name": "Root",
                }
            ],
            "language_communities": [
                {
                    "community_key": "folk",
                    "display_name": "Folk",
                    "language_key": "missing",
                    "races": ["Human"],
                }
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "unknown language community target" in str(exc)
    else:
        raise AssertionError("Expected invalid community target to fail fast")


def test_bundle_validation_rejects_unknown_language_community_race():
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "lang",
            "display_name": "Lang",
            "lore_text": "Lang lore",
            "races": [
                {"name": "Human", "description": "A", "stat_bonuses": {}},
            ],
            "languages": [
                {
                    "language_key": "root",
                    "display_name": "Root",
                }
            ],
            "language_communities": [
                {
                    "community_key": "folk",
                    "display_name": "Folk",
                    "language_key": "root",
                    "races": ["Elff"],
                }
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "unknown community races" in str(exc)
    else:
        raise AssertionError("Expected invalid community race to fail fast")


def test_aethoria_bundle_validation_allows_legacy_community_races_during_catalog_override():
    bundle = default_aethoria_bundle()
    bundle.world_definition.races = []

    restored = bundle_from_dict_validated(bundle.to_dict(), source="test bundle")

    assert restored.world_definition.language_communities


def test_bundle_validation_rejects_unknown_language_community_region():
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "lang",
            "display_name": "Lang",
            "lore_text": "Lang lore",
            "site_seeds": [
                {
                    "location_id": "loc_real",
                    "name": "Real",
                    "description": "",
                    "region_type": "city",
                    "x": 0,
                    "y": 0,
                }
            ],
            "languages": [
                {
                    "language_key": "root",
                    "display_name": "Root",
                }
            ],
            "language_communities": [
                {
                    "community_key": "folk",
                    "display_name": "Folk",
                    "language_key": "root",
                    "regions": ["loc_typo"],
                }
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "unknown community regions" in str(exc)
    else:
        raise AssertionError("Expected invalid community region to fail fast")


def test_bundle_validation_rejects_overlapping_consonants_and_vowels():
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "lang",
            "display_name": "Lang",
            "lore_text": "Lang lore",
            "languages": [
                {
                    "language_key": "root",
                    "display_name": "Root",
                    "consonants": ["b", "a"],
                    "vowels": ["a", "e"],
                }
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "overlapping consonants/vowels" in str(exc)
    else:
        raise AssertionError("Expected invalid phonology overlap to fail fast")


def test_world_definition_round_trip_preserves_evolution_interval():
    world_def = WorldDefinition(
        world_key="custom",
        display_name="Custom Realm",
        lore_text="Custom lore",
        languages=[
            LanguageDefinition(
                language_key="root",
                display_name="Root",
                evolution_interval_years=75,
            )
        ],
    )

    restored = WorldDefinition.from_dict(world_def.to_dict())

    assert restored.languages[0].evolution_interval_years == 75


def test_world_definition_round_trip_preserves_structured_sound_change_rules():
    world_def = WorldDefinition(
        world_key="custom",
        display_name="Custom Realm",
        lore_text="Custom lore",
        languages=[
            LanguageDefinition(
                language_key="root",
                display_name="Root",
                inspiration_tags=["germanic_like"],
                sound_change_rules=[
                    SoundChangeRuleDefinition(
                        rule_key="root.lenition",
                        source="t",
                        target="d",
                        before="vowel",
                        after="vowel",
                        position="medial",
                    )
                ],
                evolution_rule_pool=[
                    SoundChangeRuleDefinition(
                        rule_key="root.umlaut",
                        source="a",
                        target="e",
                        after="front_vowel",
                    )
                ],
            )
        ],
    )

    restored = WorldDefinition.from_dict(world_def.to_dict())

    assert restored.languages[0].inspiration_tags == ["germanic_like"]
    assert restored.languages[0].sound_change_rules[0].before == "vowel"
    assert restored.languages[0].evolution_rule_pool[0].rule_key == "root.umlaut"


def test_bundle_validation_rejects_invalid_structured_sound_change_position():
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "lang",
            "display_name": "Lang",
            "lore_text": "Lang lore",
            "languages": [
                {
                    "language_key": "root",
                    "display_name": "Root",
                    "sound_change_rules": [
                        {
                            "rule_key": "bad.rule",
                            "source": "t",
                            "target": "d",
                            "position": "inside",
                        }
                    ],
                }
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "invalid sound change position" in str(exc)
    else:
        raise AssertionError("Expected invalid structured sound change position to fail fast")


def test_load_setting_bundle_reports_missing_required_fields(tmp_path):
    bundle_path = tmp_path / "invalid-bundle.json"
    bundle_path.write_text(json.dumps({"schema_version": 1}), encoding="utf-8")

    try:
        load_setting_bundle(bundle_path)
    except ValueError as exc:
        assert "missing required field" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing world_definition")


def test_load_setting_bundle_reports_duplicate_site_seed_ids(tmp_path):
    bundle_path = tmp_path / "invalid-duplicate-sites.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "world_definition": {
                    "world_key": "dup",
                    "display_name": "Dup",
                    "lore_text": "Dup lore",
                    "site_seeds": [
                        {
                            "location_id": "loc_dup",
                            "name": "One",
                            "description": "",
                            "region_type": "city",
                            "x": 0,
                            "y": 0,
                        },
                        {
                            "location_id": "loc_dup",
                            "name": "Two",
                            "description": "",
                            "region_type": "city",
                            "x": 1,
                            "y": 0,
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_setting_bundle(bundle_path)
    except ValueError as exc:
        assert "duplicate site seed ids" in str(exc)
        assert "loc_dup" in str(exc)
    else:
        raise AssertionError("Expected ValueError for duplicate site seed ids")


def test_load_setting_bundle_reports_duplicate_site_seed_names(tmp_path):
    bundle_path = tmp_path / "invalid-duplicate-site-names.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "world_definition": {
                    "world_key": "dup",
                    "display_name": "Dup",
                    "lore_text": "Dup lore",
                    "site_seeds": [
                        {
                            "location_id": "loc_dup_one",
                            "name": "Duplicate",
                            "description": "",
                            "region_type": "city",
                            "x": 0,
                            "y": 0,
                        },
                        {
                            "location_id": "loc_dup_two",
                            "name": "Duplicate",
                            "description": "",
                            "region_type": "city",
                            "x": 1,
                            "y": 0,
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_setting_bundle(bundle_path)
    except ValueError as exc:
        assert "duplicate site seed names" in str(exc)
        assert "Duplicate" in str(exc)
    else:
        raise AssertionError("Expected ValueError for duplicate site seed names")


def test_bundle_from_dict_rejects_string_tags_instead_of_coercing_characters() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "bad_tags",
            "display_name": "Bad Tags",
            "lore_text": "Malformed",
            "site_seeds": [
                {
                    "location_id": "loc_bad",
                    "name": "Bad",
                    "description": "",
                    "region_type": "city",
                    "x": 0,
                    "y": 0,
                    "tags": "capital",
                }
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "tags" in str(exc)
    else:
        raise AssertionError("Expected malformed tags payload to fail fast")


def test_bundle_validation_rejects_negative_site_coordinates() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "bad_coords",
            "display_name": "Bad Coords",
            "lore_text": "Malformed",
            "site_seeds": [
                {
                    "location_id": "loc_bad",
                    "name": "Bad",
                    "description": "",
                    "region_type": "city",
                    "x": -1,
                    "y": 0,
                }
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "negative site seed coordinates" in str(exc)
    else:
        raise AssertionError("Expected negative coordinates to fail fast")


def test_bundle_from_dict_rejects_string_cultures_and_factions() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "bad_lists",
            "display_name": "Bad Lists",
            "lore_text": "Malformed",
            "cultures": "empire",
            "factions": "wardens",
            "site_seeds": [],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "cultures" in str(exc) or "factions" in str(exc)
    else:
        raise AssertionError("Expected malformed cultures/factions payload to fail fast")


def test_bundle_validation_rejects_duplicate_cultures_and_factions() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "duplicate_groups",
            "display_name": "Duplicate Groups",
            "lore_text": "Malformed",
            "cultures": ["Archivists", "Archivists"],
            "factions": ["Keepers"],
            "site_seeds": [],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "duplicate culture names" in str(exc)
    else:
        raise AssertionError("Expected duplicate cultures to fail fast")

    payload["world_definition"]["cultures"] = ["Archivists"]
    payload["world_definition"]["factions"] = ["Keepers", "Keepers"]

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "duplicate faction names" in str(exc)
    else:
        raise AssertionError("Expected duplicate factions to fail fast")


def test_bundle_validation_rejects_duplicate_culture_and_faction_inspection_keys() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "duplicate_group_keys",
            "display_name": "Duplicate Group Keys",
            "lore_text": "Malformed",
            "cultures": ["Dawn-Court", "Dawn Court"],
            "factions": ["Keepers"],
            "site_seeds": [],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "duplicate culture inspection keys" in str(exc)
    else:
        raise AssertionError("Expected duplicate culture keys to fail fast")

    payload["world_definition"]["cultures"] = ["Archivists"]
    payload["world_definition"]["factions"] = ["Dawn-Court", "Dawn Court"]

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "duplicate faction inspection keys" in str(exc)
    else:
        raise AssertionError("Expected duplicate faction keys to fail fast")


def test_bundle_validation_rejects_blank_cultures_and_factions() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "blank_groups",
            "display_name": "Blank Groups",
            "lore_text": "Malformed",
            "cultures": [""],
            "factions": ["Keepers"],
            "site_seeds": [],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "blank culture names" in str(exc)
    else:
        raise AssertionError("Expected blank cultures to fail fast")

    payload["world_definition"]["cultures"] = ["Archivists"]
    payload["world_definition"]["factions"] = ["  "]

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "blank faction names" in str(exc)
    else:
        raise AssertionError("Expected blank factions to fail fast")


def test_bundle_validation_rejects_blank_glossary_terms() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "blank_glossary",
            "display_name": "Blank Glossary",
            "lore_text": "Malformed",
            "glossary": [
                {
                    "term": "  ",
                    "definition": "Whitespace is not a term.",
                }
            ],
            "site_seeds": [],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "blank glossary terms" in str(exc)
    else:
        raise AssertionError("Expected blank glossary terms to fail fast")


def test_bundle_validation_rejects_duplicate_glossary_terms_and_keys() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "duplicate_glossary",
            "display_name": "Duplicate Glossary",
            "lore_text": "Malformed",
            "glossary": [
                {"term": "Star Road", "definition": "First."},
                {"term": "Star Road", "definition": "Second."},
            ],
            "site_seeds": [],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "duplicate glossary terms" in str(exc)
        assert "Star Road" in str(exc)
    else:
        raise AssertionError("Expected duplicate glossary terms to fail fast")

    payload["world_definition"]["glossary"] = [
        {"term": "Star-Road", "definition": "First."},
        {"term": "Star Road", "definition": "Second."},
    ]

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "duplicate glossary inspection keys" in str(exc)
        assert "star_road" in str(exc)
    else:
        raise AssertionError("Expected duplicate glossary keys to fail fast")


def test_load_setting_bundle_reports_duplicate_race_names(tmp_path):
    bundle_path = tmp_path / "invalid-duplicate-races.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "world_definition": {
                    "world_key": "dup",
                    "display_name": "Dup",
                    "lore_text": "Dup lore",
                    "races": [
                        {"name": "Mirrorkin", "description": "A", "stat_bonuses": {}},
                        {"name": "Mirrorkin", "description": "B", "stat_bonuses": {}},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_setting_bundle(bundle_path)
    except ValueError as exc:
        assert "duplicate race names" in str(exc)
        assert "Mirrorkin" in str(exc)
    else:
        raise AssertionError("Expected ValueError for duplicate race names")


def test_load_setting_bundle_reports_duplicate_job_names(tmp_path):
    bundle_path = tmp_path / "invalid-duplicate-jobs.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "world_definition": {
                    "world_key": "dup",
                    "display_name": "Dup",
                    "lore_text": "Dup lore",
                    "jobs": [
                        {"name": "Binder", "description": "A", "primary_skills": []},
                        {"name": "Binder", "description": "B", "primary_skills": []},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_setting_bundle(bundle_path)
    except ValueError as exc:
        assert "duplicate job names" in str(exc)
        assert "Binder" in str(exc)
    else:
        raise AssertionError("Expected ValueError for duplicate job names")


def test_load_setting_bundle_reports_ambiguous_legacy_location_aliases(tmp_path):
    bundle_path = tmp_path / "invalid-legacy-alias-collision.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "world_definition": {
                    "world_key": "dup",
                    "display_name": "Dup",
                    "lore_text": "Dup lore",
                    "site_seeds": [
                        {
                            "location_id": "loc_alpha_one",
                            "name": "Alpha-One",
                            "description": "",
                            "region_type": "city",
                            "x": 0,
                            "y": 0,
                        },
                        {
                            "location_id": "loc_alpha_two",
                            "name": "Alpha One",
                            "description": "",
                            "region_type": "city",
                            "x": 1,
                            "y": 0,
                        },
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_setting_bundle(bundle_path)
    except ValueError as exc:
        assert "ambiguous legacy location id aliases" in str(exc)
    else:
        raise AssertionError("Expected ValueError for ambiguous legacy aliases")


def test_load_setting_bundle_requires_gendered_name_pools(tmp_path):
    bundle_path = tmp_path / "invalid-naming.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "world_definition": {
                    "world_key": "naming",
                    "display_name": "Naming",
                    "lore_text": "Naming lore",
                    "naming_rules": {
                        "first_names_non_binary": ["Quill"],
                        "last_names": ["Ink"],
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_setting_bundle(bundle_path)
    except ValueError as exc:
        assert "first_names_male" in str(exc)
    else:
        raise AssertionError("Expected ValueError for incomplete naming rules")


def test_empty_calendar_definition_uses_consistent_30_day_fallback():
    calendar = CalendarDefinition(
        calendar_key="empty",
        display_name="Empty",
        months=[],
    )

    assert calendar.months_per_year == 1
    assert calendar.days_in_month(1) == 30
    assert calendar.days_per_year == 30


def test_bundle_authoring_summary_exposes_region_route_and_language_breakdowns():
    bundle = default_aethoria_bundle()

    summary = build_setting_bundle_authoring_summary(bundle)

    assert summary.world_key == "aethoria"
    assert summary.site_count == len(bundle.world_definition.site_seeds)
    assert summary.route_count == len(bundle.world_definition.route_seeds)
    assert "loc_aethoria_capital" in summary.capital_site_ids
    assert "loc_aethoria_capital" in summary.resident_site_ids
    assert summary.culture_count == len(bundle.world_definition.cultures)
    assert summary.faction_count == len(bundle.world_definition.factions)
    assert summary.glossary_count == len(bundle.world_definition.glossary)
    assert "aethic_heartlanders" in summary.culture_keys
    assert "aethorian_crown_council" in summary.faction_keys
    assert "arcane_cataclysm" in summary.glossary_keys
    assert "ley_lines" in summary.glossary_keys
    assert summary.site_counts_by_region_type["city"] >= 1
    assert summary.route_counts_by_type["road"] >= 1
    assert "aethic_common" in summary.language_keys
    assert "loc_thornwood" in summary.community_keys_by_region
    assert summary.language_community_count == len(bundle.world_definition.language_communities)
    assert summary.site_ids_without_language_key == []
    assert summary.site_ids_without_language_community == []
    assert summary.site_ids_without_matching_language_community == []


def test_aethoria_bundle_authoring_coverage_has_language_for_each_site():
    bundle = default_aethoria_bundle()
    world = bundle.world_definition
    language_keys = {language.language_key for language in world.languages}
    community_regions = {
        region_id
        for community in world.language_communities
        for region_id in community.regions
    }

    for seed in world.site_seeds:
        assert seed.language_key in language_keys
        assert seed.location_id in community_regions


def test_bundle_validation_rejects_native_name_without_language_key() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "bad_native_name",
            "display_name": "Bad Native Name",
            "lore_text": "Malformed",
            "site_seeds": [
                {
                    "location_id": "loc_bad",
                    "name": "Bad",
                    "native_name": "Baad",
                    "description": "",
                    "region_type": "city",
                    "x": 0,
                    "y": 0,
                }
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "native_name" in str(exc)
        assert "language_key" in str(exc)
    else:
        raise AssertionError("Expected native_name without language_key to fail fast")


def test_bundle_validation_treats_blank_native_name_as_absent() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "blank_native_name",
            "display_name": "Blank Native Name",
            "lore_text": "Sparse but valid",
            "site_seeds": [
                {
                    "location_id": "loc_blank",
                    "name": "Blank",
                    "native_name": "   ",
                    "description": "",
                    "region_type": "city",
                    "x": 0,
                    "y": 0,
                }
            ],
        },
    }

    bundle = bundle_from_dict_validated(payload, source="test bundle")

    assert bundle.world_definition.site_seeds[0].native_name == "   "


def test_bundle_validation_rejects_non_positive_route_distance() -> None:
    payload = {
        "schema_version": 1,
        "world_definition": {
            "world_key": "bad_distance",
            "display_name": "Bad Distance",
            "lore_text": "Malformed",
            "site_seeds": [
                {
                    "location_id": "loc_one",
                    "name": "One",
                    "description": "",
                    "region_type": "city",
                    "x": 0,
                    "y": 0,
                },
                {
                    "location_id": "loc_two",
                    "name": "Two",
                    "description": "",
                    "region_type": "village",
                    "x": 1,
                    "y": 0,
                },
            ],
            "route_seeds": [
                {
                    "route_id": "route_bad",
                    "from_site_id": "loc_one",
                    "to_site_id": "loc_two",
                    "distance": 0,
                }
            ],
        },
    }

    try:
        bundle_from_dict_validated(payload, source="test bundle")
    except ValueError as exc:
        assert "distance >= 1" in str(exc)
    else:
        raise AssertionError("Expected non-positive route distance to fail fast")


def test_load_setting_bundle_rejects_invalid_event_impact_rule_delta(tmp_path):
    bundle_path = tmp_path / "invalid-impact-rules.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "world_definition": {
                    "world_key": "invalid",
                    "display_name": "Invalid",
                    "lore_text": "Invalid lore",
                    "event_impact_rules": {
                        "meeting": {
                            "mood": "loud",
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_setting_bundle(bundle_path)
    except ValueError as exc:
        assert "event_impact_rules" in str(exc)
        assert "Unsupported impact delta type" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid impact rule delta")


def test_load_setting_bundle_rejects_unknown_event_impact_attribute(tmp_path):
    bundle_path = tmp_path / "unknown-impact-attribute.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "world_definition": {
                    "world_key": "invalid",
                    "display_name": "Invalid",
                    "lore_text": "Invalid lore",
                    "event_impact_rules": {
                        "meeting": {
                            "curiosity": 3,
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_setting_bundle(bundle_path)
    except ValueError as exc:
        assert "event_impact_rules" in str(exc)
        assert "Unsupported impact attribute" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown impact attribute")


def test_load_setting_bundle_rejects_unknown_propagation_section(tmp_path):
    bundle_path = tmp_path / "unknown-propagation-section.json"
    bundle_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "world_definition": {
                    "world_key": "invalid",
                    "display_name": "Invalid",
                    "lore_text": "Invalid lore",
                    "propagation_rules": {
                        "omens": {
                            "decay": 1,
                        }
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    try:
        load_setting_bundle(bundle_path)
    except ValueError as exc:
        assert "propagation_rules" in str(exc)
        assert "Unsupported propagation section" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown propagation section")


def test_world_apply_setting_bundle_rejects_invalid_propagation_rule_override():
    world = World()
    bundle = world.setting_bundle
    bundle.world_definition.propagation_rules = {
        "danger": {
            "decay": "fast",
        }
    }

    try:
        world.apply_setting_bundle(bundle)
    except ValueError as exc:
        assert "propagation_rules" in str(exc)
        assert "must be numeric" in str(exc)
    else:
        raise AssertionError("Expected ValueError for invalid propagation rule override")


def test_world_apply_setting_bundle_rejects_unknown_propagation_rule_key():
    world = World()
    bundle = world.setting_bundle
    bundle.world_definition.propagation_rules = {
        "danger": {
            "mystery": 4,
        }
    }

    try:
        world.apply_setting_bundle(bundle)
    except ValueError as exc:
        assert "propagation_rules" in str(exc)
        assert "Unsupported propagation key" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unknown propagation rule key")

"""Tests for the minimal PR-I SettingBundle foundation."""

from __future__ import annotations

import json

from fantasy_simulator.content.setting_bundle import (
    CalendarDefinition,
    SettingBundle,
    WorldDefinition,
    default_aethoria_bundle,
    load_setting_bundle,
)


def test_world_definition_round_trip():
    world_def = WorldDefinition(
        world_key="custom",
        display_name="Custom Realm",
        lore_text="Custom lore",
        era="Second Dawn",
        cultures=["Skyfolk"],
        factions=["Wardens"],
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


def test_default_aethoria_bundle_has_minimal_phase_i_slots():
    bundle = default_aethoria_bundle()

    assert bundle.schema_version == 1
    assert bundle.world_definition.world_key == "aethoria"
    assert bundle.world_definition.era == "Age of Embers"
    assert bundle.world_definition.cultures == []
    assert bundle.world_definition.factions == []
    assert bundle.world_definition.races
    assert bundle.world_definition.jobs
    assert bundle.world_definition.site_seeds
    assert bundle.world_definition.naming_rules.last_names
    capital_seed = next(
        seed for seed in bundle.world_definition.site_seeds
        if seed.location_id == "loc_aethoria_capital"
    )
    assert "capital" in capital_seed.tags
    assert "default_resident" in capital_seed.tags


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
    else:
        raise AssertionError("Expected ValueError for duplicate site seed names")


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

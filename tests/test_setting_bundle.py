"""Tests for the minimal PR-I SettingBundle foundation."""

from __future__ import annotations

import json

from fantasy_simulator.content.setting_bundle import (
    CalendarDefinition,
    SettingBundle,
    WorldDefinition,
    bundle_from_dict_validated,
    default_aethoria_bundle,
    load_setting_bundle,
)
from fantasy_simulator.world import World


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
    assert bundle.world_definition.route_seeds
    assert bundle.world_definition.naming_rules.last_names
    capital_seed = next(
        seed for seed in bundle.world_definition.site_seeds
        if seed.location_id == "loc_aethoria_capital"
    )
    assert "capital" in capital_seed.tags
    assert "default_resident" in capital_seed.tags


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

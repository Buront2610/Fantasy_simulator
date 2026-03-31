"""Tests for the minimal PR-I SettingBundle foundation."""

from __future__ import annotations

import json

from fantasy_simulator.content.setting_bundle import (
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
                },
            }
        ),
        encoding="utf-8",
    )

    bundle = load_setting_bundle(bundle_path)

    assert bundle.schema_version == 3
    assert bundle.world_definition.display_name == "Archive"
    assert bundle.world_definition.cultures == ["Archivists"]

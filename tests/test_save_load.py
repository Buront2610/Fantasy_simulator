"""
tests/test_save_load.py - Unit tests for save/load helpers.
"""

import json

from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.content.setting_bundle import (
    NamingRulesDefinition,
    SettingBundle,
    SiteSeedDefinition,
    WorldDefinition,
)
from fantasy_simulator.event_models import EventResult
from fantasy_simulator.persistence.migrations import CURRENT_VERSION
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.events import WorldEventRecord
from fantasy_simulator.world import World


def _make_world(n_chars: int = 3) -> World:
    world = World()
    creator = CharacterCreator()
    import random
    rng = random.Random(42)
    for i in range(n_chars):
        char = creator.create_random(rng=rng)
        world.add_character(char, rng=rng)
    return world


def _bundle_with_rule_overrides() -> SettingBundle:
    return SettingBundle(
        schema_version=1,
        world_definition=WorldDefinition(
            world_key="custom",
            display_name="Custom Realm",
            lore_text="Custom lore",
            event_impact_rules={"meeting": {"mood": 7}},
            propagation_rules={"road_damage_from_danger": {"danger_threshold": 101, "road_penalty": 0}},
        ),
    )


class TestSaveSimulation:
    def test_save_creates_file(self, tmp_path):
        path = tmp_path / "test_save.json"
        sim = Simulator(_make_world(), seed=0)
        result = save_simulation(sim, str(path))
        assert result is True
        assert path.exists()

    def test_save_produces_valid_json(self, tmp_path):
        path = tmp_path / "test_save.json"
        sim = Simulator(_make_world(), seed=0)
        save_simulation(sim, str(path))
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "world" in data
        assert "characters" in data
        assert "history" not in data
        assert "event_records" in data["world"]
        assert "event_log" not in data["world"]

    def test_save_returns_false_on_bad_path(self, tmp_path):
        sim = Simulator(_make_world(), seed=0)
        bad_path = str(tmp_path / "nonexistent_dir" / "file.json")
        result = save_simulation(sim, bad_path)
        assert result is False


class TestLoadSimulation:
    def test_load_returns_simulator(self, tmp_path):
        path = tmp_path / "snapshot.json"
        sim = Simulator(_make_world(), seed=0)
        sim.run(years=1)
        save_simulation(sim, str(path))
        restored = load_simulation(str(path))
        assert restored is not None
        assert restored.world.name == sim.world.name
        assert len(restored.world.characters) == len(sim.world.characters)

    def test_load_returns_none_for_missing_file(self):
        result = load_simulation("/nonexistent/path/file.json")
        assert result is None

    def test_load_returns_none_for_invalid_json(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("not valid json {{{", encoding="utf-8")
        result = load_simulation(str(path))
        assert result is None

    def test_load_returns_none_for_malformed_data(self, tmp_path):
        path = tmp_path / "malformed.json"
        path.write_text('{"missing": "world key"}', encoding="utf-8")
        result = load_simulation(str(path))
        assert result is None

    def test_round_trip_preserves_characters(self, tmp_path):
        path = tmp_path / "roundtrip.json"
        sim = Simulator(_make_world(n_chars=5), seed=7)
        sim.run(years=2)
        save_simulation(sim, str(path))
        restored = load_simulation(str(path))
        assert restored is not None
        original_names = sorted(c.name for c in sim.world.characters)
        restored_names = sorted(c.name for c in restored.world.characters)
        assert original_names == restored_names

    def test_round_trip_preserves_event_log(self, tmp_path):
        path = tmp_path / "events.json"
        sim = Simulator(_make_world(), seed=42)
        sim.run(years=3)
        save_simulation(sim, str(path))
        restored = load_simulation(str(path))
        assert restored is not None
        assert restored.world.event_log == sim.world.event_log

    def test_load_old_save_without_schema_version_migrates_to_v3(self, tmp_path):
        path = tmp_path / "old_save.json"
        old_save = {
            "characters": [
                {
                    "name": "Aldric",
                    "age": 25,
                    "gender": "Male",
                    "race": "Human",
                    "job": "Warrior",
                    "location": "Aethoria Capital",
                },
            ],
            "world": {
                "name": "Aethoria",
                "year": 1000,
                "grid": [
                    {
                        "name": "Aethoria Capital",
                        "description": "The capital.",
                        "region_type": "city",
                        "x": 2,
                        "y": 2,
                    },
                ],
                "event_records": [],
            },
            "history": [],
        }
        path.write_text(json.dumps(old_save), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is not None
        assert restored.world.characters[0].location_id == "loc_aethoria_capital"
        assert restored.world.characters[0].favorite is False
        capital = restored.world.get_location_by_id("loc_aethoria_capital")
        assert capital is not None
        assert capital.safety == 80
        assert capital.danger == 15
        assert restored.world.get_location_by_id("loc_thornwood") is not None

    def test_corrupted_rng_state_does_not_crash(self, tmp_path):
        """If rng_state is tampered with, loading should still succeed."""
        path = tmp_path / "tampered.json"
        sim = Simulator(_make_world(), seed=1)
        save_simulation(sim, str(path))
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["rng_state"] = "INVALID_STATE_DATA"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        restored = load_simulation(str(path))
        assert restored is not None  # Should not crash

    def test_load_returns_none_for_duplicate_character_ids(self, tmp_path):
        path = tmp_path / "duplicate_ids.json"
        duplicate_save = {
            "schema_version": 3,
            "world": {
                "name": "Aethoria",
                "lore": "Test lore",
                "width": 5,
                "height": 5,
                "year": 1000,
                "grid": [loc.to_dict() for loc in World().grid.values()],
                "event_log": [],
                "event_records": [],
                "active_adventures": [],
                "completed_adventures": [],
            },
            "characters": [
                {
                    "char_id": "dup1",
                    "name": "Aldric",
                    "age": 25,
                    "gender": "Male",
                    "race": "Human",
                    "job": "Warrior",
                    "location_id": "loc_aethoria_capital",
                },
                {
                    "char_id": "dup1",
                    "name": "Lyra",
                    "age": 22,
                    "gender": "Female",
                    "race": "Elf",
                    "job": "Mage",
                    "location_id": "loc_thornwood",
                },
            ],
            "events_per_year": 8,
            "adventure_steps_per_year": 3,
            "history": [],
        }
        path.write_text(json.dumps(duplicate_save), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is None

    def test_load_custom_bundle_recovers_legacy_character_location_names_via_embedded_bundle(self, tmp_path):
        path = tmp_path / "custom-bundle-location.json"
        sim = Simulator(World(name="Custom"), seed=0)
        sim.world.setting_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="custom",
                display_name="Custom",
                lore_text="Custom lore",
                site_seeds=[
                    SiteSeedDefinition(
                        location_id="hub_primary",
                        name="Clockwork Hub",
                        description="A custom site with a non-slug ID.",
                        region_type="city",
                        x=0,
                        y=0,
                    ),
                ],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )
        payload = sim.to_dict()
        payload["schema_version"] = CURRENT_VERSION
        payload["characters"] = [
            {
                "char_id": "char_1",
                "name": "Aldric",
                "age": 25,
                "gender": "Male",
                "race": "Human",
                "job": "Warrior",
                "location": "Clockwork Hub",
            }
        ]
        path.write_text(json.dumps(payload), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is not None
        assert restored.world.characters[0].location_id == "hub_primary"

    def test_migration_uses_embedded_custom_bundle_for_legacy_location_recovery(self, tmp_path):
        path = tmp_path / "legacy-custom-bundle.json"
        legacy_payload = {
            "schema_version": 1,
            "world": {
                "name": "Custom",
                "lore": "Custom lore",
                "width": 1,
                "height": 1,
                "year": 1000,
                "grid": [
                    {
                        "name": "Clockwork Hub",
                        "description": "A custom site with a non-slug ID.",
                        "region_type": "city",
                        "x": 0,
                        "y": 0,
                    }
                ],
                "event_records": [],
                "setting_bundle": {
                    "schema_version": 1,
                    "world_definition": {
                        "world_key": "custom",
                        "display_name": "Custom",
                        "lore_text": "Custom lore",
                        "site_seeds": [
                            {
                                "location_id": "hub_primary",
                                "name": "Clockwork Hub",
                                "description": "A custom site with a non-slug ID.",
                                "region_type": "city",
                                "x": 0,
                                "y": 0,
                            }
                        ],
                        "naming_rules": {
                            "last_names": ["Fallback"],
                        },
                    },
                },
            },
            "characters": [
                {
                    "char_id": "char_1",
                    "name": "Aldric",
                    "age": 25,
                    "gender": "Male",
                    "race": "Human",
                    "job": "Warrior",
                    "location": "Clockwork Hub",
                }
            ],
            "history": [],
        }
        path.write_text(json.dumps(legacy_payload), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is not None
        assert restored.world.get_location_by_id("hub_primary") is not None
        assert restored.world.get_location_by_id("loc_aethoria_capital") is None
        assert restored.world.characters[0].location_id == "hub_primary"

    def test_current_schema_load_remaps_legacy_fallback_slug_ids_to_bundle_ids(self, tmp_path):
        path = tmp_path / "current-custom-bundle.json"
        payload = {
            "schema_version": CURRENT_VERSION,
            "world": {
                "name": "Custom",
                "lore": "Custom lore",
                "width": 1,
                "height": 1,
                "year": 1000,
                "grid": [
                    {
                        "id": "loc_clockwork_hub",
                        "name": "Clockwork Hub",
                        "description": "A custom site with a non-slug ID.",
                        "region_type": "city",
                        "x": 0,
                        "y": 0,
                    }
                ],
                "event_log": [],
                "event_records": [
                    {
                        "record_id": "rec_1",
                        "kind": "meeting",
                        "year": 1000,
                        "month": 1,
                        "day": 1,
                        "location_id": "loc_clockwork_hub",
                    }
                ],
                "active_adventures": [
                    {
                        "character_id": "char_1",
                        "character_name": "Aldric",
                        "origin": "loc_clockwork_hub",
                        "destination": "loc_clockwork_hub",
                        "year_started": 1000,
                    }
                ],
                "completed_adventures": [],
                "terrain_map": {
                    "width": 1,
                    "height": 1,
                    "cells": [
                        {
                            "x": 0,
                            "y": 0,
                            "biome": "plains",
                            "elevation": 128,
                            "moisture": 128,
                            "temperature": 128,
                        }
                    ],
                },
                "sites": [
                    {
                        "location_id": "loc_clockwork_hub",
                        "x": 0,
                        "y": 0,
                        "site_type": "city",
                        "importance": 50,
                    }
                ],
                "routes": [
                    {
                        "route_id": "route_001",
                        "from_site_id": "loc_clockwork_hub",
                        "to_site_id": "loc_clockwork_hub",
                        "route_type": "road",
                        "distance": 1,
                        "blocked": False,
                    }
                ],
                "setting_bundle": {
                    "schema_version": 1,
                    "world_definition": {
                        "world_key": "custom",
                        "display_name": "Custom",
                        "lore_text": "Custom lore",
                        "site_seeds": [
                            {
                                "location_id": "hub_primary",
                                "name": "Clockwork Hub",
                                "description": "A custom site with a non-slug ID.",
                                "region_type": "city",
                                "x": 0,
                                "y": 0,
                            }
                        ],
                        "naming_rules": {
                            "last_names": ["Fallback"],
                        },
                    },
                },
            },
            "characters": [
                {
                    "char_id": "char_1",
                    "name": "Aldric",
                    "age": 25,
                    "gender": "Male",
                    "race": "Human",
                    "job": "Warrior",
                    "location_id": "loc_clockwork_hub",
                }
            ],
            "history": [],
        }
        path.write_text(json.dumps(payload), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is not None
        assert restored.world.get_location_by_id("hub_primary") is not None
        assert restored.world.characters[0].location_id == "hub_primary"
        assert restored.world.event_records[0].location_id == "hub_primary"
        assert restored.world.active_adventures[0].origin == "hub_primary"
        assert restored.world.sites[0].location_id == "hub_primary"
        assert restored.world.routes[0].from_site_id == "hub_primary"

    def test_migration_lifts_text_only_legacy_event_log_into_canonical_event_records(self, tmp_path):
        path = tmp_path / "legacy-event-log-only.json"
        world = World()
        payload = {
            "schema_version": CURRENT_VERSION - 1,
            "world": world.to_dict(),
            "characters": [],
            "history": [],
        }
        payload["world"]["event_records"] = []
        payload["world"]["event_log"] = ["Year 1000: A legacy omen spread through the capital."]
        path.write_text(json.dumps(payload), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is not None
        assert len(restored.world.event_records) == 1
        assert restored.world.event_records[0].legacy_event_log_entry == payload["world"]["event_log"][0]
        assert restored.world.event_records[0].description == payload["world"]["event_log"][0]
        restored.world.record_event(
            WorldEventRecord(
                record_id="rec_new",
                kind="meeting",
                year=restored.world.year,
                month=1,
                day=1,
                description="A new structured event.",
            )
        )
        compatibility_log = restored.world.get_compatibility_event_log()
        assert payload["world"]["event_log"][0] in compatibility_log
        assert any("A new structured event." in entry for entry in compatibility_log)

    def test_migration_lifts_legacy_history_into_canonical_event_records(self, tmp_path):
        path = tmp_path / "legacy-history-only.json"
        world = World()
        payload = {
            "schema_version": CURRENT_VERSION - 1,
            "world": world.to_dict(),
            "characters": [],
            "history": [
                {
                    "description": "A legacy battle occurred.",
                    "affected_characters": ["char_1"],
                    "stat_changes": {"char_1": {"strength": -2}},
                    "event_type": "battle",
                    "year": 1000,
                    "metadata": {"source": "legacy"},
                }
            ],
        }
        payload["world"]["event_records"] = []
        payload["world"]["event_log"] = []
        path.write_text(json.dumps(payload), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is not None
        assert len(restored.world.event_records) == 1
        assert restored.world.event_records[0].kind == "battle"
        assert len(restored.history) == 1
        assert restored.history[0].event_type == "battle"
        assert restored.history[0].stat_changes == {"char_1": {"strength": -2}}
        assert restored.history[0].metadata == {"source": "legacy"}

    def test_migration_lifts_mixed_legacy_history_and_event_log_into_canonical_event_records(self, tmp_path):
        path = tmp_path / "legacy-mixed-event-adapters.json"
        world = World()
        payload = {
            "schema_version": CURRENT_VERSION - 1,
            "world": world.to_dict(),
            "characters": [],
            "history": [
                {
                    "description": "A legacy battle occurred.",
                    "affected_characters": ["char_1"],
                    "stat_changes": {"char_1": {"strength": -2}},
                    "event_type": "battle",
                    "year": 1000,
                    "metadata": {"source": "legacy"},
                }
            ],
        }
        payload["world"]["event_records"] = []
        payload["world"]["event_log"] = ["Year 1000: A legacy omen spread through the capital."]
        path.write_text(json.dumps(payload), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is not None
        assert len(restored.world.event_records) == 2
        assert {record.kind for record in restored.world.event_records} == {"battle", "legacy_event_log"}
        assert len(restored.history) == 2
        assert {event.event_type for event in restored.history} == {"battle", "legacy_event_log"}
        battle_event = next(event for event in restored.history if event.event_type == "battle")
        legacy_log_event = next(event for event in restored.history if event.event_type == "legacy_event_log")
        assert battle_event.stat_changes == {"char_1": {"strength": -2}}
        assert battle_event.metadata == {"source": "legacy"}
        assert legacy_log_event.metadata == {"legacy_event_log_entry": True}
        assert payload["world"]["event_log"][0] in restored.world.get_compatibility_event_log()

    def test_save_load_preserves_non_default_bundle_rule_overrides(self, tmp_path):
        path = tmp_path / "custom-rules.json"
        sim = Simulator(World(name="Custom"), seed=0)
        sim.world.setting_bundle = _bundle_with_rule_overrides()

        assert save_simulation(sim, str(path)) is True

        restored = load_simulation(str(path))

        assert restored is not None
        assert restored.world.setting_bundle.world_definition.event_impact_rules == {"meeting": {"mood": 7}}
        assert restored.world.setting_bundle.world_definition.propagation_rules == {
            "road_damage_from_danger": {"danger_threshold": 101, "road_penalty": 0}
        }
        assert restored.world.event_impact_rules["meeting"]["mood"] == 7
        assert restored.world.event_impact_rules["battle"]["danger"] == 3
        assert restored.world.propagation_rules["road_damage_from_danger"]["danger_threshold"] == 101
        assert restored.world.propagation_rules["danger"]["cap"] == 15

    def test_save_load_round_trip_preserves_history_metadata_for_event_result_records(self, tmp_path):
        path = tmp_path / "legacy-history-roundtrip.json"
        sim = Simulator(_make_world(), seed=42)
        sim._record_event(  # noqa: SLF001 - compatibility regression test seam
            EventResult(
                description="A modern event-result path still carries legacy metadata.",
                affected_characters=["char_1", "char_2"],
                stat_changes={"char_1": {"wisdom": 2}},
                event_type="discovery",
                year=sim.world.year,
                metadata={"source": "runtime", "chain": {"step": 1}},
            ),
            location_id="loc_thornwood",
        )
        save_simulation(sim, str(path))

        restored = load_simulation(str(path))

        assert restored is not None
        assert len(restored.history) == 1
        assert restored.history[0].affected_characters == ["char_1", "char_2"]
        assert restored.history[0].stat_changes == {"char_1": {"wisdom": 2}}
        assert restored.history[0].metadata == {"source": "runtime", "chain": {"step": 1}}

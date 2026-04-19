"""
tests/test_save_load.py - Unit tests for save/load helpers.
"""

import json

from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.content.setting_bundle import (
    LanguageDefinition,
    NamingRulesDefinition,
    SettingBundle,
    SiteSeedDefinition,
    WorldDefinition,
)
from fantasy_simulator.event_models import EventResult
from fantasy_simulator.language.schema import SoundChangeRuleDefinition
from fantasy_simulator.persistence.migrations import CURRENT_VERSION
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.events import WorldEventRecord
from fantasy_simulator.world import World
from fantasy_simulator.reports import generate_monthly_report


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

    def test_round_trip_preserves_bundle_backed_blocked_route_state(self, tmp_path):
        path = tmp_path / "blocked-route.json"
        sim = Simulator(World(), seed=0)
        sim.world.routes[0].blocked = True

        save_simulation(sim, str(path))
        restored = load_simulation(str(path))

        assert restored is not None
        assert restored.world.routes[0].route_id == sim.world.routes[0].route_id
        assert restored.world.routes[0].blocked is True

    def test_load_returns_none_for_invalid_bundle_backed_blocked_route_state(self, tmp_path):
        path = tmp_path / "invalid-blocked-route.json"
        sim = Simulator(World(), seed=0)
        save_simulation(sim, str(path))
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["world"]["routes"][0]["blocked"] = "false"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        restored = load_simulation(str(path))

        assert restored is None

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

    def test_load_returns_none_for_duplicate_event_record_ids(self, tmp_path):
        path = tmp_path / "duplicate_event_ids.json"
        world_payload = World().to_dict()
        world_payload["event_records"] = [
            {
                "record_id": "dup_event",
                "kind": "battle",
                "year": 1000,
                "month": 1,
                "day": 1,
                "absolute_day": 0,
                "location_id": "loc_thornwood",
                "primary_actor_id": None,
                "secondary_actor_ids": [],
                "description": "First",
                "severity": 2,
                "visibility": "public",
                "calendar_key": "",
                "tags": [],
                "impacts": [],
            },
            {
                "record_id": "dup_event",
                "kind": "journey",
                "year": 1000,
                "month": 1,
                "day": 2,
                "absolute_day": 0,
                "location_id": "loc_thornwood",
                "primary_actor_id": None,
                "secondary_actor_ids": [],
                "description": "Second",
                "severity": 1,
                "visibility": "public",
                "calendar_key": "",
                "tags": [],
                "impacts": [],
            },
        ]
        duplicate_save = {
            "schema_version": CURRENT_VERSION,
            "world": world_payload,
            "characters": [],
            "events_per_year": 8,
            "adventure_steps_per_year": 3,
            "history": [],
        }
        path.write_text(json.dumps(duplicate_save), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is None

    def test_load_returns_none_for_duplicate_serialized_route_pairs(self, tmp_path):
        from fantasy_simulator.world import LocationState
        from fantasy_simulator.terrain import RouteEdge

        path = tmp_path / "duplicate_routes.json"
        world = World(_skip_defaults=True, width=3, height=1)
        for x, (loc_id, name) in enumerate(
            [("loc_alpha", "Alpha"), ("loc_bravo", "Bravo"), ("loc_charlie", "Charlie")]
        ):
            defaults = world.location_state_defaults(loc_id, "village")
            world._register_location(
                LocationState(
                    id=loc_id,
                    canonical_name=name,
                    description=f"{name} description",
                    region_type="village",
                    x=x,
                    y=0,
                    **defaults,
                )
            )
        world._build_terrain_from_grid()
        world.routes = [
            RouteEdge("route_alpha_bravo", "loc_alpha", "loc_bravo", "road"),
            RouteEdge("route_bravo_charlie", "loc_bravo", "loc_charlie", "road"),
        ]
        world._rebuild_route_index()
        world.atlas_layout = world._build_atlas_layout_from_current_state()
        duplicate_save = {
            "schema_version": CURRENT_VERSION,
            "world": world.to_dict(),
            "characters": [],
            "events_per_year": 0,
            "adventure_steps_per_year": 0,
            "history": [],
        }
        duplicate = dict(duplicate_save["world"]["routes"][0])
        duplicate["route_id"] = "route_duplicate"
        duplicate_save["world"]["routes"].append(duplicate)
        path.write_text(json.dumps(duplicate_save), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is None

    def test_load_returns_none_for_malformed_serialized_route_scalars(self, tmp_path):
        from fantasy_simulator.world import LocationState
        from fantasy_simulator.terrain import RouteEdge

        path = tmp_path / "malformed_routes.json"
        world = World(_skip_defaults=True, width=2, height=1)
        for x, (loc_id, name) in enumerate([("loc_alpha", "Alpha"), ("loc_bravo", "Bravo")]):
            defaults = world.location_state_defaults(loc_id, "village")
            world._register_location(
                LocationState(
                    id=loc_id,
                    canonical_name=name,
                    description=f"{name} description",
                    region_type="village",
                    x=x,
                    y=0,
                    **defaults,
                )
            )
        world.routes = [RouteEdge("route_alpha_bravo", "loc_alpha", "loc_bravo", "road")]
        world._build_terrain_from_grid()
        world.routes = [RouteEdge("route_alpha_bravo", "loc_alpha", "loc_bravo", "road")]
        world._rebuild_route_index()
        world.atlas_layout = world._build_atlas_layout_from_current_state()
        payload = {
            "schema_version": CURRENT_VERSION,
            "world": world.to_dict(),
            "characters": [],
            "events_per_year": 0,
            "adventure_steps_per_year": 0,
            "history": [],
        }
        payload["world"]["routes"][0]["route_id"] = 123
        payload["world"]["routes"][0]["from_site_id"] = ["loc_alpha"]
        payload["world"]["routes"][0]["route_type"] = 9
        payload["world"]["routes"][0]["distance"] = "7"
        path.write_text(json.dumps(payload), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is None

    def test_load_returns_none_for_duplicate_bundle_backed_route_state_entries(self, tmp_path):
        path = tmp_path / "duplicate-bundle-route-state.json"
        sim = Simulator(World(), seed=0)
        save_simulation(sim, str(path))
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        duplicate = dict(data["world"]["routes"][0])
        data["world"]["routes"].append(duplicate)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

        restored = load_simulation(str(path))

        assert restored is None

    def test_load_returns_none_for_bundle_backed_route_overlay_with_mismatched_endpoints(self, tmp_path):
        path = tmp_path / "bundle-route-endpoints.json"
        sim = Simulator(World(), seed=0)
        save_simulation(sim, str(path))
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["world"]["routes"][0]["from_site_id"] = "loc_thornwood"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

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

    def test_load_preserves_explicitly_disconnected_bundle_travel_contract(self, tmp_path):
        path = tmp_path / "disconnected-bundle.json"
        sim = Simulator(World(name="Disconnected", width=2, height=1), seed=0)
        sim.world.setting_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="disconnected",
                display_name="Disconnected",
                lore_text="No roads",
                site_seeds=[
                    SiteSeedDefinition(
                        location_id="loc_one",
                        name="One",
                        description="",
                        region_type="city",
                        x=0,
                        y=0,
                    ),
                    SiteSeedDefinition(
                        location_id="loc_two",
                        name="Two",
                        description="",
                        region_type="village",
                        x=1,
                        y=0,
                    ),
                ],
                route_seeds=[],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )
        save_simulation(sim, str(path))

        restored = load_simulation(str(path))

        assert restored is not None
        assert restored.world.routes == []
        assert restored.world.get_neighboring_locations("loc_one") == []
        assert restored.world.get_travel_neighboring_locations("loc_one") == []
        assert restored.world.reachable_location_ids("loc_one") == []

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
        assert restored.world.routes == []
        assert restored.world.get_neighboring_locations("hub_primary") == []

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

    def test_load_current_schema_backfills_watched_tags_for_untagged_canonical_records(self, tmp_path):
        path = tmp_path / "current-schema-untagged-watch.json"
        hero = {
            "char_id": "char_hero",
            "name": "Hero",
            "age": 25,
            "gender": "Male",
            "race": "Human",
            "job": "Warrior",
            "location_id": "loc_aethoria_capital",
            "favorite": True,
        }
        payload = {
            "schema_version": CURRENT_VERSION,
            "world": World().to_dict(),
            "characters": [hero],
            "history": [],
        }
        payload["world"]["event_records"] = [
            {
                "record_id": "untagged_watch_001",
                "kind": "meeting",
                "year": 1000,
                "month": 3,
                "day": 1,
                "absolute_day": 0,
                "location_id": "loc_aethoria_capital",
                "primary_actor_id": "char_hero",
                "secondary_actor_ids": [],
                "description": "Old canonical record without watched tags.",
                "severity": 2,
                "visibility": "public",
                "calendar_key": "",
                "tags": [],
                "impacts": [],
            }
        ]
        path.write_text(json.dumps(payload), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is not None
        restored.world.characters[0].favorite = False
        report = generate_monthly_report(restored.world, 1000, 3)
        assert f"{restored.world.WATCHED_ACTOR_TAG_PREFIX}char_hero" in restored.world.event_records[0].tags
        assert restored.world.WATCHED_ACTOR_INFERRED_TAG in restored.world.event_records[0].tags
        assert [entry.name for entry in report.character_entries] == ["Hero"]

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

    def test_migration_merges_existing_canonical_records_with_legacy_adapters(self, tmp_path):
        path = tmp_path / "legacy-mixed-with-canonical.json"
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
        payload["world"]["event_records"] = [
            {
                "record_id": "existing_001",
                "kind": "meeting",
                "year": 1000,
                "month": 4,
                "day": 2,
                "absolute_day": 0,
                "location_id": "loc_aethoria_capital",
                "primary_actor_id": "char_existing",
                "secondary_actor_ids": [],
                "description": "A canonical meeting already exists.",
                "severity": 2,
                "visibility": "public",
                "calendar_key": "",
                "tags": [],
                "impacts": [],
            }
        ]
        payload["world"]["event_log"] = ["Year 1000: A legacy omen spread through the capital."]
        path.write_text(json.dumps(payload), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is not None
        assert len(restored.world.event_records) == 3
        assert {record.kind for record in restored.world.event_records} == {
            "meeting", "battle", "legacy_event_log",
        }
        assert any(record.record_id == "existing_001" for record in restored.world.event_records)
        assert any(
            record.description == "A canonical meeting already exists."
            for record in restored.world.event_records
        )

    def test_migration_preserves_repeated_legacy_adapters_while_skipping_already_migrated_duplicates(self, tmp_path):
        path = tmp_path / "legacy-repeated-adapters.json"
        world = World()
        repeated_history_item = {
            "description": "A repeated legacy battle occurred.",
            "affected_characters": ["char_1"],
            "stat_changes": {"char_1": {"strength": -1}},
            "event_type": "battle",
            "year": 1000,
            "metadata": {"source": "legacy"},
        }
        repeated_log_entry = "Year 1000: A repeated legacy omen spread through the capital."
        payload = {
            "schema_version": CURRENT_VERSION - 1,
            "world": world.to_dict(),
            "characters": [],
            "history": [dict(repeated_history_item), dict(repeated_history_item)],
        }
        payload["world"]["event_records"] = [
            {
                "record_id": "legacy_history_000001",
                "kind": "battle",
                "year": 1000,
                "month": 1,
                "day": 1,
                "absolute_day": 0,
                "location_id": None,
                "primary_actor_id": "char_1",
                "secondary_actor_ids": [],
                "description": repeated_history_item["description"],
                "severity": 1,
                "visibility": "public",
                "calendar_key": "",
                "tags": [],
                "impacts": [],
                "legacy_event_result": dict(repeated_history_item),
                "legacy_event_log_entry": None,
            },
            {
                "record_id": "legacy_event_log_000001",
                "kind": "legacy_event_log",
                "year": 1000,
                "month": 1,
                "day": 1,
                "absolute_day": 0,
                "location_id": None,
                "primary_actor_id": None,
                "secondary_actor_ids": [],
                "description": repeated_log_entry,
                "severity": 1,
                "visibility": "public",
                "calendar_key": "",
                "tags": ["legacy_event_log"],
                "impacts": [],
                "legacy_event_result": {
                    "description": repeated_log_entry,
                    "affected_characters": [],
                    "stat_changes": {},
                    "event_type": "legacy_event_log",
                    "year": 1000,
                    "metadata": {"legacy_event_log_entry": True},
                },
                "legacy_event_log_entry": repeated_log_entry,
            },
        ]
        payload["world"]["event_log"] = [repeated_log_entry, repeated_log_entry]
        path.write_text(json.dumps(payload), encoding="utf-8")

        restored = load_simulation(str(path))

        assert restored is not None
        battle_records = [record for record in restored.world.event_records if record.kind == "battle"]
        legacy_log_records = [
            record for record in restored.world.event_records if record.kind == "legacy_event_log"
        ]
        assert len(battle_records) == 2
        assert len(legacy_log_records) == 2
        assert len(restored.world.event_records) == 4

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

    def test_save_load_preserves_language_evolution_history(self, tmp_path):
        path = tmp_path / "language-evolution.json"
        world = World(name="Custom", year=1000)
        world.setting_bundle = SettingBundle(
            schema_version=1,
            world_definition=WorldDefinition(
                world_key="custom",
                display_name="Custom",
                lore_text="Custom lore",
                site_seeds=[
                    SiteSeedDefinition(
                        location_id="loc_custom",
                        name="Custom",
                        description="Custom site.",
                        region_type="city",
                        x=0,
                        y=0,
                        language_key="custom_lang",
                    ),
                ],
                languages=[
                    LanguageDefinition(
                        language_key="custom_lang",
                        display_name="Custom Lang",
                        seed_syllables=["tor", "sel", "mar"],
                        evolution_rule_pool=[
                            SoundChangeRuleDefinition(
                                rule_key="custom_lang.rhotic_drift",
                                source="r",
                                target="rh",
                            )
                        ],
                        evolution_interval_years=2,
                    )
                ],
                naming_rules=NamingRulesDefinition(last_names=["Fallback"]),
            ),
        )
        sim = Simulator(world, seed=0)
        sim.advance_years(2)

        assert save_simulation(sim, str(path)) is True
        restored = load_simulation(str(path))

        assert restored is not None
        assert len(restored.world.language_evolution_history) == 1
        assert restored.world.language_evolution_history[0].language_key == "custom_lang"
        assert restored.world.language_status()[0]["sound_shifts"].get("r") == "rh"

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

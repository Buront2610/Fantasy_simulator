"""
tests/test_migrations.py - Unit tests for schema migration.
"""

from fantasy_simulator.persistence.migrations import (
    CURRENT_VERSION,
    _migrate_v1_to_v2,
    _migrate_v2_to_v3,
    _migrate_v4_to_v5,
    migrate,
)
from fantasy_simulator.content.world_data import NAME_TO_LOCATION_ID


class TestMigrations:
    def test_no_schema_version_treated_as_v0(self):
        data = {"characters": [], "world": {"grid": []}}
        result = migrate(data)
        assert result["schema_version"] == CURRENT_VERSION

    def test_character_location_migrated(self):
        data = {
            "characters": [
                {
                    "name": "Hero",
                    "age": 25,
                    "gender": "Male",
                    "race": "Human",
                    "job": "Warrior",
                    "location": "Aethoria Capital",
                },
            ],
            "world": {"grid": []},
        }
        result = migrate(data)
        char = result["characters"][0]
        assert "location" not in char
        assert char["location_id"] == "loc_aethoria_capital"

    def test_grid_locations_get_ids(self):
        data = {
            "schema_version": 1,
            "characters": [],
            "world": {
                "grid": [
                    {
                        "name": "Aethoria Capital",
                        "description": "The capital.",
                        "region_type": "city",
                        "x": 2,
                        "y": 2,
                    },
                ],
            },
        }
        result = migrate(data)
        loc = result["world"]["grid"][0]
        assert loc["id"] == "loc_aethoria_capital"
        assert loc["canonical_name"] == "Aethoria Capital"
        assert loc["prosperity"] == 85

    def test_adventure_origin_destination_migrated(self):
        data = {
            "schema_version": 1,
            "characters": [],
            "world": {
                "grid": [],
                "active_adventures": [
                    {"origin": "Aethoria Capital", "destination": "Thornwood"},
                ],
                "completed_adventures": [
                    {"origin": "Millhaven", "destination": "Sunken Ruins"},
                ],
            },
        }
        result = migrate(data)
        active = result["world"]["active_adventures"][0]
        assert active["origin"] == "loc_aethoria_capital"
        assert active["destination"] == "loc_thornwood"
        completed = result["world"]["completed_adventures"][0]
        assert completed["origin"] == "loc_millhaven"
        assert completed["destination"] == "loc_sunken_ruins"

    def test_unknown_location_uses_slug_fallback(self):
        data = {
            "schema_version": 1,
            "characters": [
                {
                    "name": "Hero",
                    "age": 25,
                    "gender": "Male",
                    "race": "Human",
                    "job": "Warrior",
                    "location": "Unknown Place",
                },
            ],
            "world": {"grid": []},
        }
        result = migrate(data)
        assert result["characters"][0]["location_id"] == "loc_unknown_place"

    def test_all_known_locations_mapped(self):
        for name, loc_id in NAME_TO_LOCATION_ID.items():
            data = {
                "characters": [
                    {
                        "name": "X",
                        "age": 20,
                        "gender": "Male",
                        "race": "Human",
                        "job": "Warrior",
                        "location": name,
                    },
                ],
                "world": {"grid": []},
            }
            result = _migrate_v1_to_v2(data)
            assert result["characters"][0]["location_id"] == loc_id

    def test_v3_adds_character_flags_and_location_state(self):
        data = {
            "schema_version": 2,
            "characters": [
                {
                    "name": "Hero",
                    "age": 25,
                    "gender": "Male",
                    "race": "Human",
                    "job": "Warrior",
                    "location_id": "loc_aethoria_capital",
                },
            ],
            "world": {
                "grid": [
                    {
                        "id": "loc_aethoria_capital",
                        "name": "Aethoria Capital",
                        "description": "The capital.",
                        "region_type": "city",
                        "x": 2,
                        "y": 2,
                    },
                ],
                "event_records": [{"kind": "battle", "year": 1001, "location_id": "invalid"}],
            },
        }
        result = _migrate_v2_to_v3(data)
        char = result["characters"][0]
        loc = result["world"]["grid"][0]
        assert char["favorite"] is False
        assert char["spotlighted"] is False
        assert char["playable"] is False
        assert loc["canonical_name"] == "Aethoria Capital"
        assert loc["safety"] == 80
        assert loc["danger"] == 15
        assert result["world"]["event_records"][0]["location_id"] is None

    def test_v3_rebuilds_recent_event_ids_from_existing_event_records(self):
        data = {
            "schema_version": 2,
            "characters": [],
            "world": {
                "grid": [
                    {
                        "id": "loc_aethoria_capital",
                        "name": "Aethoria Capital",
                        "description": "The capital.",
                        "region_type": "city",
                        "x": 2,
                        "y": 2,
                    },
                    {
                        "id": "loc_thornwood",
                        "name": "Thornwood",
                        "description": "Forest.",
                        "region_type": "forest",
                        "x": 0,
                        "y": 1,
                    },
                ],
                "event_records": [
                    {"record_id": "r1", "kind": "battle", "year": 1001, "location_id": "loc_aethoria_capital"},
                    {"record_id": "r2", "kind": "meeting", "year": 1002, "location_id": "loc_thornwood"},
                    {"record_id": "r3", "kind": "journey", "year": 1003, "location_id": "loc_aethoria_capital"},
                    {"record_id": "r4", "kind": "battle", "year": 1004, "location_id": "invalid"},
                ],
            },
        }

        result = _migrate_v2_to_v3(data)

        capital = result["world"]["grid"][0]
        thornwood = result["world"]["grid"][1]
        assert capital["recent_event_ids"] == ["r1", "r3"]
        assert thornwood["recent_event_ids"] == ["r2"]
        assert result["world"]["event_records"][3]["location_id"] is None

    def test_already_v3_data_unchanged(self):
        data = {
            "schema_version": 3,
            "characters": [
                {
                    "name": "Hero",
                    "age": 25,
                    "gender": "Male",
                    "race": "Human",
                    "job": "Warrior",
                    "location_id": "loc_aethoria_capital",
                    "favorite": True,
                },
            ],
            "world": {
                "grid": [
                    {
                        "id": "loc_aethoria_capital",
                        "canonical_name": "Aethoria Capital",
                        "name": "Aethoria Capital",
                        "description": "The capital.",
                        "region_type": "city",
                        "x": 2,
                        "y": 2,
                        "prosperity": 85,
                        "safety": 80,
                        "mood": 65,
                        "danger": 15,
                        "traffic": 90,
                        "rumor_heat": 60,
                        "road_condition": 85,
                        "visited": False,
                        "controlling_faction_id": None,
                        "recent_event_ids": [],
                        "aliases": [],
                        "memorial_ids": [],
                    },
                ],
                "active_adventures": [],
                "completed_adventures": [],
                "event_records": [],
            },
        }
        result = migrate(data)
        # v3 data is migrated forward to CURRENT_VERSION (now 4 after PR-E)
        assert result["schema_version"] == CURRENT_VERSION
        assert result["characters"][0]["favorite"] is True
        assert result["world"]["grid"][0]["canonical_name"] == "Aethoria Capital"
        # v3→v4 migration adds party fields to adventures (none here, so grid stays intact)

    def test_current_version_constant(self):
        assert CURRENT_VERSION == 8

    def test_v3_to_v4_adds_party_fields_to_adventures(self):
        """PR-E migration adds party fields to existing AdventureRun data."""
        data = {
            "schema_version": 3,
            "characters": [],
            "world": {
                "grid": [],
                "event_records": [],
                "active_adventures": [
                    {
                        "character_id": "hero1",
                        "character_name": "Aldric",
                        "adventure_id": "abc123",
                        "origin": "loc_aethoria_capital",
                        "destination": "loc_thornwood",
                        "year_started": 1000,
                        "state": "exploring",
                        "injury_status": "none",
                        "steps_taken": 1,
                        "outcome": None,
                        "loot_summary": [],
                        "summary_log": [],
                        "detail_log": [],
                        "pending_choice": None,
                        "resolution_year": None,
                    }
                ],
                "completed_adventures": [],
            },
        }
        result = migrate(data)
        assert result["schema_version"] == CURRENT_VERSION  # migrates to latest (v4→v5 also applied)

        adv = result["world"]["active_adventures"][0]
        # member_ids should default to [character_id] for solo legacy runs
        assert adv["member_ids"] == ["hero1"]
        assert adv["party_id"] is None
        assert adv["policy"] == "cautious"
        assert adv["retreat_rule"] == "on_serious"
        assert adv["supply_state"] == "full"
        assert adv["danger_level"] == 50

    def test_v3_to_v4_already_has_member_ids_respected(self):
        """If member_ids already exists (partial pre-migration), it is preserved."""
        data = {
            "schema_version": 3,
            "characters": [],
            "world": {
                "grid": [],
                "event_records": [],
                "active_adventures": [
                    {
                        "character_id": "c1",
                        "character_name": "A",
                        "adventure_id": "xyz",
                        "origin": "loc_aethoria_capital",
                        "destination": "loc_thornwood",
                        "year_started": 1000,
                        "state": "traveling",
                        "member_ids": ["c1", "c2"],   # already set
                        "policy": "assault",
                    }
                ],
                "completed_adventures": [],
            },
        }
        result = migrate(data)
        adv = result["world"]["active_adventures"][0]
        assert adv["member_ids"] == ["c1", "c2"]
        assert adv["policy"] == "assault"

    def test_future_version_raises_error(self):
        import pytest

        data = {
            "schema_version": 999,
            "characters": [],
            "world": {"grid": []},
        }
        with pytest.raises(ValueError, match="schema_version 999"):
            migrate(data)

    def test_v4_to_v5_adds_live_traces_and_memorials(self):
        """PR-F migration adds live_traces to locations and memorials dict to world."""
        data = {
            "schema_version": 4,
            "characters": [],
            "world": {
                "grid": [
                    {
                        "id": "loc_aethoria_capital",
                        "canonical_name": "Aethoria Capital",
                        "name": "Aethoria Capital",
                        "description": "The capital.",
                        "region_type": "city",
                        "x": 2,
                        "y": 2,
                    },
                    {
                        "id": "loc_thornwood",
                        "canonical_name": "Thornwood",
                        "name": "Thornwood",
                        "description": "Forest.",
                        "region_type": "forest",
                        "x": 0,
                        "y": 1,
                    },
                ],
                "event_records": [],
                "active_adventures": [],
                "completed_adventures": [],
            },
        }
        result = _migrate_v4_to_v5(data)
        assert result["schema_version"] == 5

        # Every location gets live_traces
        for loc_data in result["world"]["grid"]:
            assert "live_traces" in loc_data
            assert loc_data["live_traces"] == []

        # World gets memorials dict
        assert "memorials" in result["world"]
        assert result["world"]["memorials"] == {}

    def test_v4_to_v5_existing_live_traces_not_overwritten(self):
        """If live_traces already present, migration leaves them alone."""
        data = {
            "schema_version": 4,
            "characters": [],
            "world": {
                "grid": [
                    {
                        "id": "loc_aethoria_capital",
                        "name": "Aethoria Capital",
                        "description": "...",
                        "region_type": "city",
                        "x": 2, "y": 2,
                        "live_traces": [{"year": 1001, "char_name": "X", "text": "X was here."}],
                    },
                ],
                "event_records": [],
                "active_adventures": [],
                "completed_adventures": [],
            },
        }
        result = _migrate_v4_to_v5(data)
        loc = result["world"]["grid"][0]
        assert len(loc["live_traces"]) == 1
        assert loc["live_traces"][0]["char_name"] == "X"

    def test_full_migration_from_v0_reaches_v5(self):
        """A bare-minimum v0 save file migrates all the way to CURRENT_VERSION (5)."""
        data = {"characters": [], "world": {"grid": []}}
        result = migrate(data)
        assert result["schema_version"] == CURRENT_VERSION

"""
tests/test_migrations.py - Unit tests for schema migration.
"""

from migrations import CURRENT_VERSION, migrate, _migrate_v1_to_v2
from world_data import NAME_TO_LOCATION_ID


class TestMigrateV1ToV2:
    def test_no_schema_version_treated_as_v1(self):
        data = {"characters": [], "world": {"grid": []}}
        result = migrate(data)
        assert result["schema_version"] == CURRENT_VERSION

    def test_character_location_migrated(self):
        data = {
            "characters": [
                {"name": "Hero", "age": 25, "gender": "Male", "race": "Human", "job": "Warrior",
                 "location": "Aethoria Capital"},
            ],
            "world": {"grid": []},
        }
        result = migrate(data)
        char = result["characters"][0]
        assert "location" not in char
        assert char["location_id"] == "loc_aethoria_capital"

    def test_character_with_location_id_unchanged(self):
        data = {
            "schema_version": 2,
            "characters": [
                {"name": "Hero", "age": 25, "gender": "Male", "race": "Human", "job": "Warrior",
                 "location_id": "loc_aethoria_capital"},
            ],
            "world": {"grid": []},
        }
        result = migrate(data)
        assert result["characters"][0]["location_id"] == "loc_aethoria_capital"

    def test_grid_locations_get_ids(self):
        data = {
            "characters": [],
            "world": {
                "grid": [
                    {"name": "Aethoria Capital", "description": "The capital.", "region_type": "city", "x": 2, "y": 2},
                ],
            },
        }
        result = migrate(data)
        loc = result["world"]["grid"][0]
        assert loc["id"] == "loc_aethoria_capital"

    def test_adventure_origin_destination_migrated(self):
        data = {
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

    def test_already_v2_data_unchanged(self):
        data = {
            "schema_version": 2,
            "characters": [
                {"name": "Hero", "age": 25, "gender": "Male", "race": "Human", "job": "Warrior",
                 "location_id": "loc_aethoria_capital"},
            ],
            "world": {
                "grid": [
                    {"id": "loc_aethoria_capital", "name": "Aethoria Capital",
                     "description": "The capital.", "region_type": "city", "x": 2, "y": 2},
                ],
                "active_adventures": [],
                "completed_adventures": [],
            },
        }
        result = migrate(data)
        assert result["schema_version"] == 2
        assert result["characters"][0]["location_id"] == "loc_aethoria_capital"
        assert result["world"]["grid"][0]["id"] == "loc_aethoria_capital"

    def test_unknown_location_uses_default_capital(self):
        data = {
            "characters": [
                {"name": "Hero", "age": 25, "gender": "Male", "race": "Human", "job": "Warrior",
                 "location": "Unknown Place"},
            ],
            "world": {"grid": []},
        }
        result = migrate(data)
        assert result["characters"][0]["location_id"] == "loc_aethoria_capital"

    def test_all_known_locations_mapped(self):
        for name, loc_id in NAME_TO_LOCATION_ID.items():
            data = {
                "characters": [
                    {"name": "X", "age": 20, "gender": "Male", "race": "Human", "job": "Warrior",
                     "location": name},
                ],
                "world": {"grid": []},
            }
            result = _migrate_v1_to_v2(data)
            assert result["characters"][0]["location_id"] == loc_id

    def test_current_version_constant(self):
        assert CURRENT_VERSION == 2

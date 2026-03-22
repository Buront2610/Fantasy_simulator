"""
tests/test_location.py - Unit tests for the LocationState class and migrations.
"""

import pytest

from location import (
    LocationState,
    make_location_id,
)
from migrations import apply_migrations, migrate_v0_to_v1, migrate_v1_to_v2, CURRENT_VERSION
from world import World
from character import Character
from world_data import DEFAULT_LOCATIONS


# ---------------------------------------------------------------------------
# make_location_id
# ---------------------------------------------------------------------------

class TestMakeLocationId:
    def test_lowercase_with_underscores(self):
        assert make_location_id("Aethoria Capital") == "aethoria_capital"

    def test_multi_word(self):
        assert make_location_id("The Grey Pass") == "the_grey_pass"

    def test_special_chars_replaced(self):
        assert make_location_id("Goblin's Den!") == "goblin_s_den"

    def test_strips_leading_trailing_underscores(self):
        result = make_location_id("  Leading")
        assert not result.startswith("_")
        assert not result.endswith("_")

    def test_consistent_across_calls(self):
        name = "Frostpeak Summit"
        assert make_location_id(name) == make_location_id(name)

    def test_all_default_locations_produce_unique_ids(self):
        ids = [make_location_id(entry[0]) for entry in DEFAULT_LOCATIONS]
        assert len(ids) == len(set(ids)), "Duplicate IDs generated for DEFAULT_LOCATIONS"


# ---------------------------------------------------------------------------
# LocationState construction
# ---------------------------------------------------------------------------

class TestLocationStateConstruction:
    def test_basic_fields(self):
        loc = LocationState(
            id="test_city",
            canonical_name="Test City",
            description="A test city.",
            region_type="city",
            x=0,
            y=0,
        )
        assert loc.id == "test_city"
        assert loc.canonical_name == "Test City"
        assert loc.description == "A test city."
        assert loc.region_type == "city"
        assert loc.x == 0
        assert loc.y == 0

    def test_name_property_alias(self):
        loc = LocationState(
            id="foo", canonical_name="Foo Place", description="", region_type="plains", x=0, y=0
        )
        assert loc.name == "Foo Place"
        assert loc.name == loc.canonical_name

    def test_default_state_values(self):
        loc = LocationState(id="x", canonical_name="X", description="", region_type="plains", x=0, y=0)
        assert loc.prosperity == 50
        assert loc.safety == 50
        assert loc.mood == 50
        assert loc.danger == 50
        assert loc.traffic == 50
        assert loc.rumor_heat == 30
        assert loc.road_condition == 50

    def test_default_flags(self):
        loc = LocationState(id="x", canonical_name="X", description="", region_type="plains", x=0, y=0)
        assert loc.visited is False
        assert loc.controlling_faction_id is None
        assert loc.aliases == []
        assert loc.memorial_ids == []
        assert loc.recent_event_ids == []

    def test_make_id_static(self):
        assert LocationState.make_id("Aethoria Capital") == "aethoria_capital"


# ---------------------------------------------------------------------------
# State value clamping (§15.5 invariant: 0-100)
# ---------------------------------------------------------------------------

class TestLocationStateStateClamping:
    @pytest.mark.parametrize("field_name", [
        "prosperity", "safety", "mood", "danger", "traffic", "rumor_heat", "road_condition"
    ])
    def test_clamps_above_100(self, field_name):
        loc = LocationState(
            id="x", canonical_name="X", description="", region_type="plains", x=0, y=0,
            **{field_name: 150},
        )
        assert getattr(loc, field_name) == 100

    @pytest.mark.parametrize("field_name", [
        "prosperity", "safety", "mood", "danger", "traffic", "rumor_heat", "road_condition"
    ])
    def test_clamps_below_zero(self, field_name):
        loc = LocationState(
            id="x", canonical_name="X", description="", region_type="plains", x=0, y=0,
            **{field_name: -10},
        )
        assert getattr(loc, field_name) == 0

    @pytest.mark.parametrize("value", [0, 1, 50, 99, 100])
    def test_valid_values_pass_through(self, value):
        loc = LocationState(
            id="x", canonical_name="X", description="", region_type="plains", x=0, y=0,
            prosperity=value,
        )
        assert loc.prosperity == value


# ---------------------------------------------------------------------------
# Display label derivation (§5.3)
# ---------------------------------------------------------------------------

class TestLocationStateLabels:
    def test_prosperity_label_ruined(self):
        loc = LocationState(id="x", canonical_name="X", description="", region_type="dungeon", x=0, y=0,
                            prosperity=0)
        assert loc.prosperity_label == "ruined"

    def test_prosperity_label_thriving(self):
        loc = LocationState(id="x", canonical_name="X", description="", region_type="city", x=0, y=0,
                            prosperity=80)
        assert loc.prosperity_label == "thriving"

    def test_safety_label_peaceful(self):
        loc = LocationState(id="x", canonical_name="X", description="", region_type="city", x=0, y=0,
                            safety=90)
        assert loc.safety_label == "peaceful"

    def test_safety_label_lawless(self):
        loc = LocationState(id="x", canonical_name="X", description="", region_type="dungeon", x=0, y=0,
                            safety=5)
        assert loc.safety_label == "lawless"

    def test_mood_label_festive(self):
        loc = LocationState(id="x", canonical_name="X", description="", region_type="city", x=0, y=0,
                            mood=85)
        assert loc.mood_label == "festive"

    def test_mood_label_grieving(self):
        loc = LocationState(id="x", canonical_name="X", description="", region_type="dungeon", x=0, y=0,
                            mood=10)
        assert loc.mood_label == "grieving"

    @pytest.mark.parametrize("prosperity,expected", [
        (0, "ruined"), (10, "ruined"),
        (20, "declining"), (40, "declining"),
        (45, "stable"), (74, "stable"),
        (75, "thriving"), (100, "thriving"),
    ])
    def test_prosperity_all_thresholds(self, prosperity, expected):
        loc = LocationState(id="x", canonical_name="X", description="", region_type="plains", x=0, y=0,
                            prosperity=prosperity)
        assert loc.prosperity_label == expected


# ---------------------------------------------------------------------------
# Icon property
# ---------------------------------------------------------------------------

class TestLocationStateIcon:
    @pytest.mark.parametrize("region_type,expected_icon", [
        ("city", "C"), ("village", "V"), ("forest", "F"),
        ("dungeon", "D"), ("mountain", "M"), ("plains", "P"), ("sea", "~"),
    ])
    def test_known_region_types(self, region_type, expected_icon):
        loc = LocationState(id="x", canonical_name="X", description="", region_type=region_type, x=0, y=0)
        assert loc.icon == expected_icon

    def test_unknown_region_type_returns_question_mark(self):
        loc = LocationState(id="x", canonical_name="X", description="", region_type="void", x=0, y=0)
        assert loc.icon == "?"


# ---------------------------------------------------------------------------
# Serialisation
# ---------------------------------------------------------------------------

class TestLocationStateSerialization:
    def _make_loc(self, **kwargs) -> LocationState:
        defaults = dict(
            id="aethoria_capital", canonical_name="Aethoria Capital",
            description="The grand capital.", region_type="city", x=2, y=2,
            prosperity=70, safety=65, mood=55, danger=25, traffic=70,
            rumor_heat=45, road_condition=75,
        )
        defaults.update(kwargs)
        return LocationState(**defaults)

    def test_to_dict_has_id(self):
        d = self._make_loc().to_dict()
        assert d["id"] == "aethoria_capital"

    def test_to_dict_has_canonical_name(self):
        d = self._make_loc().to_dict()
        assert d["canonical_name"] == "Aethoria Capital"

    def test_to_dict_has_backward_compat_name_key(self):
        d = self._make_loc().to_dict()
        assert d["name"] == "Aethoria Capital"

    def test_to_dict_has_state_values(self):
        d = self._make_loc(prosperity=70, danger=25).to_dict()
        assert d["prosperity"] == 70
        assert d["danger"] == 25

    def test_round_trip_new_format(self):
        loc = self._make_loc()
        restored = LocationState.from_dict(loc.to_dict())
        assert restored.id == loc.id
        assert restored.canonical_name == loc.canonical_name
        assert restored.prosperity == loc.prosperity
        assert restored.safety == loc.safety
        assert restored.danger == loc.danger
        assert restored.traffic == loc.traffic

    def test_from_dict_old_location_format(self):
        """Load a legacy Location dict (no id/canonical_name/state values)."""
        old_data = {
            "name": "Aethoria Capital",
            "description": "The grand capital.",
            "region_type": "city",
            "x": 2,
            "y": 2,
        }
        loc = LocationState.from_dict(old_data)
        assert loc.canonical_name == "Aethoria Capital"
        assert loc.id == "aethoria_capital"
        assert loc.prosperity == 50  # default

    def test_from_dict_derives_id_from_name_when_missing(self):
        data = {"name": "Frostpeak Summit", "description": "", "region_type": "mountain", "x": 0, "y": 0}
        loc = LocationState.from_dict(data)
        assert loc.id == "frostpeak_summit"

    def test_from_dict_uses_explicit_id_when_present(self):
        data = {
            "id": "custom_id",
            "canonical_name": "Custom Place",
            "name": "Custom Place",
            "description": "",
            "region_type": "plains",
            "x": 0,
            "y": 0,
        }
        loc = LocationState.from_dict(data)
        assert loc.id == "custom_id"


# ---------------------------------------------------------------------------
# World integration: id-based lookup and invariants
# ---------------------------------------------------------------------------

class TestWorldLocationIntegration:
    def test_all_world_locations_have_ids(self):
        world = World()
        for loc in world.grid.values():
            assert loc.id, f"Location '{loc.canonical_name}' has no id"

    def test_location_ids_are_unique_in_world(self):
        world = World()
        ids = [loc.id for loc in world.grid.values()]
        assert len(ids) == len(set(ids))

    def test_canonical_names_are_unique_in_world(self):
        world = World()
        names = [loc.canonical_name for loc in world.grid.values()]
        assert len(names) == len(set(names))

    def test_get_location_by_id(self):
        world = World()
        loc = world.get_location_by_id("aethoria_capital")
        assert loc is not None
        assert loc.canonical_name == "Aethoria Capital"

    def test_get_location_by_id_returns_none_for_unknown(self):
        world = World()
        assert world.get_location_by_id("nonexistent_place") is None

    def test_character_location_id_matches_world(self):
        """Invariant: all character.location_ids reference valid LocationState.ids."""
        world = World()
        char = Character(name="Test", age=25, gender="Male", race="Human", job="Warrior",
                         location="Aethoria Capital")
        world.add_character(char)
        valid_ids = {loc.id for loc in world.grid.values()}
        for c in world.characters:
            assert c.location_id in valid_ids, f"character.location_id {c.location_id!r} not in world"

    def test_get_characters_at_location_uses_location_id(self):
        world = World()
        char = Character(name="Alice", age=25, gender="Female", race="Human", job="Mage",
                         location="Aethoria Capital")
        world.add_character(char)
        result = world.get_characters_at_location("Aethoria Capital")
        assert char in result

    def test_world_roundtrip_preserves_location_ids(self):
        world = World()
        payload = world.to_dict()
        restored = World.from_dict(payload)
        original_ids = {loc.id for loc in world.grid.values()}
        restored_ids = {loc.id for loc in restored.grid.values()}
        assert original_ids == restored_ids

    def test_world_roundtrip_preserves_state_values(self):
        world = World()
        cap = world.get_location_by_id("aethoria_capital")
        assert cap is not None
        original_danger = cap.danger
        payload = world.to_dict()
        restored = World.from_dict(payload)
        cap2 = restored.get_location_by_id("aethoria_capital")
        assert cap2 is not None
        assert cap2.danger == original_danger


# ---------------------------------------------------------------------------
# Character location_id
# ---------------------------------------------------------------------------

class TestCharacterLocationId:
    def test_location_id_derived_from_location_name(self):
        c = Character(name="Test", age=25, gender="Male", race="Human", job="Warrior",
                      location="Aethoria Capital")
        assert c.location_id == "aethoria_capital"

    def test_explicit_location_id_used_when_provided(self):
        c = Character(name="Test", age=25, gender="Male", race="Human", job="Warrior",
                      location="Aethoria Capital", location_id="custom_id")
        assert c.location_id == "custom_id"

    def test_setting_location_updates_location_id(self):
        c = Character(name="Test", age=25, gender="Male", race="Human", job="Warrior",
                      location="Aethoria Capital")
        c.location = "Frostpeak Summit"
        assert c.location_id == "frostpeak_summit"
        assert c.location == "Frostpeak Summit"

    def test_location_property_returns_name(self):
        c = Character(name="Test", age=25, gender="Male", race="Human", job="Warrior",
                      location="Aethoria Capital")
        assert c.location == "Aethoria Capital"

    def test_to_dict_includes_location_id(self):
        c = Character(name="Test", age=25, gender="Male", race="Human", job="Warrior",
                      location="Aethoria Capital")
        d = c.to_dict()
        assert "location_id" in d
        assert d["location_id"] == "aethoria_capital"

    def test_from_dict_reads_location_id(self):
        data = {
            "name": "Test", "age": 25, "gender": "Male", "race": "Human", "job": "Warrior",
            "location": "Frostpeak Summit",
            "location_id": "frostpeak_summit",
        }
        c = Character.from_dict(data)
        assert c.location_id == "frostpeak_summit"
        assert c.location == "Frostpeak Summit"

    def test_from_dict_derives_location_id_from_old_save(self):
        """Old saves have only 'location'; location_id should be derived."""
        data = {
            "name": "OldChar", "age": 30, "gender": "Female", "race": "Elf", "job": "Mage",
            "location": "Silverbrook",
        }
        c = Character.from_dict(data)
        assert c.location_id == "silverbrook"
        assert c.location == "Silverbrook"

    def test_roundtrip_preserves_location_id(self):
        c = Character(name="Test", age=25, gender="Male", race="Human", job="Warrior",
                      location="Millhaven")
        restored = Character.from_dict(c.to_dict())
        assert restored.location_id == c.location_id
        assert restored.location == c.location


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

class TestMigrations:
    def _make_legacy_v0_data(self) -> dict:
        """Build a minimal v0 save dict (no schema_version, old Location format)."""
        return {
            "world": {
                "name": "Aethoria",
                "lore": "Once upon a time...",
                "width": 5,
                "height": 5,
                "year": 1005,
                "grid": [
                    {"name": "Aethoria Capital", "description": "Capital city.", "region_type": "city",
                     "x": 2, "y": 2},
                ],
                "event_log": [],
                "active_adventures": [],
                "completed_adventures": [],
            },
            "characters": [
                {"name": "Alice", "age": 30, "gender": "Female", "race": "Human", "job": "Warrior",
                 "location": "Aethoria Capital"},
            ],
            "events_per_year": 8,
            "adventure_steps_per_year": 3,
            "locale": "en",
            "rng_state": "None",
            "history": [],
        }

    def test_apply_migrations_adds_schema_version(self):
        data = self._make_legacy_v0_data()
        result = apply_migrations(data)
        assert result["schema_version"] == CURRENT_VERSION

    def test_migrate_v1_to_v2_adds_location_id_to_characters(self):
        data = self._make_legacy_v0_data()
        data["schema_version"] = 1
        result = migrate_v1_to_v2(data)
        char = result["characters"][0]
        assert "location_id" in char
        assert char["location_id"] == "aethoria_capital"

    def test_migrate_v1_to_v2_adds_state_values_to_locations(self):
        data = self._make_legacy_v0_data()
        data["schema_version"] = 1
        result = migrate_v1_to_v2(data)
        loc = result["world"]["grid"][0]
        assert "id" in loc
        assert loc["id"] == "aethoria_capital"
        assert "canonical_name" in loc
        assert "prosperity" in loc
        assert "safety" in loc
        assert "danger" in loc

    def test_migrate_v0_to_v1_stamps_version(self):
        data = {"foo": "bar"}
        result = migrate_v0_to_v1(data)
        assert result["schema_version"] == 1

    def test_apply_migrations_idempotent_on_current_version(self):
        data = self._make_legacy_v0_data()
        data["schema_version"] = CURRENT_VERSION
        # Add location_id to characters so migration is satisfied
        data["characters"][0]["location_id"] = "aethoria_capital"
        result = apply_migrations(data)
        assert result["schema_version"] == CURRENT_VERSION
        # Character should be unchanged
        assert result["characters"][0]["location_id"] == "aethoria_capital"

    def test_full_migration_chain_v0_to_current(self):
        data = self._make_legacy_v0_data()
        result = apply_migrations(data)
        assert result["schema_version"] == CURRENT_VERSION
        # Check location_id on character
        assert result["characters"][0]["location_id"] == "aethoria_capital"
        # Check state values on location
        loc = result["world"]["grid"][0]
        assert isinstance(loc["prosperity"], int)
        assert 0 <= loc["prosperity"] <= 100

    def test_migration_preserves_existing_location_id(self):
        """If a character already has location_id in v1, migration must not overwrite it."""
        data = self._make_legacy_v0_data()
        data["schema_version"] = 1
        data["characters"][0]["location_id"] = "existing_custom_id"
        result = migrate_v1_to_v2(data)
        assert result["characters"][0]["location_id"] == "existing_custom_id"

"""Tests for world_data.py data integrity."""

from world_data import (
    ALL_SKILLS,
    BATTLE_OUTCOMES_LOSE,
    BATTLE_OUTCOMES_WIN,
    DEFAULT_LOCATIONS,
    DISCOVERY_ITEMS,
    JOBS,
    JOURNEY_EVENTS,
    NAME_TO_LOCATION_ID,
    RACES,
    SKILLS,
)


class TestRaces:
    VALID_STATS = {"strength", "intelligence", "dexterity", "wisdom", "charisma", "constitution"}

    def test_all_races_have_six_stat_bonuses(self):
        for name, _desc, bonuses in RACES:
            assert set(bonuses.keys()) == self.VALID_STATS, f"{name} has unexpected stat keys"

    def test_race_names_unique(self):
        names = [name for name, _, _ in RACES]
        assert len(names) == len(set(names))

    def test_race_bonuses_are_integers(self):
        for name, _desc, bonuses in RACES:
            for stat, val in bonuses.items():
                assert isinstance(val, int), f"{name}.{stat} is not int"


class TestJobs:
    def test_job_names_unique(self):
        names = [name for name, _, _ in JOBS]
        assert len(names) == len(set(names))

    def test_each_job_has_skills(self):
        for name, _desc, skills in JOBS:
            assert len(skills) > 0, f"{name} has no skills"

    def test_job_skills_exist_in_all_skills(self):
        for name, _desc, skills in JOBS:
            for skill in skills:
                assert skill in ALL_SKILLS, f"{name} skill {skill!r} not in ALL_SKILLS"


class TestSkills:
    def test_no_duplicate_skills(self):
        assert len(ALL_SKILLS) == len(set(ALL_SKILLS))

    def test_categories_non_empty(self):
        for category, skills in SKILLS.items():
            assert len(skills) > 0, f"Category {category!r} is empty"


class TestLocations:
    VALID_REGION_TYPES = {"city", "village", "forest", "dungeon", "mountain", "plains", "sea"}

    def test_location_names_unique(self):
        names = [entry[1] for entry in DEFAULT_LOCATIONS]
        assert len(names) == len(set(names))

    def test_location_ids_unique(self):
        ids = [entry[0] for entry in DEFAULT_LOCATIONS]
        assert len(ids) == len(set(ids))

    def test_coordinates_unique(self):
        coords = [(entry[4], entry[5]) for entry in DEFAULT_LOCATIONS]
        assert len(coords) == len(set(coords))

    def test_valid_region_types(self):
        for loc_id, name, _desc, rtype, _x, _y in DEFAULT_LOCATIONS:
            assert rtype in self.VALID_REGION_TYPES, f"{name} has invalid region_type {rtype!r}"

    def test_coordinates_within_5x5_grid(self):
        for loc_id, name, _desc, _rtype, x, y in DEFAULT_LOCATIONS:
            assert 0 <= x < 5, f"{name} x={x} out of range"
            assert 0 <= y < 5, f"{name} y={y} out of range"

    def test_25_locations_for_5x5_grid(self):
        assert len(DEFAULT_LOCATIONS) == 25

    def test_name_to_location_id_mapping(self):
        assert len(NAME_TO_LOCATION_ID) == 25
        for entry in DEFAULT_LOCATIONS:
            loc_id, name = entry[0], entry[1]
            assert NAME_TO_LOCATION_ID[name] == loc_id

    def test_location_ids_follow_naming_convention(self):
        for loc_id, name, *_ in DEFAULT_LOCATIONS:
            assert loc_id.startswith("loc_"), f"{loc_id} doesn't start with 'loc_'"


class TestFlavorData:
    def test_discovery_items_non_empty(self):
        assert len(DISCOVERY_ITEMS) > 0

    def test_battle_outcomes_non_empty(self):
        assert len(BATTLE_OUTCOMES_WIN) > 0
        assert len(BATTLE_OUTCOMES_LOSE) > 0

    def test_journey_events_non_empty(self):
        assert len(JOURNEY_EVENTS) > 0

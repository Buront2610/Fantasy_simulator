"""Safety invariant tests for location and event references."""

from pathlib import Path
import re

import pytest

from character import Character
from events import WorldEventRecord
from world import World


@pytest.fixture
def world_fixture() -> World:
    world = World()
    world.add_character(Character("Aldric", 25, "Male", "Human", "Warrior", location_id="loc_aethoria_capital"))
    world.add_character(Character("Lyra", 22, "Female", "Elf", "Mage", location_id="loc_thornwood"))
    world.record_event(WorldEventRecord(kind="battle", year=1001, location_id="loc_aethoria_capital"))
    world.record_event(WorldEventRecord(kind="journey", year=1001, location_id="invalid_location"))
    return world


def test_si1_all_characters_have_valid_location_id(world_fixture: World):
    for char in world_fixture.characters:
        assert world_fixture.get_location_by_id(char.location_id) is not None


def test_si2_location_lookup_never_returns_none_for_character(world_fixture: World):
    for char in world_fixture.characters:
        location = world_fixture.get_location_by_id(char.location_id)
        assert location is not None


def test_si3_world_event_records_location_id_is_valid_or_none(world_fixture: World):
    valid_ids = {loc.id for loc in world_fixture.grid.values()}
    for record in world_fixture.event_records:
        if record.location_id is not None:
            assert record.location_id in valid_ids


def test_si10_location_state_values_stay_in_bounds(world_fixture: World):
    for location in world_fixture.grid.values():
        for attr in (
            "prosperity",
            "safety",
            "mood",
            "danger",
            "traffic",
            "rumor_heat",
            "road_condition",
        ):
            value = getattr(location, attr)
            assert 0 <= value <= 100, f"{location.id}.{attr} out of bounds: {value}"


def test_phase1_no_legacy_character_location_references():
    source_files = [
        Path("adventure.py"),
        Path("character.py"),
        Path("events.py"),
        Path("main.py"),
        Path("save_load.py"),
        Path("screens.py"),
        Path("simulator.py"),
        Path("world.py"),
    ]
    pattern = re.compile(r"character\.location\b")
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        assert pattern.search(text) is None, f"Legacy location reference found in {path}"

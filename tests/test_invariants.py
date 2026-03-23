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


def test_si4_schema_version_always_present_in_save(tmp_path):
    """SI-4: schema_version is present in all saved data."""
    import json
    from save_load import save_simulation
    from simulator import Simulator

    world = World()
    world.add_character(Character("Test", 25, "Male", "Human", "Warrior"))
    sim = Simulator(world)
    path = str(tmp_path / "si4_test.json")
    assert save_simulation(sim, path) is True
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    assert "schema_version" in data, "Save data must contain schema_version"
    assert isinstance(data["schema_version"], int)
    assert data["schema_version"] >= 1


def test_si5_dead_chars_not_in_active_adventures(world_fixture: World):
    """SI-5: Dead characters should not have active adventures."""
    from adventure import create_adventure_run
    from events import EventSystem
    import random

    rng = random.Random(42)
    char = world_fixture.characters[0]
    run = create_adventure_run(char, world_fixture, rng=rng, id_rng=rng)
    char.active_adventure_id = run.adventure_id
    world_fixture.add_adventure(run)

    # Kill the character through event_death
    es = EventSystem()
    es.event_death(char, world_fixture, rng=rng)

    # SI-5: dead char must not be in active adventures
    assert char.active_adventure_id is None
    active_char_ids = {r.character_id for r in world_fixture.active_adventures}
    assert char.char_id not in active_char_ids, "Dead character still in active adventures"


def test_phase1_no_legacy_character_location_references():
    project_root = Path(__file__).resolve().parents[1]
    source_files = [
        project_root / "adventure.py",
        project_root / "character.py",
        project_root / "events.py",
        project_root / "main.py",
        project_root / "save_load.py",
        project_root / "screens.py",
        project_root / "simulator.py",
        project_root / "world.py",
    ]
    pattern = re.compile(r"\.location\b")
    for path in source_files:
        text = path.read_text(encoding="utf-8")
        assert pattern.search(text) is None, f"Legacy location reference found in {path}"

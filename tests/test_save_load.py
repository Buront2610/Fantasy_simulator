"""
tests/test_save_load.py - Unit tests for save/load helpers.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json

import pytest

from character import Character
from character_creator import CharacterCreator
from save_load import load_simulation, save_simulation
from simulator import Simulator
from world import World


def _make_world(n_chars: int = 3) -> World:
    world = World()
    creator = CharacterCreator()
    import random
    rng = random.Random(42)
    for i in range(n_chars):
        char = creator.create_random(rng=rng)
        world.add_character(char, rng=rng)
    return world


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
        assert "history" in data

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

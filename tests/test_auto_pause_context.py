"""Tests for enhanced auto-pause context payload."""

from fantasy_simulator.character import Character
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


def test_advance_until_pause_returns_context_and_supplemental_keys():
    world = World()
    char = Character("Aldric", 20, "Male", "Human", "Warrior", location_id="loc_aethoria_capital")
    char.injury_status = "dying"
    world.add_character(char)
    sim = Simulator(world, events_per_year=0, seed=1)

    result = sim.advance_until_pause(max_years=1)

    assert "pause_context" in result
    assert "supplemental_reasons" in result
    assert result["pause_reason"].startswith("dying")

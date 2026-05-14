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
    assert "pause_subreasons" in result
    assert "recommended_actions" in result
    assert result["pause_reason"].startswith("dying")
    assert result["pause_subreasons"][0]["key"] == "actor_in_danger"
    assert result["recommended_actions"][0]["key"] == "inspect_character"
    assert result["recommended_actions"][0]["character"] == "Aldric"


def test_condition_worsened_favorite_pause_context_names_character_and_location():
    world = World()
    char = Character("Mira", 24, "Female", "Human", "Ranger", location_id="loc_aethoria_capital")
    char.favorite = True
    world.add_character(char)
    sim = Simulator(world, events_per_year=0, seed=1)
    sim._favorites_worsened_this_year.add(char.char_id)

    assert sim._check_pause_conditions() == "condition_worsened_favorite"
    assert sim._pause_context_for_reason("condition_worsened_favorite") == {
        "character": "Mira",
        "location": "Aethoria Capital",
    }
    assert sim._pause_subreasons_for_reason("condition_worsened_favorite")[0]["key"] == (
        "watched_condition_worsened"
    )
    assert sim._pause_recommendations_for_reason("condition_worsened_favorite")[0]["key"] == "inspect_character"

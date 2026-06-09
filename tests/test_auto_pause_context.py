"""Tests for enhanced auto-pause context payload."""

from fantasy_simulator.character import Character
from fantasy_simulator.adventure import AdventureChoice, AdventureRun
from fantasy_simulator.event_models import WorldEventRecord
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
    assert result["pause_subreasons"][0]["character_id"] == char.char_id
    assert result["pause_subreasons"][0]["location_id"] == "loc_aethoria_capital"
    assert result["recommended_actions"][0]["key"] == "inspect_character"
    assert result["recommended_actions"][0]["character_id"] == char.char_id
    assert result["recommended_actions"][0]["location_id"] == "loc_aethoria_capital"
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
        "character_id": char.char_id,
        "character": "Mira",
        "location_id": "loc_aethoria_capital",
        "location": "Aethoria Capital",
    }
    subreason = sim._pause_subreasons_for_reason("condition_worsened_favorite")[0]
    assert subreason["key"] == "watched_condition_worsened"
    assert subreason["character_id"] == char.char_id
    assert subreason["location_id"] == "loc_aethoria_capital"
    recommendation = sim._pause_recommendations_for_reason("condition_worsened_favorite")[0]
    assert recommendation["key"] == "inspect_character"
    assert recommendation["character_id"] == char.char_id
    assert recommendation["location_id"] == "loc_aethoria_capital"


def test_pending_decision_pause_payload_uses_adventure_ids():
    world = World()
    char = Character("Sera", 22, "Female", "Human", "Scout", location_id="loc_aethoria_capital")
    world.add_character(char)
    run = AdventureRun(
        character_id=char.char_id,
        character_name=char.name,
        origin="loc_aethoria_capital",
        destination="loc_thornwood",
        year_started=world.year,
        pending_choice=AdventureChoice(
            prompt="Press on?",
            options=["press_on", "retreat"],
            default_option="retreat",
            context="danger",
        ),
    )
    world.active_adventures.append(run)
    sim = Simulator(world, events_per_year=0, seed=1)

    assert sim._check_pause_conditions() == "pending_decision"
    context = sim._pause_context_for_reason("pending_decision")
    assert context["character_id"] == char.char_id
    assert context["location_id"] == "loc_thornwood"
    subreason = sim._pause_subreasons_for_reason("pending_decision")[0]
    recommendation = sim._pause_recommendations_for_reason("pending_decision")[0]
    assert subreason["key"] == "adventure_needs_decision"
    assert subreason["character_id"] == char.char_id
    assert subreason["location_id"] == "loc_thornwood"
    assert recommendation["key"] == "review_pending_adventure"
    assert recommendation["character_id"] == char.char_id
    assert recommendation["location_id"] == "loc_thornwood"


def test_world_change_notification_pause_payload_points_to_dashboard_and_location():
    world = World()
    record = WorldEventRecord(
        record_id="evt_route_blocked",
        kind="route_blocked",
        year=world.year,
        month=1,
        location_id="loc_aethoria_capital",
        severity=2,
        tags=["world_change", "location:loc_aethoria_capital"],
        render_params={"route_id": "route_capital_thornwood"},
        description="The capital road was blocked.",
    )
    sim = Simulator(world, events_per_year=0, seed=1)
    sim.pending_notifications.append(record)

    assert sim._check_pause_conditions() == "world_change_notification"
    context = sim._pause_context_for_reason("world_change_notification")
    subreason = sim._pause_subreasons_for_reason("world_change_notification")[0]
    recommendation = sim._pause_recommendations_for_reason("world_change_notification")[0]

    assert context["record_id"] == "evt_route_blocked"
    assert context["event_kind"] == "route_blocked"
    assert context["location_id"] == "loc_aethoria_capital"
    assert context["target_type"] == "route"
    assert context["target_id"] == "route_capital_thornwood"
    assert subreason["key"] == "world_change_notification"
    assert subreason["location_id"] == "loc_aethoria_capital"
    assert subreason["record_id"] == "evt_route_blocked"
    assert subreason["target_type"] == "route"
    assert subreason["target_id"] == "route_capital_thornwood"
    assert recommendation["key"] == "review_world_dashboard"
    assert recommendation["record_id"] == "evt_route_blocked"
    assert recommendation["target_type"] == "route"
    assert recommendation["target_id"] == "route_capital_thornwood"


def test_years_elapsed_pause_payload_is_stable_and_recommendations_are_capped():
    world = World()
    char = Character("Dain", 33, "Male", "Human", "Guard", location_id="loc_aethoria_capital")
    char.injury_status = "dying"
    char.favorite = True
    world.add_character(char)
    sim = Simulator(world, events_per_year=0, seed=1)
    sim._favorites_worsened_this_year.add(char.char_id)

    subreason = sim._pause_subreasons_for_reason("years_elapsed")[0]
    recommendation = sim._pause_recommendations_for_reason("years_elapsed")[0]
    combined = sim._pause_recommendations_for_reasons(
        "dying_favorite",
        ["condition_worsened_favorite", "years_elapsed"],
    )

    assert subreason == {
        "key": "auto_window_elapsed",
        "character_id": "",
        "character": "",
        "location_id": "",
        "location": "",
        "record_id": "",
        "event_kind": "",
        "target_type": "",
        "target_id": "",
    }
    assert recommendation == {
        "key": "review_recent_events",
        "character_id": "",
        "character": "",
        "location_id": "",
        "location": "",
        "record_id": "",
        "event_kind": "",
        "target_type": "",
        "target_id": "",
    }
    assert len(combined) <= 3
    identities = {
        (item["key"], item["character_id"], item["location_id"], item["record_id"], item["target_id"])
        for item in combined
    }
    assert len(identities) == len(combined)

"""Real edge timing, physical presence, topology changes and atomic itinerary recovery."""

from copy import deepcopy

import pytest

from fantasy_simulator.adventure import AdventureRun
from fantasy_simulator.adventure.itinerary import AdventureItinerary, TravelLeg
from fantasy_simulator.adventure.objective import AdventureObjective
from fantasy_simulator.adventure.routing import capture_travel_network, shortest_itinerary
from fantasy_simulator.character import Character
from fantasy_simulator.character_model.death_resolution import mark_character_dead
from fantasy_simulator.simulation import Simulator
from fantasy_simulator.simulation.adventure_travel import initialize_itinerary
from fantasy_simulator.terrain import RouteEdge
from fantasy_simulator.world import LocationState, World
from fantasy_simulator.world_map.view_models import _alive_counts_by_location


@pytest.fixture
def expedition():
    world = World(_skip_defaults=True, width=4, height=1)
    for index, site in enumerate(("home", "waypoint", "detour", "dungeon")):
        world._register_location(LocationState(
            site, site.title(), "route test", "dungeon" if site == "dungeon" else "village",
            index, 0, 50, 50, 50, 20, 10, 10, 50,
        ))
    world._build_terrain_from_grid()
    world.routes = [RouteEdge("hw", "home", "waypoint"),
                    RouteEdge("wd", "waypoint", "dungeon", distance=2),
                    RouteEdge("wt", "waypoint", "detour", distance=2),
                    RouteEdge("td", "detour", "dungeon", distance=2)]
    hero = Character("Traveler", 25, "Male", "Human", "Warrior", char_id="hero", location_id="home")
    world.add_character(hero)
    sim = Simulator(world, seed=42, adventure_steps_per_year=360)
    run = AdventureRun("hero", "Traveler", "home", "dungeon", world.year, adventure_id="route-test",
                       summary_log=["departure"], objective=AdventureObjective())
    sim._commit_adventure_start(run, [hero])
    return sim, run, hero


def advance_due(sim, run):
    sim.elapsed_days = run.schedule.next_step_tick - 1
    sim._advance_scheduled_adventures()


def edge(sim, route_id):
    return next(route for route in sim.world.routes if route.route_id == route_id)


def test_least_cost_route_respects_weights_and_explicit_empty_graph(expedition):
    sim, run, _ = expedition
    network = capture_travel_network(sim.world)
    assert [leg.route_id for leg in shortest_itinerary(network, "home", "dungeon")] == ["hw", "wd"]
    edge(sim, "wd").distance = 8
    path = shortest_itinerary(capture_travel_network(sim.world), "home", "dungeon")
    assert [leg.route_id for leg in path] == ["hw", "wt", "td"]
    sim.world.routes = []
    sim.world._route_graph_explicit = True
    assert shortest_itinerary(capture_travel_network(sim.world), "home", "dungeon") is None


def test_waypoints_take_edge_time_and_preserve_residence(expedition):
    sim, run, hero = expedition
    assert run.itinerary.active_leg.route_id == "hw"
    assert run.schedule.next_step_tick == 2
    assert hero.residence_location_id == "home"
    assert sim.world.get_characters_at_location("home") == []
    assert _alive_counts_by_location(sim.world) == {}
    advance_due(sim, run)
    assert run.state == "traveling"
    assert hero.location_id == run.itinerary.current_site_id == "waypoint"
    assert run.itinerary.active_leg.route_id == "wd"
    assert run.schedule.next_step_tick == 4
    assert sim.world.character_presence_location_id(hero) is None
    assert sim.world.event_records[-1].location_id == "waypoint"
    advance_due(sim, run)
    assert hero.location_id == "dungeon"
    assert sim.world.character_presence_location_id(hero) == "dungeon"
    assert sim.world.get_characters_at_location("dungeon") == [hero]
    assert hero.residence_location_id == run.origin == "home"
    assert _alive_counts_by_location(sim.world) == {"dungeon": 1}


def test_fractional_route_cost_is_rounded_after_calendar_scaling(expedition):
    sim, run, _ = expedition
    edge(sim, "hw").route_type = "trail"
    run.schedule.interval_days = 2
    initialize_itinerary(sim.world, run, 1)
    assert run.itinerary.active_leg.cost == 1.5
    assert run.schedule.next_step_tick == 4  # 1 + ceil(1.5 * 2), not 1 + ceil(1.5) * 2.


def test_mid_leg_blockage_reroutes_from_last_confirmed_site(expedition):
    sim, run, hero = expedition
    advance_due(sim, run)
    edge(sim, "wd").blocked = True
    advance_due(sim, run)
    assert hero.location_id == "waypoint"
    assert run.itinerary.active_leg.route_id == "wt"
    assert sim.world.event_records[-1].kind == "adventure_route_blocked"
    assert sim.world.event_records[-1].location_id == "waypoint"
    advance_due(sim, run)
    assert hero.location_id == "detour"
    advance_due(sim, run)
    assert hero.location_id == "dungeon"


def test_unreachable_destination_returns_over_real_route(expedition):
    sim, run, hero = expedition
    advance_due(sim, run)
    edge(sim, "wd").blocked = edge(sim, "wt").blocked = True
    advance_due(sim, run)
    assert run.state == "returning"
    assert run.itinerary.active_leg.route_id == "hw"
    assert hero.location_id == "waypoint"
    advance_due(sim, run)
    assert run.is_resolved and hero.location_id == "home"
    assert hero.active_adventure_id is None
    destination = sim.world.get_location_by_id("dungeon")
    assert not destination.visited
    assert destination.exploration_progress == 0
    assert destination.live_traces == []


def test_disconnected_return_waits_without_log_spam_and_resumes_after_reload(expedition):
    sim, run, hero = expedition
    advance_due(sim, run)
    for route in sim.world.routes:
        route.blocked = True
    advance_due(sim, run)
    assert run.state == "returning" and run.itinerary.active_leg is None
    assert sim.world.character_presence_location_id(hero) == "waypoint"
    count = len(sim.world.event_records)
    advance_due(sim, run)
    assert len(sim.world.event_records) == count
    loaded = Simulator.from_dict(deepcopy(sim.to_dict()))
    restored = loaded.world.get_adventure_by_id(run.adventure_id)
    assert loaded.to_dict() == sim.to_dict()
    edge(loaded, "hw").blocked = False
    advance_due(loaded, restored)
    assert restored.itinerary.active_leg.route_id == "hw"
    advance_due(loaded, restored)
    assert restored.is_resolved
    assert loaded.world.get_character_by_id(hero.char_id).location_id == "home"


def test_failure_at_waypoint_restores_positions_routes_supplies_and_retry(expedition, monkeypatch):
    sim, run, hero = expedition
    sim.elapsed_days = 1
    before = deepcopy(sim.to_dict())
    record = sim._record_adventure_step_result

    def fail(*args):
        record(*args)
        raise RuntimeError("waypoint record failure")

    with monkeypatch.context() as patch:
        patch.setattr(sim, "_record_adventure_step_result", fail)
        with pytest.raises(RuntimeError, match="waypoint record"):
            sim._advance_scheduled_adventures()
    assert sim.to_dict() == before
    assert hero.location_id == "home"
    control = Simulator.from_dict(deepcopy(before))
    sim._advance_scheduled_adventures()
    control._advance_scheduled_adventures()
    assert sim.to_dict() == control.to_dict()


def test_party_death_in_transit_does_not_teleport_survivor_home(expedition):
    sim, run, hero = expedition
    companion = Character("Companion", 25, "Male", "Human", "Warrior", char_id="companion", location_id="home",
                          residence_location_id="home", active_adventure_id=run.adventure_id)
    sim.world.add_character(companion)
    run.member_ids.append(companion.char_id)
    advance_due(sim, run)
    mark_character_dead(hero, sim.world)
    assert run.is_resolved
    assert companion.location_id == "waypoint"
    assert companion.residence_location_id == "home"
    assert companion.active_adventure_id is None
    assert sim.world.get_characters_at_location("waypoint") == [companion]
    assert sim.world.get_characters_at_location("home") == []
    sim._apply_world_memory(run)
    assert sim.world.get_location_by_id("waypoint").memorial_ids
    assert sim.world.get_location_by_id("dungeon").memorial_ids == []
    assert sim.world.get_location_by_id("dungeon").exploration_progress == 0


def test_mid_transit_save_preserves_position_and_remaining_time(expedition):
    sim, run, hero = expedition
    advance_due(sim, run)
    sim.elapsed_days = 2
    loaded = Simulator.from_dict(deepcopy(sim.to_dict()))
    restored = loaded.world.get_adventure_by_id(run.adventure_id)
    assert restored.itinerary.to_dict() == run.itinerary.to_dict()
    assert restored.schedule.next_step_tick == 4
    assert loaded.world.character_presence_location_id(loaded.world.get_character_by_id(hero.char_id)) is None
    advance_due(sim, run)
    advance_due(loaded, restored)
    assert sim.to_dict() == loaded.to_dict()


def test_disconnected_saved_itinerary_is_rejected():
    payload = AdventureItinerary("home", [TravelLeg("elsewhere", "destination", 1)]).to_dict()
    with pytest.raises(ValueError, match="Disconnected"):
        AdventureItinerary.from_dict(payload)


def test_old_adventure_payload_has_no_invented_itinerary(expedition):
    _, run, _ = expedition
    payload = run.to_dict()
    payload.pop("itinerary")
    restored = AdventureRun.from_dict(payload)
    assert restored.itinerary is None


def test_loading_rejects_inconsistent_physical_position(expedition):
    sim, _, _ = expedition
    payload = sim.to_dict()
    payload["characters"][0]["location_id"] = "detour"
    with pytest.raises(ValueError, match="position conflicts"):
        Simulator.from_dict(payload)

"""Physical travel on the adventure draft; live state is committed by its caller."""

from typing import Any
from math import ceil

from ..adventure.itinerary import AdventureItinerary
from ..adventure.schedule import PACE_DURATION
from ..adventure.results import AdventureFactKind, AdventureStepResult, step_fact_result
from ..adventure.routing import capture_travel_network, leg_is_passable, shortest_itinerary


def initialize_itinerary(world: Any, run: Any, tick: int) -> None:
    network = capture_travel_network(world)
    path = shortest_itinerary(network, run.origin, run.destination)
    if path is None:
        raise ValueError("Adventure destination is no longer reachable")
    run.itinerary = AdventureItinerary(run.origin, visited_destination=run.origin == run.destination)
    interval = run.schedule.interval_days
    duration = 2 * sum(ceil(leg.cost * interval) for leg in path) + 4 * interval
    run.schedule.deadline_tick = tick + duration
    run.schedule.initial_provisions = run.schedule.provisions = duration * len(run.member_ids)
    plan_departure(network, run, tick)


def arrive_if_due(world: Any, run: Any, tick: int) -> bool:
    itinerary = run.itinerary
    if itinerary is None or itinerary.active_leg is None:
        return False
    if tick < itinerary.arrival_tick:
        raise ValueError("Cannot apply a travel arrival before its scheduled day")
    blocked = not leg_is_passable(world.travel_network, itinerary.active_leg)
    if not blocked:
        itinerary.current_site_id = itinerary.active_leg.destination
        itinerary.visited_destination |= itinerary.current_site_id == run.destination
        for member_id in run.member_ids:
            world.get_character_by_id(member_id).location_id = itinerary.current_site_id
    itinerary.active_leg = None
    itinerary.departure_tick = itinerary.arrival_tick = None
    itinerary.remaining_legs = []
    return blocked


def travel_step(world: Any, run: Any, *, blocked: bool = False) -> AdventureStepResult | None:
    itinerary = run.itinerary
    if itinerary is None or run.state not in ("traveling", "returning"):
        return None
    target = run.origin if run.state == "returning" else run.destination
    if itinerary.current_site_id == target and not blocked:
        itinerary.waiting_for_route = False
        return None
    path = shortest_itinerary(world.travel_network, itinerary.current_site_id, target)
    previously_waiting = itinerary.waiting_for_route
    itinerary.waiting_for_route = path is None
    if path is None and run.state == "traveling":
        run.state = "returning"
    if path is None and previously_waiting and not blocked:
        return AdventureStepResult(run.adventure_id, run.state)
    kind: AdventureFactKind = "adventure_route_blocked" if blocked or path is None else "adventure_travel"
    run.steps_taken += 1
    result = step_fact_result(
        run, kind, f"summary_{kind}",
        {"name": run.character_name, "location": world.location_name(itinerary.current_site_id)},
        location_id=itinerary.current_site_id,
    )
    run._record(result.facts[0].description, result.facts[0].description)
    return result


def plan_departure(network: Any, run: Any, tick: int) -> None:
    itinerary = run.itinerary
    if itinerary is None or run.state not in ("traveling", "returning"):
        return
    target = run.origin if run.state == "returning" else run.destination
    path = shortest_itinerary(network, itinerary.current_site_id, target)
    # A disconnected return retries daily without fabricating an edge or teleporting.
    if not path:
        if path == []:
            itinerary.waiting_for_route = False
        itinerary.remaining_legs = []
        run.schedule.next_step_tick = tick + 1
        return
    itinerary.active_leg, itinerary.remaining_legs = path[0], path[1:]
    itinerary.waiting_for_route = False
    itinerary.departure_tick = tick
    pace = PACE_DURATION[run.objective.pace] if run.objective is not None else 1.0
    itinerary.arrival_tick = tick + ceil(path[0].cost * run.schedule.interval_days * pace)
    run.schedule.next_step_tick = itinerary.arrival_tick

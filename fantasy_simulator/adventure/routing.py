"""Snapshot the existing travel topology and choose deterministic least-cost paths."""

from heapq import heappop, heappush
from typing import Any

from .itinerary import TravelLeg


def capture_travel_network(world: Any) -> dict[str, tuple[TravelLeg, ...]]:
    network = {}
    for location in world.grid.values():
        edges = []
        routes = world.get_routes_for_site(location.id)
        for neighbor in world.get_travel_neighboring_locations(location.id):
            route = next((edge for edge in routes if not edge.blocked and edge.other_end(location.id) == neighbor.id),
                         None)
            cost = route.distance * route.base_cost if route else 1.0
            edges.append(TravelLeg(location.id, neighbor.id, cost, route.route_id if route else None))
        network[location.id] = tuple(sorted(edges, key=lambda edge: (edge.destination, edge.route_id or "")))
    return network


def shortest_itinerary(network: dict[str, tuple[TravelLeg, ...]], origin: str,
                       destination: str) -> list[TravelLeg] | None:
    if origin not in network or destination not in network:
        raise ValueError("Itinerary location is not in the travel network")
    costs = {origin: 0.0}
    previous: dict[str, TravelLeg] = {}
    queue = [(0.0, origin)]
    while queue:
        cost, site = heappop(queue)
        if cost != costs[site]:
            continue
        if site == destination:
            path = []
            while site != origin:
                leg = previous[site]
                path.append(leg)
                site = leg.origin
            return list(reversed(path))
        for leg in network[site]:
            new_cost = cost + leg.cost
            if new_cost < costs.get(leg.destination, float("inf")):
                costs[leg.destination] = new_cost
                previous[leg.destination] = leg
                heappush(queue, (new_cost, leg.destination))
    return None


def leg_is_passable(network: dict[str, tuple[TravelLeg, ...]], leg: TravelLeg) -> bool:
    return any(edge.destination == leg.destination and edge.route_id == leg.route_id
               for edge in network.get(leg.origin, ()))


def validate_itinerary_references(world: Any, run: Any, *, include_members: bool = True) -> None:
    if run.itinerary is None or run.is_resolved:
        return
    itinerary = run.itinerary
    locations = {itinerary.current_site_id}
    legs = [*itinerary.remaining_legs, *([itinerary.active_leg] if itinerary.active_leg else [])]
    for leg in legs:
        locations.update((leg.origin, leg.destination))
    if any(world.get_location_by_id(location_id) is None for location_id in locations):
        raise ValueError("Itinerary refers to an unknown location")
    if not include_members:
        return
    for member_id in run.member_ids:
        member = world.get_character_by_id(member_id)
        if member is None or member.location_id != itinerary.current_site_id:
            raise ValueError("Adventure member position conflicts with itinerary")

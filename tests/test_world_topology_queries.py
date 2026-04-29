from __future__ import annotations

from dataclasses import dataclass

import pytest

from fantasy_simulator.terrain import RouteEdge
from fantasy_simulator.world_topology_queries import (
    propagation_neighboring_locations,
    reachable_location_ids,
    travel_neighboring_locations,
)


@dataclass
class _Loc:
    id: str
    x: int
    y: int


def test_travel_neighbors_respect_explicit_empty_route_graph() -> None:
    loc_a = _Loc("a", 0, 0)
    loc_b = _Loc("b", 1, 0)
    index = {"a": loc_a, "b": loc_b}
    grid = {(0, 0): loc_a, (1, 0): loc_b}

    neighbors = travel_neighboring_locations(
        "a",
        location_index=index,
        grid=grid,
        routes=[],
        route_graph_explicit=True,
        get_routes_for_site=lambda _location_id: [],
    )

    assert neighbors == []


def test_propagation_neighbors_can_include_blocked_routes() -> None:
    loc_a = _Loc("a", 0, 0)
    loc_b = _Loc("b", 1, 0)
    index = {"a": loc_a, "b": loc_b}
    grid = {(0, 0): loc_a, (1, 0): loc_b}
    route = RouteEdge("route_a_b", "a", "b", "road", blocked=True)

    blocked = propagation_neighboring_locations(
        "a",
        location_index=index,
        grid=grid,
        routes=[route],
        route_graph_explicit=True,
        get_routes_for_site=lambda _location_id: [route],
    )
    included = propagation_neighboring_locations(
        "a",
        location_index=index,
        grid=grid,
        routes=[route],
        route_graph_explicit=True,
        get_routes_for_site=lambda _location_id: [route],
        include_blocked_routes=True,
    )

    assert blocked == []
    assert included == [loc_b]


def test_reachable_location_ids_walks_travel_neighbors_once() -> None:
    loc_a = _Loc("a", 0, 0)
    loc_b = _Loc("b", 1, 0)
    loc_c = _Loc("c", 2, 0)
    index = {"a": loc_a, "b": loc_b, "c": loc_c}
    neighbor_map = {"a": [loc_b], "b": [loc_a, loc_c], "c": [loc_b]}

    assert reachable_location_ids(
        "a",
        location_index=index,
        get_travel_neighbors=lambda location_id: neighbor_map[location_id],
    ) == ["b", "c"]


def test_propagation_neighbors_reject_unknown_mode() -> None:
    loc_a = _Loc("a", 0, 0)

    with pytest.raises(ValueError, match="Unsupported propagation topology mode"):
        propagation_neighboring_locations(
            "a",
            location_index={"a": loc_a},
            grid={(0, 0): loc_a},
            routes=[],
            route_graph_explicit=False,
            get_routes_for_site=lambda _location_id: [],
            topology_mode="bogus",
        )

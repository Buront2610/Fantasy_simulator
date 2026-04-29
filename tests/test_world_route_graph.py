from __future__ import annotations

from fantasy_simulator.terrain import RouteEdge, Site
from fantasy_simulator.world_route_graph import RouteCollection, rebuild_route_index, replace_routes, routes_for_site


def test_rebuild_route_index_indexes_both_endpoints_and_attaches_observer() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    route = RouteEdge("route_1", "loc_one", "loc_two", "road")
    route_index = rebuild_route_index(
        sites=[
            Site(location_id="loc_one", x=0, y=0, site_type="city"),
            Site(location_id="loc_two", x=1, y=0, site_type="village"),
        ],
        routes=[route],
        on_change=_notify,
    )

    assert routes_for_site(route_index, "loc_one") == [route]
    assert routes_for_site(route_index, "loc_two") == [route]

    route.blocked = True

    assert notifications == 1


def test_replace_routes_detaches_old_observers_and_wraps_new_collection() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    old_route = RouteEdge("route_old", "loc_one", "loc_two", "road")
    old_route._on_change = _notify
    new_route = RouteEdge("route_new", "loc_two", "loc_three", "road")

    wrapped = replace_routes([old_route], [new_route], on_change=_notify)

    old_route.blocked = True
    wrapped[0].blocked = True

    assert notifications == 1


def test_route_collection_extend_notifies_once_and_attaches_observers() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    first = RouteEdge("route_1", "loc_one", "loc_two", "road")
    second = RouteEdge("route_2", "loc_two", "loc_three", "road")
    routes = RouteCollection(on_change=_notify)

    routes.extend([first, second])
    first.blocked = True

    assert notifications == 2


def test_route_collection_setitem_detaches_replaced_route() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    old_route = RouteEdge("route_old", "loc_one", "loc_two", "road")
    new_route = RouteEdge("route_new", "loc_one", "loc_three", "road")
    routes = RouteCollection([old_route], on_change=_notify)

    routes[0] = new_route
    old_route.blocked = True
    new_route.blocked = True

    assert notifications == 2


def test_route_collection_slice_delete_detaches_removed_routes() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    first = RouteEdge("route_1", "loc_one", "loc_two", "road")
    second = RouteEdge("route_2", "loc_two", "loc_three", "road")
    routes = RouteCollection([first, second], on_change=_notify)

    del routes[:]
    first.blocked = True
    second.blocked = True

    assert routes == []
    assert notifications == 1


def test_route_collection_sort_and_reverse_mark_dirty() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    first = RouteEdge("route_b", "loc_one", "loc_two", "road")
    second = RouteEdge("route_a", "loc_two", "loc_three", "road")
    routes = RouteCollection([first, second], on_change=_notify)

    routes.sort(key=lambda route: route.route_id)
    routes.reverse()

    assert [route.route_id for route in routes] == ["route_b", "route_a"]
    assert notifications == 2

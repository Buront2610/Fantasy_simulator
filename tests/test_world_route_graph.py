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


def test_route_collection_pop_and_clear_detach_removed_routes() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    first = RouteEdge("route_1", "loc_one", "loc_two", "road")
    second = RouteEdge("route_2", "loc_two", "loc_three", "road")
    routes = RouteCollection([first, second], on_change=_notify)

    popped = routes.pop()
    popped.blocked = True
    routes.clear()
    first.blocked = True

    assert popped is second
    assert routes == []
    assert notifications == 2


def test_route_collection_slice_assignment_detaches_removed_routes() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    old_route = RouteEdge("route_old", "loc_one", "loc_two", "road")
    new_route = RouteEdge("route_new", "loc_one", "loc_three", "road")
    routes = RouteCollection([old_route], on_change=_notify)

    routes[:] = [new_route]
    old_route.blocked = True
    new_route.blocked = True

    assert notifications == 2


def test_route_collection_rejects_non_route_edges() -> None:
    routes = RouteCollection()

    for action in (
        lambda: routes.append("bad"),  # type: ignore[arg-type]
        lambda: routes.extend([RouteEdge("route_ok", "a", "b"), "bad"]),  # type: ignore[list-item]
        lambda: routes.insert(0, "bad"),  # type: ignore[arg-type]
        lambda: routes.__iadd__(["bad"]),  # type: ignore[list-item]
        lambda: routes.__setitem__(slice(None), ["bad"]),  # type: ignore[list-item]
    ):
        try:
            action()
        except TypeError as exc:
            assert "RouteEdge" in str(exc)
            continue
        raise AssertionError("Expected RouteCollection to reject non-RouteEdge values")


def test_route_collection_rejects_repetition() -> None:
    routes = RouteCollection([RouteEdge("route_1", "loc_one", "loc_two", "road")])

    try:
        routes *= 2
    except TypeError as exc:
        assert "repetition" in str(exc)
    else:
        raise AssertionError("Expected RouteCollection repetition to fail fast")


def test_route_collection_rejects_route_owned_by_another_active_collection() -> None:
    first_notifications = 0
    second_notifications = 0

    def _notify_first() -> None:
        nonlocal first_notifications
        first_notifications += 1

    def _notify_second() -> None:
        nonlocal second_notifications
        second_notifications += 1

    route = RouteEdge("route_1", "loc_one", "loc_two", "road")
    first = RouteCollection([route], on_change=_notify_first)
    second = RouteCollection(on_change=_notify_second)

    try:
        second.append(route)
    except ValueError as exc:
        assert "shared" in str(exc)
    else:
        raise AssertionError("Expected active RouteEdge sharing to fail fast")

    route.blocked = True
    assert first == [route]
    assert second == []
    assert first_notifications == 1
    assert second_notifications == 0


def test_rebuild_route_index_rejects_route_owned_by_another_active_collection() -> None:
    first_notifications = 0
    second_notifications = 0

    def _notify_first() -> None:
        nonlocal first_notifications
        first_notifications += 1

    def _notify_second() -> None:
        nonlocal second_notifications
        second_notifications += 1

    route = RouteEdge("route_1", "loc_one", "loc_two", "road")
    RouteCollection([route], on_change=_notify_first)

    try:
        rebuild_route_index(
            sites=[
                Site(location_id="loc_one", x=0, y=0, site_type="city"),
                Site(location_id="loc_two", x=1, y=0, site_type="village"),
            ],
            routes=[route],
            on_change=_notify_second,
        )
    except ValueError as exc:
        assert "shared" in str(exc)
    else:
        raise AssertionError("Expected route index rebuild to reject a foreign active owner")

    route.blocked = True
    assert first_notifications == 1
    assert second_notifications == 0


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

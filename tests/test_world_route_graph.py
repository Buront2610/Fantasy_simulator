from __future__ import annotations

from fantasy_simulator.terrain import RouteEdge, Site
from fantasy_simulator.world import World
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


def test_rebuild_route_index_rejects_invalid_plain_iterable_topology() -> None:
    sites = [
        Site(location_id="loc_one", x=0, y=0, site_type="city"),
        Site(location_id="loc_two", x=1, y=0, site_type="village"),
        Site(location_id="loc_three", x=2, y=0, site_type="village"),
    ]

    for routes, message in (
        ([RouteEdge("route_loop", "loc_one", "loc_one", "road")], "self-loop"),
        (
            [
                RouteEdge("route_1", "loc_one", "loc_two", "road"),
                RouteEdge("route_1", "loc_two", "loc_three", "road"),
            ],
            "duplicate route id",
        ),
        (
            [
                RouteEdge("route_1", "loc_one", "loc_two", "road"),
                RouteEdge("route_2", "loc_two", "loc_one", "road"),
            ],
            "duplicate route pair",
        ),
    ):
        try:
            rebuild_route_index(sites=sites, routes=routes, on_change=lambda: None)
        except ValueError as exc:
            assert message in str(exc)
            continue
        raise AssertionError(f"Expected invalid route topology to fail: {message}")


def test_world_route_index_rebuild_rejects_direct_route_identity_mutation() -> None:
    world = World()
    first = world.routes[0]
    second = world.routes[1]

    second.route_id = first.route_id

    try:
        world.get_routes_for_site(second.from_site_id)
    except ValueError as exc:
        assert "duplicate route id" in str(exc)
    else:
        raise AssertionError("Expected direct duplicate route_id mutation to fail during rebuild")


def test_world_route_index_rebuild_rejects_direct_route_self_loop_mutation() -> None:
    world = World()
    route = world.routes[0]

    route.to_site_id = route.from_site_id

    try:
        world.get_routes_for_site(route.from_site_id)
    except ValueError as exc:
        assert "self-loop" in str(exc)
    else:
        raise AssertionError("Expected direct self-loop mutation to fail during rebuild")


def test_replace_routes_preserves_old_observers_when_new_routes_are_invalid() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    old_route = RouteEdge("route_old", "loc_one", "loc_two", "road")
    old_route._on_change = _notify

    try:
        replace_routes([old_route], ["bad"], on_change=_notify)  # type: ignore[list-item]
    except TypeError as exc:
        assert "RouteEdge" in str(exc)
    else:
        raise AssertionError("Expected invalid replacement route to fail")

    old_route.blocked = True

    assert notifications == 1


def test_replace_routes_preserves_old_observers_when_new_route_has_foreign_owner() -> None:
    old_notifications = 0
    foreign_notifications = 0

    def _notify_old() -> None:
        nonlocal old_notifications
        old_notifications += 1

    def _notify_foreign() -> None:
        nonlocal foreign_notifications
        foreign_notifications += 1

    old_route = RouteEdge("route_old", "loc_one", "loc_two", "road")
    old_route._on_change = _notify_old
    foreign_route = RouteEdge("route_foreign", "loc_two", "loc_three", "road")
    RouteCollection([foreign_route], on_change=_notify_foreign)

    try:
        replace_routes([old_route], [foreign_route], on_change=_notify_old)
    except ValueError as exc:
        assert "shared" in str(exc)
    else:
        raise AssertionError("Expected foreign-owned replacement route to fail")

    old_route.blocked = True
    foreign_route.blocked = True

    assert old_notifications == 1
    assert foreign_notifications == 1


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


def test_route_collection_rejects_duplicate_route_ids_during_construction_and_extend() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    first = RouteEdge("route_1", "loc_one", "loc_two", "road")
    duplicate = RouteEdge("route_1", "loc_two", "loc_three", "road")

    try:
        RouteCollection([first, duplicate], on_change=_notify)
    except ValueError as exc:
        assert "duplicate route id" in str(exc)
    else:
        raise AssertionError("Expected duplicate route ids to fail during construction")

    first.blocked = True
    duplicate.blocked = True

    assert notifications == 0

    routes = RouteCollection([first], on_change=_notify)
    try:
        routes.extend([duplicate])
    except ValueError as exc:
        assert "duplicate route id" in str(exc)
    else:
        raise AssertionError("Expected duplicate route ids to fail during extend")

    duplicate.blocked = False

    assert routes == [first]
    assert notifications == 0


def test_route_collection_rejects_self_loop_routes_on_mutation_paths() -> None:
    baseline = RouteEdge("route_1", "loc_one", "loc_two", "road")

    try:
        RouteCollection([RouteEdge("route_self", "loc_one", "loc_one", "road")])
    except ValueError as exc:
        assert "self-loop" in str(exc)
    else:
        raise AssertionError("Expected self-loop route construction to fail")

    for action in (
        lambda routes: routes.append(RouteEdge("route_append", "loc_one", "loc_one", "road")),
        lambda routes: routes.extend([RouteEdge("route_extend", "loc_one", "loc_one", "road")]),
        lambda routes: routes.insert(0, RouteEdge("route_insert", "loc_one", "loc_one", "road")),
        lambda routes: routes.__setitem__(0, RouteEdge("route_setitem", "loc_one", "loc_one", "road")),
        lambda routes: routes.__setitem__(
            slice(None),
            [RouteEdge("route_slice", "loc_one", "loc_one", "road")],
        ),
    ):
        routes = RouteCollection([baseline])
        try:
            action(routes)
        except ValueError as exc:
            assert "self-loop" in str(exc)
            assert routes == [baseline]
            continue
        raise AssertionError("Expected self-loop route mutation to fail")


def test_route_collection_rejects_duplicate_undirected_endpoint_pairs_on_append_insert_and_iadd() -> None:
    first = RouteEdge("route_1", "loc_one", "loc_two", "road")
    routes = RouteCollection([first])

    for action in (
        lambda: routes.append(RouteEdge("route_append", "loc_two", "loc_one", "road")),
        lambda: routes.insert(0, RouteEdge("route_insert", "loc_one", "loc_two", "trail")),
        lambda: routes.__iadd__([RouteEdge("route_iadd", "loc_two", "loc_one", "sea_lane")]),
    ):
        try:
            action()
        except ValueError as exc:
            assert "duplicate route pair" in str(exc)
            continue
        raise AssertionError("Expected duplicate endpoint pair to fail")

    assert routes == [first]


def test_route_collection_rejects_duplicates_from_item_and_slice_assignment() -> None:
    first = RouteEdge("route_1", "loc_one", "loc_two", "road")
    second = RouteEdge("route_2", "loc_three", "loc_four", "road")
    routes = RouteCollection([first, second])

    try:
        routes[0] = RouteEdge("route_2", "loc_five", "loc_six", "road")
    except ValueError as exc:
        assert "duplicate route id" in str(exc)
    else:
        raise AssertionError("Expected duplicate route id assignment to fail")

    try:
        routes[:] = [
            RouteEdge("route_3", "loc_one", "loc_two", "road"),
            RouteEdge("route_4", "loc_two", "loc_one", "trail"),
        ]
    except ValueError as exc:
        assert "duplicate route pair" in str(exc)
    else:
        raise AssertionError("Expected duplicate route pair slice assignment to fail")

    assert routes == [first, second]


def test_route_collection_allows_replacing_slot_with_same_route_identity_fields() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    old_route = RouteEdge("route_1", "loc_one", "loc_two", "road")
    equivalent_route = RouteEdge("route_1", "loc_two", "loc_one", "trail")
    routes = RouteCollection([old_route], on_change=_notify)

    routes[0] = equivalent_route
    old_route.blocked = True
    equivalent_route.blocked = True

    assert routes == [equivalent_route]
    assert notifications == 2


def test_route_collection_init_failure_does_not_attach_partial_observers() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    valid_route = RouteEdge("route_valid", "loc_one", "loc_two", "road")

    try:
        RouteCollection([valid_route, "bad"], on_change=_notify)  # type: ignore[list-item]
    except TypeError as exc:
        assert "RouteEdge" in str(exc)
    else:
        raise AssertionError("Expected invalid route collection construction to fail")

    valid_route.blocked = True

    assert notifications == 0


def test_route_collection_extend_failure_does_not_attach_partial_observers() -> None:
    first_notifications = 0
    second_notifications = 0

    def _notify_first() -> None:
        nonlocal first_notifications
        first_notifications += 1

    def _notify_second() -> None:
        nonlocal second_notifications
        second_notifications += 1

    valid_route = RouteEdge("route_valid", "loc_one", "loc_two", "road")
    foreign_route = RouteEdge("route_foreign", "loc_two", "loc_three", "road")
    RouteCollection([foreign_route], on_change=_notify_second)
    routes = RouteCollection(on_change=_notify_first)

    try:
        routes.extend([valid_route, foreign_route])
    except ValueError as exc:
        assert "shared" in str(exc)
    else:
        raise AssertionError("Expected mixed ownership extend to fail")

    valid_route.blocked = True
    foreign_route.blocked = True

    assert routes == []
    assert first_notifications == 0
    assert second_notifications == 1


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


def test_route_collection_setitem_out_of_range_does_not_attach_observer() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    new_route = RouteEdge("route_new", "loc_one", "loc_three", "road")
    routes = RouteCollection(on_change=_notify)

    try:
        routes[1] = new_route
    except IndexError:
        pass
    else:
        raise AssertionError("Expected out-of-range route assignment to fail")

    new_route.blocked = True

    assert notifications == 0


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


def test_route_collection_extended_slice_assignment_failure_does_not_attach_observers() -> None:
    notifications = 0

    def _notify() -> None:
        nonlocal notifications
        notifications += 1

    first = RouteEdge("route_1", "loc_one", "loc_two", "road")
    second = RouteEdge("route_2", "loc_two", "loc_three", "road")
    new_route = RouteEdge("route_new", "loc_one", "loc_three", "road")
    routes = RouteCollection([first, second], on_change=_notify)

    try:
        routes[::2] = [new_route, RouteEdge("route_extra", "loc_three", "loc_four", "road")]
    except ValueError as exc:
        assert "extended slice" in str(exc)
    else:
        raise AssertionError("Expected extended slice size mismatch to fail")

    new_route.blocked = True

    assert routes == [first, second]
    assert notifications == 0


def test_stale_route_collection_alias_cannot_detach_active_collection_observers() -> None:
    old_notifications = 0
    active_notifications = 0

    def _notify_old() -> None:
        nonlocal old_notifications
        old_notifications += 1

    def _notify_active() -> None:
        nonlocal active_notifications
        active_notifications += 1

    route = RouteEdge("route_1", "loc_one", "loc_two", "road")
    old_routes = RouteCollection([route], on_change=_notify_old)
    active_routes = replace_routes(old_routes, list(old_routes), on_change=_notify_active)

    old_routes.clear()
    route.blocked = True

    assert active_routes == [route]
    assert old_notifications == 1
    assert active_notifications == 1


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

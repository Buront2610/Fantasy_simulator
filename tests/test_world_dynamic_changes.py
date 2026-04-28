from fantasy_simulator.world import World


def test_rename_location_updates_name_index_and_keeps_old_name_as_alias():
    world = World()
    location = world.get_location_by_id("loc_aethoria_capital")

    old_name = world.rename_location("loc_aethoria_capital", "Aethoria March")

    assert old_name == "Aethoria Capital"
    assert location.canonical_name == "Aethoria March"
    assert "Aethoria Capital" in location.aliases
    assert world.get_location_by_name("Aethoria Capital") is None
    assert world.get_location_by_name("Aethoria March") is location


def test_set_location_controlling_faction_returns_previous_value():
    world = World()

    assert world.set_location_controlling_faction("loc_aethoria_capital", "wardens") is None
    assert world.set_location_controlling_faction("loc_aethoria_capital", "dawn_court") == "wardens"
    assert world.get_location_by_id("loc_aethoria_capital").controlling_faction_id == "dawn_court"


def test_set_route_blocked_uses_existing_route_collection_observers():
    world = World()
    route_id = world.routes[0].route_id

    previous = world.set_route_blocked(route_id, True)

    assert previous is False
    assert next(route for route in world.routes if route.route_id == route_id).blocked is True

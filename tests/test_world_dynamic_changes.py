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


def test_rename_location_survives_reports_and_save_load_views():
    world = World()

    world.rename_location("loc_aethoria_capital", "Aethoria March")
    restored = World.from_dict(world.to_dict())

    assert world.location_name("loc_aethoria_capital") == "Aethoria March"
    assert "Aethoria March" in world.location_names
    assert restored.location_name("loc_aethoria_capital") == "Aethoria March"
    assert restored.get_location_by_name("Aethoria March") is not None
    assert restored.get_location_by_name("Aethoria Capital") is None
    assert restored.atlas_layout is not None
    assert restored.get_location_by_id("loc_aethoria_capital").aliases == ["Aethoria Capital"]


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

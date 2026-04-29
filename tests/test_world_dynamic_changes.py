from fantasy_simulator.event_rendering import render_event_record
from fantasy_simulator.i18n import get_locale, set_locale
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


def test_rename_location_rejects_existing_canonical_name_without_mutating_indexes():
    world = World()
    capital = world.get_location_by_id("loc_aethoria_capital")
    silverbrook = world.get_location_by_id("loc_silverbrook")
    assert capital is not None
    assert silverbrook is not None

    try:
        world.rename_location("loc_aethoria_capital", "Silverbrook")
    except ValueError as exc:
        assert "location name already exists" in str(exc)
    else:
        raise AssertionError("Expected duplicate canonical location name to fail fast")

    assert capital.canonical_name == "Aethoria Capital"
    assert silverbrook.canonical_name == "Silverbrook"
    assert world.get_location_by_name("Aethoria Capital") is capital
    assert world.get_location_by_name("Silverbrook") is silverbrook


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


def test_apply_location_rename_change_updates_map_and_records_canonical_event():
    previous_locale = get_locale()
    set_locale("en")
    world = World()

    try:
        record = world.apply_location_rename_change(
            "loc_aethoria_capital",
            "Aethoria March",
            month=2,
            day=3,
        )
    finally:
        set_locale(previous_locale)

    location = world.get_location_by_id("loc_aethoria_capital")
    assert location.canonical_name == "Aethoria March"
    assert world.get_location_by_name("Aethoria March") is location
    assert world.get_location_by_name("Aethoria Capital") is None

    assert record is world.event_records[-1]
    assert record.kind == "location_renamed"
    assert record.year == world.year
    assert record.month == 2
    assert record.day == 3
    assert record.location_id == "loc_aethoria_capital"
    assert record.summary_key == "events.location_renamed.summary"
    assert record.render_params == {
        "location_id": "loc_aethoria_capital",
        "old_name": "Aethoria Capital",
        "new_name": "Aethoria March",
    }
    assert record.impacts == [
        {
            "target_type": "location",
            "target_id": "loc_aethoria_capital",
            "attribute": "canonical_name",
            "old_value": "Aethoria Capital",
            "new_value": "Aethoria March",
        }
    ]
    assert render_event_record(record, locale="en") == "Aethoria Capital was renamed Aethoria March."
    assert render_event_record(record, locale="ja") == "Aethoria Capital は Aethoria March に改名された。"


def test_apply_route_blocked_change_records_block_and_reopen_events():
    previous_locale = get_locale()
    set_locale("en")
    world = World()
    route = world.routes[0]
    route_id = route.route_id
    from_location = world.location_name(route.from_site_id)
    to_location = world.location_name(route.to_site_id)

    try:
        blocked_record = world.apply_route_blocked_change(route_id, True)
        reopened_record = world.apply_route_blocked_change(route_id, False)
    finally:
        set_locale(previous_locale)

    assert next(item for item in world.routes if item.route_id == route_id).blocked is False
    assert blocked_record.kind == "route_blocked"
    assert reopened_record.kind == "route_reopened"
    assert blocked_record.summary_key == "events.route_blocked.summary"
    assert reopened_record.summary_key == "events.route_reopened.summary"
    assert blocked_record.render_params == {
        "route_id": route_id,
        "from_location": from_location,
        "to_location": to_location,
    }
    assert blocked_record.impacts == [
        {
            "target_type": "route",
            "target_id": route_id,
            "attribute": "blocked",
            "old_value": False,
            "new_value": True,
        }
    ]
    assert reopened_record.impacts[0]["old_value"] is True
    assert reopened_record.impacts[0]["new_value"] is False
    assert world.event_records[-2:] == [blocked_record, reopened_record]


def test_apply_controlling_faction_change_updates_location_and_records_event():
    previous_locale = get_locale()
    set_locale("en")
    world = World()

    try:
        first = world.apply_controlling_faction_change("loc_aethoria_capital", "wardens")
        second = world.apply_controlling_faction_change("loc_aethoria_capital", "dawn_court")
    finally:
        set_locale(previous_locale)

    location = world.get_location_by_id("loc_aethoria_capital")
    assert location.controlling_faction_id == "dawn_court"
    assert first.kind == "location_faction_changed"
    assert second.kind == "location_faction_changed"
    assert second.summary_key == "events.location_faction_changed.summary"
    assert second.render_params == {
        "location": "Aethoria Capital",
        "location_id": "loc_aethoria_capital",
        "old_faction": "wardens",
        "new_faction": "dawn_court",
    }
    assert second.impacts == [
        {
            "target_type": "location",
            "target_id": "loc_aethoria_capital",
            "attribute": "controlling_faction_id",
            "old_value": "wardens",
            "new_value": "dawn_court",
        }
    ]
    assert render_event_record(second, locale="en") == (
        "Aethoria Capital changed controlling faction from wardens to dawn_court."
    )


def test_world_change_event_records_survive_world_round_trip():
    previous_locale = get_locale()
    set_locale("en")
    world = World()

    try:
        record = world.apply_location_rename_change("loc_aethoria_capital", "Aethoria March")
    finally:
        set_locale(previous_locale)

    restored = World.from_dict(world.to_dict())
    restored_record = restored.event_records[-1]

    assert restored.location_name("loc_aethoria_capital") == "Aethoria March"
    assert restored_record.to_dict() == record.to_dict()
    assert restored_record.render_params["new_name"] == "Aethoria March"

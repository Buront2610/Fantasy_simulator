from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.observation import build_route_status_projection
from fantasy_simulator.ui.map_renderer import build_map_info
from fantasy_simulator.world import World
from fantasy_simulator.world_location.state import clamp_state


def test_route_status_projection_reports_current_state_without_history() -> None:
    world = World()
    route = world.routes[0]

    projection = build_route_status_projection(
        routes=world.routes,
        event_records=world.event_records,
        route_id=route.route_id,
    )

    assert projection.route_id == route.route_id
    assert projection.from_location_id == route.from_site_id
    assert projection.to_location_id == route.to_site_id
    assert projection.status == "open"
    assert projection.blocked is False
    assert projection.history == ()


def test_route_status_projection_includes_block_and_reopen_history() -> None:
    world = World()
    route = world.routes[0]

    blocked = world.apply_route_blocked_change(route.route_id, True, month=2, day=3)
    reopened = world.apply_route_blocked_change(route.route_id, False, month=2, day=4)

    projection = build_route_status_projection(
        routes=world.routes,
        event_records=world.event_records,
        route_id=route.route_id,
    )

    assert blocked is not None
    assert reopened is not None
    assert projection.status == "open"
    assert projection.blocked is False
    assert [entry.record_id for entry in projection.history] == [blocked.record_id, reopened.record_id]
    assert [entry.kind for entry in projection.history] == ["route_blocked", "route_reopened"]
    assert [entry.blocked for entry in projection.history] == [True, False]
    assert [entry.day for entry in projection.history] == [3, 4]


def test_route_block_and_reopen_apply_endpoint_location_state_pressure_and_map_visibility() -> None:
    previous_locale = get_locale()
    set_locale("en")
    world = World()
    route = world.routes[0]
    from_location = world.get_location_by_id(route.from_site_id)
    to_location = world.get_location_by_id(route.to_site_id)
    assert from_location is not None
    assert to_location is not None
    before_from = (
        from_location.road_condition,
        from_location.traffic,
        from_location.rumor_heat,
        from_location.mood,
        from_location.danger,
        from_location.safety,
    )
    before_to = (
        to_location.road_condition,
        to_location.traffic,
        to_location.rumor_heat,
        to_location.mood,
        to_location.danger,
        to_location.safety,
    )

    try:
        blocked = world.apply_route_blocked_change(route.route_id, True, month=2, day=3)
        reopened = world.apply_route_blocked_change(route.route_id, False, month=2, day=4)
    finally:
        set_locale(previous_locale)

    assert blocked is not None
    assert reopened is not None
    assert (
        from_location.road_condition,
        from_location.traffic,
        from_location.rumor_heat,
        from_location.mood,
        from_location.danger,
        from_location.safety,
    ) == (
        clamp_state(before_from[0] - 3),
        clamp_state(before_from[1] - 2),
        clamp_state(before_from[2] + 13),
        before_from[3],
        clamp_state(before_from[4] + 1),
        clamp_state(before_from[5] + 2),
    )
    assert (
        to_location.road_condition,
        to_location.traffic,
        to_location.rumor_heat,
        to_location.mood,
        to_location.danger,
        to_location.safety,
    ) == (
        clamp_state(before_to[0] - 3),
        clamp_state(before_to[1] - 2),
        clamp_state(before_to[2] + 13),
        before_to[3],
        clamp_state(before_to[4] + 1),
        clamp_state(before_to[5] + 2),
    )
    assert from_location.live_traces[-2]["char_name"] == "world"
    assert "Travel pressure" in from_location.live_traces[-2]["text"]
    assert "Travel flow" in from_location.live_traces[-1]["text"]

    map_info = build_map_info(world)
    from_cell = next(cell for cell in map_info.cells.values() if cell.location_id == route.from_site_id)
    to_cell = next(cell for cell in map_info.cells.values() if cell.location_id == route.to_site_id)
    assert from_cell.traffic_indicator == from_location.traffic_indicator
    assert to_cell.traffic_indicator == to_location.traffic_indicator


def test_route_status_projection_filters_other_routes() -> None:
    world = World()
    first = world.routes[0]
    second = world.routes[1]

    first_record = world.apply_route_blocked_change(first.route_id, True)
    second_record = world.apply_route_blocked_change(second.route_id, True)

    projection = build_route_status_projection(
        routes=world.routes,
        event_records=world.event_records,
        route_id=first.route_id,
    )

    assert first_record is not None
    assert second_record is not None
    assert [entry.record_id for entry in projection.history] == [first_record.record_id]
    assert second_record.record_id not in [entry.record_id for entry in projection.history]


def test_route_status_projection_reads_sparse_impact_route_records() -> None:
    world = World()
    route = world.routes[0]
    record = WorldEventRecord(
        record_id="rec_sparse_route",
        kind="route_blocked",
        year=world.year,
        month=6,
        day=7,
        description="Sparse route closure.",
        tags=[
            f"location:{route.from_site_id}",
            f"location:{route.to_site_id}",
        ],
        impacts=[
            {
                "target_type": "route",
                "target_id": route.route_id,
                "attribute": "blocked",
                "new_value": "blocked",
            }
        ],
    )

    projection = build_route_status_projection(
        routes=world.routes,
        event_records=[record],
        route_id=route.route_id,
    )

    assert [entry.record_id for entry in projection.history] == ["rec_sparse_route"]
    assert projection.history[0].blocked is True
    assert projection.history[0].from_location_id == route.from_site_id
    assert projection.history[0].to_location_id == route.to_site_id

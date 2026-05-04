from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.observation import build_route_status_projection
from fantasy_simulator.world import World


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

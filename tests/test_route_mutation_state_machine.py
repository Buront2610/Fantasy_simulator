from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.ids import RouteId
from fantasy_simulator.terrain import RouteEdge
from fantasy_simulator.world_change import (
    SetRouteBlockedCommand,
    apply_world_change_set,
    build_route_blocked_change_set,
)
from fantasy_simulator.world_change.state_machines import transition_route_blocked_state


def _describe(summary_key: str, _render_params: dict, fallback_description: str) -> str:
    assert summary_key in {"events.route_blocked.summary", "events.route_reopened.summary"}
    return fallback_description


def _location_name(location_id: str) -> str:
    return {"loc_origin": "Origin", "loc_destination": "Destination"}.get(location_id, location_id)


def test_route_block_state_machine_returns_noop_for_same_state() -> None:
    assert transition_route_blocked_state(False, False) is None
    assert transition_route_blocked_state(True, True) is None


def test_route_block_state_machine_distinguishes_block_and_reopen() -> None:
    blocked = transition_route_blocked_state(False, True)
    reopened = transition_route_blocked_state(True, False)

    assert blocked is not None
    assert blocked.old_status == "open"
    assert blocked.new_status == "blocked"
    assert blocked.event_kind == "route_blocked"
    assert reopened is not None
    assert reopened.old_status == "blocked"
    assert reopened.new_status == "open"
    assert reopened.event_kind == "route_reopened"


def test_route_block_changeset_contains_event_and_route_update() -> None:
    route = RouteEdge("route_1", "loc_origin", "loc_destination")
    command = SetRouteBlockedCommand(route_id=RouteId(route.route_id), blocked=True, year=1001, month=2, day=3)

    change_set = build_route_blocked_change_set(
        command,
        routes=[route],
        location_ids={"loc_origin", "loc_destination"},
        location_name=_location_name,
        describe=_describe,
    )

    assert change_set is not None
    assert change_set.route_updates[0].old_blocked is False
    assert change_set.route_updates[0].new_blocked is True
    record = change_set.events[0]
    assert record.kind == "route_blocked"
    assert record.location_id == "loc_origin"
    assert record.render_params["endpoint_location_ids"] == ["loc_origin", "loc_destination"]
    assert record.description == "The route from Origin to Destination was blocked."


def test_route_block_changeset_rejects_unknown_endpoint() -> None:
    route = RouteEdge("route_1", "loc_origin", "loc_missing")
    command = SetRouteBlockedCommand(route_id=RouteId(route.route_id), blocked=True, year=1001)

    try:
        build_route_blocked_change_set(
            command,
            routes=[route],
            location_ids={"loc_origin"},
            location_name=_location_name,
            describe=_describe,
        )
    except ValueError as exc:
        assert "unknown endpoint" in str(exc)
    else:
        raise AssertionError("Expected route endpoint validation to fail")


def test_world_change_reducer_applies_update_and_records_event() -> None:
    route = RouteEdge("route_1", "loc_origin", "loc_destination")
    records: list[WorldEventRecord] = []
    command = SetRouteBlockedCommand(route_id=RouteId(route.route_id), blocked=True, year=1001)
    change_set = build_route_blocked_change_set(
        command,
        routes=[route],
        location_ids={"loc_origin", "loc_destination"},
        location_name=_location_name,
        describe=_describe,
    )
    assert change_set is not None

    stored = apply_world_change_set(
        change_set,
        routes=[route],
        record_event=lambda record: records.append(record) or record,
    )

    assert route.blocked is True
    assert stored == tuple(records)
    assert records[0].kind == "route_blocked"


def test_world_change_reducer_rolls_back_route_update_when_recording_fails() -> None:
    route = RouteEdge("route_1", "loc_origin", "loc_destination")
    command = SetRouteBlockedCommand(route_id=RouteId(route.route_id), blocked=True, year=1001)
    change_set = build_route_blocked_change_set(
        command,
        routes=[route],
        location_ids={"loc_origin", "loc_destination"},
        location_name=_location_name,
        describe=_describe,
    )
    assert change_set is not None

    def _fail_record(_record: WorldEventRecord) -> WorldEventRecord:
        raise ValueError("recording failed")

    try:
        apply_world_change_set(change_set, routes=[route], record_event=_fail_record)
    except ValueError as exc:
        assert "recording failed" in str(exc)
    else:
        raise AssertionError("Expected recording failure to roll back route state")

    assert route.blocked is False

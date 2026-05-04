"""PR-K contract tests for route world-change event records."""

from __future__ import annotations

import json

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.event_rendering import render_event_record
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.terrain import RouteEdge
from fantasy_simulator.world import World


def _assert_route_change_record_contract(
    *,
    world: World,
    route: RouteEdge,
    record: WorldEventRecord,
    expected_kind: str,
    expected_old_value: bool,
    expected_new_value: bool,
) -> None:
    from_location_id = route.from_site_id
    to_location_id = route.to_site_id

    assert record.kind == expected_kind
    assert record.location_id == from_location_id
    assert record.summary_key == f"events.{expected_kind}.summary"
    assert record.description
    assert record.render_params == {
        "route_id": route.route_id,
        "from_location_id": from_location_id,
        "to_location_id": to_location_id,
        "endpoint_location_ids": [from_location_id, to_location_id],
    }
    assert f"location:{from_location_id}" in record.tags
    assert f"location:{to_location_id}" in record.tags
    assert record.impacts == [
        {
            "target_type": "route",
            "target_id": route.route_id,
            "attribute": "blocked",
            "old_value": expected_old_value,
            "new_value": expected_new_value,
        }
    ]

    json.dumps(record.render_params)
    assert WorldEventRecord.from_dict(record.to_dict()).to_dict() == record.to_dict()
    assert render_event_record(record, locale="en", world=world) != record.summary_key


def test_route_block_and_reopen_records_follow_pr_k_event_contract() -> None:
    previous_locale = get_locale()
    set_locale("en")
    world = World()
    route = world.routes[0]

    try:
        blocked_record = world.apply_route_blocked_change(route.route_id, True, month=4, day=5)
        reopened_record = world.apply_route_blocked_change(route.route_id, False, month=4, day=6)
    finally:
        set_locale(previous_locale)

    assert blocked_record is not None
    assert reopened_record is not None
    assert next(item for item in world.routes if item.route_id == route.route_id).blocked is False
    assert world.event_records[-2:] == [blocked_record, reopened_record]

    _assert_route_change_record_contract(
        world=world,
        route=route,
        record=blocked_record,
        expected_kind="route_blocked",
        expected_old_value=False,
        expected_new_value=True,
    )
    _assert_route_change_record_contract(
        world=world,
        route=route,
        record=reopened_record,
        expected_kind="route_reopened",
        expected_old_value=True,
        expected_new_value=False,
    )


def test_route_block_and_reopen_records_are_queryable_from_both_endpoints() -> None:
    previous_locale = get_locale()
    set_locale("en")
    world = World()
    route = world.routes[0]

    try:
        blocked_record = world.apply_route_blocked_change(route.route_id, True, month=7)
        reopened_record = world.apply_route_blocked_change(route.route_id, False, month=7)
    finally:
        set_locale(previous_locale)

    assert blocked_record is not None
    assert reopened_record is not None
    route_records = [blocked_record, reopened_record]
    route_record_ids = [record.record_id for record in route_records]

    assert world.get_events_by_kind("route_blocked") == [blocked_record]
    assert world.get_events_by_kind("route_reopened") == [reopened_record]
    for location_id in (route.from_site_id, route.to_site_id):
        endpoint_records = [
            record
            for record in world.get_events_by_location(location_id)
            if record.record_id in route_record_ids
        ]
        endpoint = world.get_location_by_id(location_id)

        assert endpoint_records == route_records
        assert endpoint is not None
        assert all(record_id in endpoint.recent_event_ids for record_id in route_record_ids)


def test_location_rename_record_follows_pr_k_event_contract() -> None:
    previous_locale = get_locale()
    set_locale("en")
    world = World()

    try:
        record = world.apply_location_rename_change(
            "loc_aethoria_capital",
            "Aethoria March",
            month=3,
            day=4,
        )
    finally:
        set_locale(previous_locale)

    assert record is not None
    assert record.kind == "location_renamed"
    assert record.location_id == "loc_aethoria_capital"
    assert record.summary_key == "events.location_renamed.summary"
    assert record.description
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

    json.dumps(record.render_params)
    assert WorldEventRecord.from_dict(record.to_dict()).to_dict() == record.to_dict()
    assert world.get_events_by_location("loc_aethoria_capital") == [record]
    assert record.record_id in world.get_location_by_id("loc_aethoria_capital").recent_event_ids
    assert render_event_record(record, locale="en", world=world) != record.summary_key


def test_terrain_cell_mutation_record_follows_pr_k_event_contract() -> None:
    previous_locale = get_locale()
    set_locale("en")
    world = World()
    assert world.terrain_map is not None
    x, y = 2, 2
    cell = world.terrain_map.get(x, y)
    assert cell is not None
    old_payload = cell.to_dict()

    try:
        record = world.apply_terrain_cell_change(
            x,
            y,
            biome="forest",
            elevation=180,
            moisture=190,
            temperature=80,
            location_id="loc_aethoria_capital",
            reason_key="fey_bloom",
            month=4,
            day=5,
        )
    finally:
        set_locale(previous_locale)

    assert record is not None
    assert cell.biome == "forest"
    assert cell.elevation == 180
    assert cell.moisture == 190
    assert cell.temperature == 80
    assert record.kind == "terrain_cell_mutated"
    assert record.location_id == "loc_aethoria_capital"
    assert record.summary_key == "events.terrain_cell_mutated.summary"
    assert record.description
    assert record.render_params == {
        "terrain_cell_id": "terrain:2:2",
        "x": 2,
        "y": 2,
        "old_biome": old_payload["biome"],
        "new_biome": "forest",
        "old_elevation": old_payload["elevation"],
        "new_elevation": 180,
        "old_moisture": old_payload["moisture"],
        "new_moisture": 190,
        "old_temperature": old_payload["temperature"],
        "new_temperature": 80,
        "changed_attributes": ["biome", "elevation", "moisture", "temperature"],
        "location_id": "loc_aethoria_capital",
        "reason_key": "fey_bloom",
    }
    assert "world_change" in record.tags
    assert "terrain" in record.tags
    assert "terrain_cell:terrain:2:2" in record.tags
    assert "location:loc_aethoria_capital" in record.tags
    assert record.impacts == [
        {
            "target_type": "terrain_cell",
            "target_id": "terrain:2:2",
            "attribute": "biome",
            "old_value": old_payload["biome"],
            "new_value": "forest",
        },
        {
            "target_type": "terrain_cell",
            "target_id": "terrain:2:2",
            "attribute": "elevation",
            "old_value": old_payload["elevation"],
            "new_value": 180,
        },
        {
            "target_type": "terrain_cell",
            "target_id": "terrain:2:2",
            "attribute": "moisture",
            "old_value": old_payload["moisture"],
            "new_value": 190,
        },
        {
            "target_type": "terrain_cell",
            "target_id": "terrain:2:2",
            "attribute": "temperature",
            "old_value": old_payload["temperature"],
            "new_value": 80,
        },
    ]

    json.dumps(record.render_params)
    assert WorldEventRecord.from_dict(record.to_dict()).to_dict() == record.to_dict()
    assert world.get_events_by_kind("terrain_cell_mutated") == [record]
    assert world.get_events_by_location("loc_aethoria_capital") == [record]
    assert record.record_id in world.get_location_by_id("loc_aethoria_capital").recent_event_ids
    assert render_event_record(record, locale="en", world=world) != record.summary_key


def test_terrain_cell_mutation_summary_renders_localized_biome_terms_in_ja_strict_mode() -> None:
    world = World()
    assert world.terrain_map is not None
    cell = world.terrain_map.get(2, 2)
    assert cell is not None
    assert cell.biome == "plains"

    record = world.apply_terrain_cell_change(
        2,
        2,
        biome="forest",
        location_id="loc_aethoria_capital",
        month=4,
        day=5,
    )

    assert record is not None
    assert render_event_record(record, locale="ja", world=world, strict=True) == (
        "座標 (2, 2) の地形変化: 生物群系が 平原 から 森林。"
    )


def test_terrain_cell_mutation_summary_describes_non_biome_changes_in_strict_mode() -> None:
    world = World()
    assert world.terrain_map is not None
    cell = world.terrain_map.get(2, 2)
    assert cell is not None

    record = world.apply_terrain_cell_change(
        2,
        2,
        elevation=180,
        location_id="loc_aethoria_capital",
        month=4,
        day=5,
    )

    assert record is not None
    assert render_event_record(record, locale="en", world=world, strict=True) == (
        "Terrain at (2, 2) changed: elevation from 128 to 180."
    )

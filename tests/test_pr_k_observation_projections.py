from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.observation import (
    build_era_timeline_projection,
    build_location_history_projection,
    build_war_map_projection,
    build_world_change_report_projection,
)
from fantasy_simulator.world import World


def test_location_history_projection_includes_control_history() -> None:
    world = World()

    first = world.apply_controlling_faction_change("loc_aethoria_capital", "stormwatch_wardens", month=2, day=3)
    second = world.apply_controlling_faction_change("loc_aethoria_capital", None, month=3, day=4)

    projection = build_location_history_projection(
        locations=world.grid.values(),
        event_records=world.event_records,
        location_id="loc_aethoria_capital",
    )

    assert first is not None
    assert second is not None
    assert [entry.record_id for entry in projection.control_history] == [first.record_id, second.record_id]
    assert [(entry.old_faction_id, entry.new_faction_id) for entry in projection.control_history] == [
        (None, "stormwatch_wardens"),
        ("stormwatch_wardens", None),
    ]
    assert projection.control_history[0].summary_key == "events.location_faction_changed.summary"
    assert projection.control_history[0].render_params["new_faction_id"] == "stormwatch_wardens"


def test_war_map_projection_tracks_current_occupations_from_event_records() -> None:
    world = World()

    occupied = world.apply_controlling_faction_change("loc_aethoria_capital", "stormwatch_wardens", month=4)
    released = world.apply_controlling_faction_change("loc_aethoria_capital", None, month=5)
    reoccupied = world.apply_controlling_faction_change("loc_silverbrook", "silverbrook_merchant_league", month=6)

    projection = build_war_map_projection(event_records=world.event_records)

    assert occupied is not None
    assert released is not None
    assert reoccupied is not None
    assert [entry.record_id for entry in projection.occupation_history] == [
        occupied.record_id,
        released.record_id,
        reoccupied.record_id,
    ]
    assert [(entry.location_id, entry.controlling_faction_id) for entry in projection.current_occupations] == [
        ("loc_silverbrook", "silverbrook_merchant_league")
    ]
    assert projection.affected_location_ids == ("loc_aethoria_capital", "loc_silverbrook")
    assert "stormwatch_wardens" in projection.faction_ids
    assert "silverbrook_merchant_league" in projection.faction_ids


def test_era_timeline_projection_reads_semantic_event_records() -> None:
    records = [
        WorldEventRecord(
            kind="era_shifted",
            year=1001,
            month=7,
            day=1,
            description="The Age of Embers gave way to the Dawn Accord.",
            summary_key="events.era_shifted.summary",
            render_params={
                "old_era_id": "age_of_embers",
                "new_era_id": "dawn_accord",
                "old_civilization_phase": "crisis",
                "new_civilization_phase": "new_era",
            },
            tags=["world_change"],
            impacts=[
                {
                    "target_type": "world",
                    "target_id": "world",
                    "attribute": "era_id",
                    "old_value": "age_of_embers",
                    "new_value": "dawn_accord",
                }
            ],
        ),
        WorldEventRecord(
            kind="civilization_phase_drifted",
            year=1002,
            month=1,
            day=1,
            description="The realm settled into aftermath.",
            summary_key="events.civilization_phase_drifted.summary",
            render_params={
                "old_civilization_phase": "new_era",
                "new_civilization_phase": "aftermath",
            },
            tags=["world_change"],
        ),
    ]

    projection = build_era_timeline_projection(event_records=records)

    assert [entry.kind for entry in projection.entries] == ["era_shifted", "civilization_phase_drifted"]
    assert projection.current_era_id == "dawn_accord"
    assert projection.current_civilization_phase == "aftermath"
    assert projection.entries[0].summary_key == "events.era_shifted.summary"
    assert projection.entries[0].render_params["new_era_id"] == "dawn_accord"


def test_world_change_report_projection_counts_world_change_categories() -> None:
    world = World()
    route = world.routes[0]

    route_record = world.apply_route_blocked_change(route.route_id, True, month=8)
    rename_record = world.apply_location_rename_change("loc_aethoria_capital", "Aethoria March", month=8)
    occupation_record = world.apply_controlling_faction_change(
        "loc_silverbrook",
        "silverbrook_merchant_league",
        month=8,
    )

    projection = build_world_change_report_projection(event_records=world.event_records, year=world.year, month=8)

    assert route_record is not None
    assert rename_record is not None
    assert occupation_record is not None
    assert [entry.record_id for entry in projection.entries] == [
        route_record.record_id,
        rename_record.record_id,
        occupation_record.record_id,
    ]
    assert [(item.category, item.count) for item in projection.counts_by_category] == [
        ("location", 1),
        ("occupation", 1),
        ("route", 1),
    ]
    assert route.from_site_id in projection.affected_location_ids
    assert route.to_site_id in projection.affected_location_ids
    assert "loc_aethoria_capital" in projection.affected_location_ids
    assert "loc_silverbrook" in projection.affected_location_ids
    assert projection.entries[0].summary_key == "events.route_blocked.summary"
    assert projection.entries[0].render_params["route_id"] == route.route_id

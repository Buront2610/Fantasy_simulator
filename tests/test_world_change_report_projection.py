from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.observation import build_world_change_report_projection


def test_world_change_report_projection_filters_period_and_counts_categories() -> None:
    records = [
        WorldEventRecord(
            record_id="rec_route",
            kind="route_blocked",
            year=5,
            month=2,
            day=1,
            description="The road closed.",
            summary_key="events.route_blocked.summary",
            render_params={
                "route_id": "route_1",
                "from_location_id": "loc_a",
                "to_location_id": "loc_b",
            },
        ),
        WorldEventRecord(
            record_id="rec_occupation",
            kind="location_faction_changed",
            year=5,
            month=2,
            day=2,
            description="The town changed hands.",
            render_params={
                "location_id": "loc_b",
                "new_faction_id": "wardens",
            },
        ),
        WorldEventRecord(
            record_id="rec_era",
            kind="era_shift",
            year=5,
            month=3,
            day=1,
            description="A new era began.",
            render_params={"new_era_id": "age_of_glass"},
        ),
        WorldEventRecord(
            record_id="rec_terrain",
            kind="terrain_cell_mutated",
            year=5,
            month=2,
            day=4,
            location_id="loc_b",
            description="The lowland became forest.",
            summary_key="events.terrain_cell_mutated.summary",
            render_params={
                "terrain_cell_id": "terrain:1:0",
                "x": 1,
                "y": 0,
                "changed_attributes": ["biome"],
                "location_id": "loc_b",
            },
            tags=["world_change", "terrain", "terrain_cell:terrain:1:0", "location:loc_b"],
        ),
        WorldEventRecord(
            record_id="rec_generic",
            kind="festival",
            year=5,
            month=2,
            day=3,
            description="A festival happened.",
        ),
    ]

    projection = build_world_change_report_projection(event_records=records, year=5, month=2)

    assert [entry.record_id for entry in projection.entries] == ["rec_route", "rec_occupation", "rec_terrain"]
    assert projection.entries[0].summary_key == "events.route_blocked.summary"
    assert projection.entries[0].render_params == {
        "route_id": "route_1",
        "from_location_id": "loc_a",
        "to_location_id": "loc_b",
    }
    assert [(count.category, count.count) for count in projection.counts_by_category] == [
        ("occupation", 1),
        ("route", 1),
        ("terrain", 1),
    ]
    assert projection.affected_location_ids == ("loc_a", "loc_b")


def test_world_change_report_projection_includes_headless_war_and_civilization_categories() -> None:
    records = [
        WorldEventRecord(
            record_id="rec_war",
            kind="war_declared",
            year=8,
            month=1,
            description="A war began.",
        ),
        WorldEventRecord(
            record_id="rec_civ",
            kind="civilization_drift",
            year=8,
            month=1,
            description="Civilization changed.",
            render_params={"civilization_phase": "maritime"},
        ),
    ]

    projection = build_world_change_report_projection(event_records=records, year=8)

    assert [(entry.record_id, entry.category) for entry in projection.entries] == [
        ("rec_war", "war"),
        ("rec_civ", "civilization"),
    ]

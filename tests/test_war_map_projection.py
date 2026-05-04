from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.observation import build_war_map_projection


def test_war_map_projection_reads_war_and_occupation_records_without_world_runtime() -> None:
    records = [
        WorldEventRecord(
            record_id="rec_war",
            kind="war_declared",
            year=12,
            month=2,
            day=1,
            description="War was declared.",
            render_params={
                "location_id": "loc_aethoria_capital",
                "belligerent_faction_ids": ["wardens", "dawn_court"],
            },
        ),
        WorldEventRecord(
            record_id="rec_occupied",
            kind="location_faction_changed",
            year=12,
            month=2,
            day=3,
            location_id="loc_silverbrook",
            description="Silverbrook changed hands.",
            render_params={
                "location_id": "loc_silverbrook",
                "old_faction_id": None,
                "new_faction_id": "wardens",
            },
        ),
        WorldEventRecord(
            record_id="rec_liberated",
            kind="occupation_ended",
            year=12,
            month=4,
            day=5,
            description="Silverbrook was liberated.",
            render_params={
                "location_id": "loc_silverbrook",
                "old_faction_id": "wardens",
            },
        ),
    ]

    projection = build_war_map_projection(event_records=records)

    assert [entry.record_id for entry in projection.events] == [
        "rec_war",
        "rec_occupied",
        "rec_liberated",
    ]
    assert projection.affected_location_ids == ("loc_aethoria_capital", "loc_silverbrook")
    assert projection.faction_ids == ("wardens", "dawn_court")
    assert [(entry.location_id, entry.status) for entry in projection.occupation_history] == [
        ("loc_silverbrook", "occupied"),
        ("loc_silverbrook", "unoccupied"),
    ]
    assert projection.current_occupations == ()


def test_war_map_projection_derives_occupation_from_location_impact() -> None:
    record = WorldEventRecord(
        record_id="rec_impact_occupation",
        kind="location_occupied",
        year=4,
        month=6,
        day=7,
        description="The ford was occupied.",
        impacts=[
            {
                "target_type": "location",
                "target_id": "loc_ford",
                "attribute": "controlling_faction_id",
                "old_value": "ford_keepers",
                "new_value": "river_host",
            }
        ],
    )

    projection = build_war_map_projection(event_records=[record])

    assert projection.current_occupations[0].location_id == "loc_ford"
    assert projection.current_occupations[0].previous_faction_id == "ford_keepers"
    assert projection.current_occupations[0].controlling_faction_id == "river_host"

from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.observation import build_era_timeline_projection


def test_era_timeline_projection_reads_era_and_civilization_records_without_world_runtime() -> None:
    records = [
        WorldEventRecord(
            record_id="rec_era",
            kind="era_shift",
            year=30,
            month=1,
            day=1,
            description="The Age of Glass began.",
            render_params={
                "old_era_id": "age_of_ash",
                "new_era_id": "age_of_glass",
            },
        ),
        WorldEventRecord(
            record_id="rec_civ",
            kind="civilization_drift",
            year=31,
            month=4,
            day=2,
            description="The coast turned maritime.",
            impacts=[
                {
                    "target_type": "world",
                    "target_id": "aethoria",
                    "attribute": "civilization_phase",
                    "old_value": "frontier",
                    "new_value": "maritime",
                }
            ],
        ),
    ]

    projection = build_era_timeline_projection(event_records=records)

    assert [entry.record_id for entry in projection.entries] == ["rec_era", "rec_civ"]
    assert projection.entries[0].old_era_id == "age_of_ash"
    assert projection.entries[0].new_era_id == "age_of_glass"
    assert projection.entries[1].old_civilization_phase == "frontier"
    assert projection.entries[1].new_civilization_phase == "maritime"
    assert projection.current_era_id == "age_of_glass"
    assert projection.current_civilization_phase == "maritime"


def test_era_timeline_projection_ignores_unstructured_era_text() -> None:
    record = WorldEventRecord(
        record_id="rec_flavor",
        kind="festival",
        year=2,
        month=3,
        description="An old era was mentioned in a song.",
    )

    projection = build_era_timeline_projection(event_records=[record])

    assert projection.entries == ()
    assert projection.current_era_id is None
    assert projection.current_civilization_phase is None

from __future__ import annotations

from fantasy_simulator.world_event.models import WorldEventRecord
from fantasy_simulator.observation import build_era_timeline_projection
from fantasy_simulator.reports import format_yearly_report, generate_yearly_report
from fantasy_simulator.ui.map_renderer import build_map_info
from fantasy_simulator.world import World
from fantasy_simulator.world_location.state import clamp_state
from fantasy_simulator.world_change.event_contracts import validate_world_change_event_contract


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


def test_world_era_and_civilization_api_records_project_and_report_without_public_runtime_fields() -> None:
    world = World()
    capital = world.get_location_by_id("loc_aethoria_capital")
    assert capital is not None
    before_capital = (
        capital.prosperity,
        capital.safety,
        capital.mood,
        capital.traffic,
        capital.danger,
        capital.rumor_heat,
    )

    era_record = world.apply_era_shift(
        "age_of_reckoning",
        authored_era_keys={"age_of_embers", "age_of_reckoning"},
        year=1002,
        month=1,
        cause_key="dragon_war",
    )
    drift_record = world.apply_civilization_phase_drift(
        "crisis",
        score_deltas={"prosperity": -7, "safety": -20, "mood": -5, "traffic": -3},
        year=1002,
        month=2,
        reason_key="war_pressure",
    )

    assert era_record is not None
    assert drift_record is not None
    validate_world_change_event_contract(era_record)
    validate_world_change_event_contract(drift_record)
    assert not hasattr(world, "era_runtime")
    assert not hasattr(world, "civilization_phase")
    assert not hasattr(world, "world_scores")
    assert (
        capital.prosperity,
        capital.safety,
        capital.mood,
        capital.traffic,
        capital.danger,
        capital.rumor_heat,
    ) == (
        clamp_state(before_capital[0] + 3 - 7),
        clamp_state(before_capital[1] - 20),
        clamp_state(before_capital[2] + 4 - 5),
        clamp_state(before_capital[3] + 6 - 3),
        clamp_state(before_capital[4] + 10),
        clamp_state(before_capital[5] + 20 + 10),
    )
    assert capital.live_traces[-2]["char_name"] == "world"
    assert "new era" in capital.live_traces[-2]["text"]
    assert capital.live_traces[-1]["char_name"] == "world"
    assert "Civilization" in capital.live_traces[-1]["text"]

    projection = build_era_timeline_projection(event_records=world.event_records)
    assert [entry.record_id for entry in projection.entries] == [
        era_record.record_id,
        drift_record.record_id,
    ]
    assert projection.current_era_id == "age_of_reckoning"
    assert projection.current_civilization_phase == "crisis"

    report = generate_yearly_report(world, 1002)
    assert [(entry.record_id, entry.category) for entry in report.world_change_entries] == [
        (era_record.record_id, "era"),
        (drift_record.record_id, "civilization"),
    ]
    text = format_yearly_report(report)
    assert "▶ World Changes" in text
    assert "Era:" in text
    assert "Civilization:" in text
    assert "age_of_reckoning" in text
    assert "crisis" in text

    map_info = build_map_info(world)
    capital_cell = next(cell for cell in map_info.cells.values() if cell.location_id == "loc_aethoria_capital")
    assert capital_cell.safety_label == capital.safety_label
    assert capital_cell.mood == capital.mood

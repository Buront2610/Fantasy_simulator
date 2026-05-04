from __future__ import annotations

import json
from dataclasses import dataclass, field

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.event_rendering import render_event_record
from fantasy_simulator.ids import EraKey
from fantasy_simulator.observation import build_era_timeline_projection
from fantasy_simulator.world_change import (
    DriftCivilizationPhaseCommand,
    ShiftEraCommand,
    apply_world_change_set,
    build_civilization_phase_drift_change_set,
    build_era_shift_change_set,
)
from fantasy_simulator.world_change.state_machines import (
    transition_civilization_phase,
    transition_era_shift,
    transition_world_scores,
)


@dataclass
class _EraRuntime:
    era_key: str
    civilization_phase: str
    world_scores: dict[str, int] = field(
        default_factory=lambda: {
            "prosperity": 50,
            "safety": 50,
            "traffic": 50,
            "mood": 50,
        }
    )


def _describe(summary_key: str, _render_params: dict, fallback_description: str) -> str:
    assert summary_key in {"events.era_shifted.summary", "events.civilization_phase_drifted.summary"}
    return fallback_description


def test_era_shift_state_machine_returns_noop_for_same_era() -> None:
    assert transition_era_shift(
        old_era_key="age_of_embers",
        requested_era_key="age_of_embers",
        old_civilization_phase="stable",
        requested_civilization_phase="new_era",
    ) is None


def test_civilization_phase_state_machine_distinguishes_phase_drift() -> None:
    transition = transition_civilization_phase("stable", "crisis")

    assert transition is not None
    assert transition.old_phase == "stable"
    assert transition.new_phase == "crisis"
    assert transition.event_kind == "civilization_phase_drifted"


def test_world_score_transition_clamps_to_defined_range() -> None:
    transitions = transition_world_scores(
        {"prosperity": 95, "safety": 8, "traffic": 50, "mood": 50},
        {"prosperity": 10, "safety": -20},
    )

    assert [(item.score_key, item.old_value, item.new_value, item.delta) for item in transitions] == [
        ("prosperity", 95, 100, 5),
        ("safety", 8, 0, -8),
    ]


def test_era_shift_changeset_contains_event_and_runtime_update() -> None:
    runtime = _EraRuntime(era_key="age_of_embers", civilization_phase="stable")
    command = ShiftEraCommand(
        new_era_key=EraKey("age_of_reckoning"),
        year=1002,
        month=6,
        day=7,
        new_civilization_phase="new_era",
        cause_key="dragon_war",
    )

    change_set = build_era_shift_change_set(
        command,
        era_runtime=runtime,
        authored_era_keys={"age_of_embers", "age_of_reckoning"},
        describe=_describe,
    )

    assert change_set is not None
    assert change_set.projection_hints == ("era_timeline",)
    assert change_set.era_updates[0].old_era_key == "age_of_embers"
    assert change_set.era_updates[0].new_era_key == "age_of_reckoning"
    record = change_set.events[0]
    assert record.kind == "era_shifted"
    assert record.summary_key == "events.era_shifted.summary"
    assert record.render_params == {
        "old_era_key": "age_of_embers",
        "new_era_key": "age_of_reckoning",
        "old_civilization_phase": "stable",
        "new_civilization_phase": "new_era",
        "cause_key": "dragon_war",
    }
    assert record.impacts == [
        {
            "target_type": "world",
            "target_id": "era",
            "attribute": "era_key",
            "old_value": "age_of_embers",
            "new_value": "age_of_reckoning",
        },
        {
            "target_type": "world",
            "target_id": "civilization",
            "attribute": "civilization_phase",
            "old_value": "stable",
            "new_value": "new_era",
        },
    ]
    json.dumps(record.render_params)
    assert WorldEventRecord.from_dict(record.to_dict()).to_dict() == record.to_dict()
    assert render_event_record(record, locale="en", strict=True) == (
        "The era shifted from age_of_embers to age_of_reckoning; civilization entered new_era."
    )


def test_era_timeline_projection_reads_era_shift_records_from_slice_adapter() -> None:
    runtime = _EraRuntime(era_key="age_of_embers", civilization_phase="stable")
    command = ShiftEraCommand(
        new_era_key=EraKey("age_of_reckoning"),
        year=1002,
        new_civilization_phase="new_era",
    )
    change_set = build_era_shift_change_set(
        command,
        era_runtime=runtime,
        authored_era_keys={"age_of_embers", "age_of_reckoning"},
        describe=_describe,
    )
    assert change_set is not None

    projection = build_era_timeline_projection(event_records=change_set.events)

    assert projection.current_era_id == "age_of_reckoning"
    assert projection.current_civilization_phase == "new_era"
    assert projection.entries[0].old_era_id == "age_of_embers"
    assert projection.entries[0].new_era_id == "age_of_reckoning"


def test_era_shift_rejects_unknown_authored_era_definition() -> None:
    runtime = _EraRuntime(era_key="age_of_embers", civilization_phase="stable")
    command = ShiftEraCommand(new_era_key=EraKey("age_of_mirrors"), year=1002)

    try:
        build_era_shift_change_set(
            command,
            era_runtime=runtime,
            authored_era_keys={"age_of_embers"},
            describe=_describe,
        )
    except ValueError as exc:
        assert "unknown era definition" in str(exc)
    else:
        raise AssertionError("Expected unknown era validation to fail")


def test_civilization_phase_drift_changeset_contains_phase_and_score_updates() -> None:
    runtime = _EraRuntime(
        era_key="age_of_embers",
        civilization_phase="stable",
        world_scores={"prosperity": 95, "safety": 8, "traffic": 50, "mood": 50},
    )
    command = DriftCivilizationPhaseCommand(
        new_phase="crisis",
        year=1003,
        month=2,
        day=3,
        score_deltas={"prosperity": 10, "safety": -20, "mood": -5},
        reason_key="war_pressure",
    )

    change_set = build_civilization_phase_drift_change_set(command, era_runtime=runtime, describe=_describe)

    assert change_set is not None
    assert change_set.era_updates[0].old_civilization_phase == "stable"
    assert change_set.era_updates[0].new_civilization_phase == "crisis"
    assert [(item.score_key, item.old_value, item.new_value) for item in change_set.era_updates[0].score_updates] == [
        ("prosperity", 95, 100),
        ("safety", 8, 0),
        ("mood", 50, 45),
    ]
    record = change_set.events[0]
    assert record.kind == "civilization_phase_drifted"
    assert record.render_params["score_changes"] == [
        {"score_key": "prosperity", "old_value": 95, "new_value": 100, "delta": 5},
        {"score_key": "safety", "old_value": 8, "new_value": 0, "delta": -8},
        {"score_key": "mood", "old_value": 50, "new_value": 45, "delta": -5},
    ]
    assert record.impacts[-3:] == [
        {
            "target_type": "world",
            "target_id": "world_scores",
            "attribute": "prosperity",
            "old_value": 95,
            "new_value": 100,
        },
        {
            "target_type": "world",
            "target_id": "world_scores",
            "attribute": "safety",
            "old_value": 8,
            "new_value": 0,
        },
        {
            "target_type": "world",
            "target_id": "world_scores",
            "attribute": "mood",
            "old_value": 50,
            "new_value": 45,
        },
    ]
    assert render_event_record(record, locale="en", strict=True) == (
        "Civilization drifted from stable to crisis."
    )


def test_world_change_reducer_applies_era_runtime_update_and_records_event() -> None:
    runtime = _EraRuntime(era_key="age_of_embers", civilization_phase="stable")
    records: list[WorldEventRecord] = []
    command = ShiftEraCommand(new_era_key=EraKey("age_of_reckoning"), year=1002)
    change_set = build_era_shift_change_set(
        command,
        era_runtime=runtime,
        authored_era_keys={"age_of_embers", "age_of_reckoning"},
        describe=_describe,
    )
    assert change_set is not None

    stored = apply_world_change_set(
        change_set,
        routes=[],
        era_runtime=runtime,
        record_event=lambda record: records.append(record) or record,
    )

    assert runtime.era_key == "age_of_reckoning"
    assert runtime.civilization_phase == "new_era"
    assert stored == tuple(records)


def test_world_change_reducer_rolls_back_era_runtime_when_recording_fails() -> None:
    runtime = _EraRuntime(
        era_key="age_of_embers",
        civilization_phase="stable",
        world_scores={"prosperity": 95, "safety": 8, "traffic": 50, "mood": 50},
    )
    command = DriftCivilizationPhaseCommand(
        new_phase="crisis",
        year=1003,
        score_deltas={"prosperity": 10, "safety": -20},
    )
    change_set = build_civilization_phase_drift_change_set(command, era_runtime=runtime, describe=_describe)
    assert change_set is not None

    def _fail_record(_record: WorldEventRecord) -> WorldEventRecord:
        raise ValueError("recording failed")

    try:
        apply_world_change_set(change_set, routes=[], era_runtime=runtime, record_event=_fail_record)
    except ValueError as exc:
        assert "recording failed" in str(exc)
    else:
        raise AssertionError("Expected recording failure to roll back era runtime")

    assert runtime.era_key == "age_of_embers"
    assert runtime.civilization_phase == "stable"
    assert runtime.world_scores == {"prosperity": 95, "safety": 8, "traffic": 50, "mood": 50}

"""Persistence policy guardrails for era/civilization runtime state."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.observation import build_era_timeline_projection
from fantasy_simulator.persistence.migrations import CURRENT_VERSION
from fantasy_simulator.persistence.save_load import load_simulation
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


def _write_payload(path: Path, payload: dict[str, Any]) -> None:
    payload["schema_version"] = CURRENT_VERSION
    path.write_text(json.dumps(payload), encoding="utf-8")


def _era_records() -> list[WorldEventRecord]:
    return [
        WorldEventRecord(
            record_id="rec-era-shift",
            kind="era_shifted",
            year=1002,
            month=6,
            day=7,
            description="The era shifted from age_of_embers to age_of_reckoning.",
            summary_key="events.era_shifted.summary",
            render_params={
                "old_era_key": "age_of_embers",
                "new_era_key": "age_of_reckoning",
                "old_civilization_phase": "stable",
                "new_civilization_phase": "new_era",
            },
            impacts=[
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
            ],
        ),
        WorldEventRecord(
            record_id="rec-civilization-drift",
            kind="civilization_phase_drifted",
            year=1003,
            month=2,
            day=3,
            description="Civilization drifted from new_era to crisis.",
            summary_key="events.civilization_phase_drifted.summary",
            render_params={
                "era_key": "age_of_reckoning",
                "old_civilization_phase": "new_era",
                "new_civilization_phase": "crisis",
                "score_changes": [
                    {"score_key": "safety", "old_value": 50, "new_value": 35, "delta": -15},
                ],
            },
            impacts=[
                {
                    "target_type": "world",
                    "target_id": "civilization",
                    "attribute": "civilization_phase",
                    "old_value": "new_era",
                    "new_value": "crisis",
                },
                {
                    "target_type": "world",
                    "target_id": "world_scores",
                    "attribute": "safety",
                    "old_value": 50,
                    "new_value": 35,
                },
            ],
        ),
    ]


def test_new_saves_omit_deferred_era_civilization_runtime_fields() -> None:
    world = World()
    world.event_records = _era_records()
    world.era_key = "experimental_runtime_era"
    world.civilization_phase = "experimental_runtime_phase"
    world.world_scores = {"safety": 1}
    world.era_runtime = {
        "era_key": "experimental_runtime_era",
        "civilization_phase": "experimental_runtime_phase",
    }

    payload = Simulator(world, seed=0).to_dict()

    assert payload["world"]["event_records"] == [record.to_dict() for record in world.event_records]
    assert "era_key" not in payload["world"]
    assert "civilization_phase" not in payload["world"]
    assert "world_scores" not in payload["world"]
    assert "era_runtime" not in payload["world"]


def test_stale_era_civilization_snapshot_fields_do_not_override_canonical_records(tmp_path) -> None:
    payload = Simulator(World(), seed=0).to_dict()
    payload["world"]["event_records"] = [record.to_dict() for record in _era_records()]
    payload["world"]["era_key"] = "age_of_stale_snapshot"
    payload["world"]["civilization_phase"] = "stale_phase"
    payload["world"]["world_scores"] = {"safety": 1}
    payload["world"]["era_runtime"] = {
        "era_key": "age_of_stale_runtime",
        "civilization_phase": "stale_runtime_phase",
        "world_scores": {"safety": 2},
    }
    path = tmp_path / "stale-era-runtime-conflict.json"
    _write_payload(path, payload)

    restored = load_simulation(str(path))

    assert restored is not None
    projection = build_era_timeline_projection(event_records=restored.world.event_records)
    assert [entry.record_id for entry in projection.entries] == [
        "rec-era-shift",
        "rec-civilization-drift",
    ]
    assert projection.current_era_id == "age_of_reckoning"
    assert projection.current_civilization_phase == "crisis"
    assert not hasattr(restored.world, "era_runtime")
    assert not hasattr(restored.world, "era_key")
    assert not hasattr(restored.world, "civilization_phase")
    assert not hasattr(restored.world, "world_scores")


def test_stale_era_civilization_snapshot_without_records_is_not_projection_fallback(tmp_path) -> None:
    payload = Simulator(World(), seed=0).to_dict()
    payload["world"]["event_records"] = []
    payload["world"]["era_key"] = "age_of_snapshot_only"
    payload["world"]["civilization_phase"] = "snapshot_phase"
    payload["world"]["world_scores"] = {"safety": 99}
    payload["world"]["era_runtime"] = {
        "era_key": "age_of_runtime_only",
        "civilization_phase": "runtime_phase",
    }
    path = tmp_path / "stale-era-runtime-no-records.json"
    _write_payload(path, payload)

    restored = load_simulation(str(path))

    assert restored is not None
    projection = build_era_timeline_projection(event_records=restored.world.event_records)
    assert projection.entries == ()
    assert projection.current_era_id is None
    assert projection.current_civilization_phase is None
    assert not hasattr(restored.world, "era_runtime")

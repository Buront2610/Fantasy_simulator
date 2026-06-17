"""Tests for the headless application service boundary."""

from __future__ import annotations

import json

import pytest

from fantasy_simulator.app import FantasyAppService
from fantasy_simulator.character import Character
from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


def _world_with_characters() -> World:
    world = World()
    world.add_character(Character(name="A", age=25, gender="F", race="Human", job="Mage"))
    world.add_character(Character(name="B", age=26, gender="M", race="Human", job="Warrior"))
    return world


def test_dashboard_snapshot_is_json_safe_and_plain_data() -> None:
    world = _world_with_characters()
    world.record_event(WorldEventRecord(record_id="evt_1", kind="meeting", year=1000, description="A meeting."))
    service = FantasyAppService(Simulator(world, events_per_year=0, seed=1))

    payload = service.dashboard().to_dict()

    assert payload["world_name"] == world.name
    assert payload["event_counts_by_kind"] == {"meeting": 1}
    assert payload["recent_events"][0]["record_id"] == "evt_1"
    json.dumps(payload, ensure_ascii=False, sort_keys=True)


def test_advance_years_command_returns_updated_dashboard() -> None:
    world = _world_with_characters()
    service = FantasyAppService(Simulator(world, events_per_year=0, seed=1))

    result = service.handle_command({"command": "advance_years", "years": 2}).to_dict()

    assert result["ok"] is True
    assert result["command"] == "advance_years"
    assert result["data"]["dashboard"]["year"] == 1002
    json.dumps(result, ensure_ascii=False, sort_keys=True)


def test_event_cause_command_returns_direct_causes_and_effects() -> None:
    world = _world_with_characters()
    cause = world.record_event(WorldEventRecord(record_id="evt_cause", kind="meeting", description="Cause."))
    effect = world.record_event(WorldEventRecord(
        record_id="evt_effect",
        kind="battle",
        description="Effect.",
        cause_event_ids=[cause.record_id],
    ))
    service = FantasyAppService(Simulator(world, events_per_year=0, seed=1))

    result = service.handle_command({"command": "get_event_causes", "record_id": effect.record_id}).to_dict()
    reverse = service.handle_command({"command": "get_event_causes", "record_id": cause.record_id}).to_dict()

    assert result["data"]["causes"][0]["record_id"] == cause.record_id
    assert result["data"]["effects"] == []
    assert reverse["data"]["causes"] == []
    assert reverse["data"]["effects"][0]["record_id"] == effect.record_id


@pytest.mark.parametrize(
    "command",
    [
        {},
        {"command": ""},
        {"command": "advance_years", "years": True},
        {"command": "advance_years", "years": -1},
        {"command": "get_event_causes", "record_id": ""},
    ],
)
def test_app_service_rejects_invalid_commands(command) -> None:
    service = FantasyAppService(Simulator(_world_with_characters(), events_per_year=0, seed=1))

    with pytest.raises(ValueError):
        service.handle_command(command)

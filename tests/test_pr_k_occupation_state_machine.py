from __future__ import annotations

import json
from dataclasses import dataclass

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.event_rendering import render_event_record
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.ids import FactionId, LocationId
from fantasy_simulator.world import World
from fantasy_simulator.world_change import (
    SetLocationControllingFactionCommand,
    apply_world_change_set,
    build_location_occupation_change_set,
)
from fantasy_simulator.world_change.state_machines import transition_location_occupation_state


@dataclass
class _Location:
    id: str
    canonical_name: str
    controlling_faction_id: str | None = None


def _describe(summary_key: str, _render_params: dict, fallback_description: str) -> str:
    assert summary_key == "events.location_faction_changed.summary"
    return fallback_description


def _location_name(location_id: str) -> str:
    return {"loc_capital": "Aethoria Capital"}.get(location_id, location_id)


def test_location_occupation_state_machine_returns_noop_for_same_faction() -> None:
    assert transition_location_occupation_state("stormwatch_wardens", "stormwatch_wardens") is None
    assert transition_location_occupation_state(None, "") is None


def test_location_occupation_state_machine_distinguishes_occupation_and_release() -> None:
    occupied = transition_location_occupation_state(None, "stormwatch_wardens")
    released = transition_location_occupation_state("stormwatch_wardens", None)

    assert occupied is not None
    assert occupied.old_faction_id is None
    assert occupied.new_faction_id == "stormwatch_wardens"
    assert occupied.event_kind == "location_faction_changed"
    assert released is not None
    assert released.old_faction_id == "stormwatch_wardens"
    assert released.new_faction_id is None


def test_location_occupation_changeset_contains_event_and_runtime_update() -> None:
    location = _Location("loc_capital", "Aethoria Capital")
    command = SetLocationControllingFactionCommand(
        location_id=LocationId(location.id),
        faction_id=FactionId("stormwatch_wardens"),
        year=1001,
        month=2,
        day=3,
    )

    change_set = build_location_occupation_change_set(
        command,
        location_index={location.id: location},
        location_name=_location_name,
        known_faction_ids={"stormwatch_wardens"},
        describe=_describe,
    )

    assert change_set is not None
    assert change_set.occupation_updates[0].old_faction_id is None
    assert change_set.occupation_updates[0].new_faction_id == "stormwatch_wardens"
    record = change_set.events[0]
    assert record.kind == "location_faction_changed"
    assert record.location_id == "loc_capital"
    assert record.render_params == {
        "location_id": "loc_capital",
        "old_faction_id": None,
        "new_faction_id": "stormwatch_wardens",
    }
    assert "location:loc_capital" in record.tags
    assert record.impacts == [
        {
            "target_type": "location",
            "target_id": "loc_capital",
            "attribute": "controlling_faction_id",
            "old_value": None,
            "new_value": "stormwatch_wardens",
        }
    ]


def test_location_occupation_changeset_rejects_unknown_known_faction() -> None:
    location = _Location("loc_capital", "Aethoria Capital")
    command = SetLocationControllingFactionCommand(
        location_id=LocationId(location.id),
        faction_id=FactionId("unknown_faction"),
        year=1001,
    )

    try:
        build_location_occupation_change_set(
            command,
            location_index={location.id: location},
            location_name=_location_name,
            known_faction_ids={"stormwatch_wardens"},
            describe=_describe,
        )
    except ValueError as exc:
        assert "unknown faction id" in str(exc)
    else:
        raise AssertionError("Expected unknown faction validation to fail")


def test_world_change_reducer_applies_occupation_and_records_event() -> None:
    location = _Location("loc_capital", "Aethoria Capital")
    location_index = {location.id: location}
    records: list[WorldEventRecord] = []
    command = SetLocationControllingFactionCommand(
        location_id=LocationId(location.id),
        faction_id=FactionId("stormwatch_wardens"),
        year=1001,
    )
    change_set = build_location_occupation_change_set(
        command,
        location_index=location_index,
        location_name=_location_name,
        describe=_describe,
    )
    assert change_set is not None

    stored = apply_world_change_set(
        change_set,
        routes=[],
        location_index=location_index,
        record_event=lambda record: records.append(record) or record,
    )

    assert location.controlling_faction_id == "stormwatch_wardens"
    assert stored == tuple(records)
    assert records[0].kind == "location_faction_changed"


def test_world_change_reducer_rolls_back_occupation_when_recording_fails() -> None:
    location = _Location("loc_capital", "Aethoria Capital")
    location_index = {location.id: location}
    command = SetLocationControllingFactionCommand(
        location_id=LocationId(location.id),
        faction_id=FactionId("stormwatch_wardens"),
        year=1001,
    )
    change_set = build_location_occupation_change_set(
        command,
        location_index=location_index,
        location_name=_location_name,
        describe=_describe,
    )
    assert change_set is not None

    def _fail_record(_record: WorldEventRecord) -> WorldEventRecord:
        raise ValueError("recording failed")

    try:
        apply_world_change_set(
            change_set,
            routes=[],
            location_index=location_index,
            record_event=_fail_record,
        )
    except ValueError as exc:
        assert "recording failed" in str(exc)
    else:
        raise AssertionError("Expected recording failure to roll back occupation")

    assert location.controlling_faction_id is None


def test_world_occupation_record_follows_pr_k_event_contract() -> None:
    previous_locale = get_locale()
    set_locale("en")
    world = World()

    try:
        record = world.apply_controlling_faction_change(
            "loc_aethoria_capital",
            "stormwatch_wardens",
            month=4,
            day=5,
        )
    finally:
        set_locale(previous_locale)

    assert record is not None
    assert world.get_location_by_id("loc_aethoria_capital").controlling_faction_id == "stormwatch_wardens"
    assert record.kind == "location_faction_changed"
    assert record.location_id == "loc_aethoria_capital"
    assert record.summary_key == "events.location_faction_changed.summary"
    assert record.render_params["location_id"] == "loc_aethoria_capital"
    assert record.render_params["old_faction_id"] is None
    assert record.render_params["new_faction_id"] == "stormwatch_wardens"
    assert "location:loc_aethoria_capital" in record.tags
    assert record.impacts[0]["attribute"] == "controlling_faction_id"

    json.dumps(record.render_params)
    assert WorldEventRecord.from_dict(record.to_dict()).to_dict() == record.to_dict()
    assert world.get_events_by_location("loc_aethoria_capital") == [record]
    assert record.record_id in world.get_location_by_id("loc_aethoria_capital").recent_event_ids
    assert render_event_record(record, locale="en", world=world) != record.summary_key
    assert "location" not in record.render_params


def test_world_occupation_change_can_reject_unknown_faction_when_strict_ids_are_supplied() -> None:
    world = World()

    try:
        world.apply_controlling_faction_change(
            "loc_aethoria_capital",
            "unknown_faction",
            known_faction_ids={"stormwatch_wardens"},
        )
    except ValueError as exc:
        assert "unknown faction id" in str(exc)
    else:
        raise AssertionError("Expected strict faction validation to reject unknown ids")

    assert world.get_location_by_id("loc_aethoria_capital").controlling_faction_id is None
    assert world.event_records == []

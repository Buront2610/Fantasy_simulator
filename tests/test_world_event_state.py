from __future__ import annotations

import pytest

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.world import World
from fantasy_simulator.world_event_state import (
    apply_event_impact_to_location,
    append_canonical_event_record,
)


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def test_apply_event_impact_to_location_updates_all_battle_fields() -> None:
    world = World()
    loc = world.get_location_by_id("loc_thornwood")
    before = {
        "safety": loc.safety,
        "mood": loc.mood,
        "danger": loc.danger,
        "rumor_heat": loc.rumor_heat,
    }

    impacts = apply_event_impact_to_location(
        kind="battle",
        location_id="loc_thornwood",
        location_index=world._location_id_index,
        clamp_state=_clamp,
    )

    assert impacts
    assert loc.safety == before["safety"] - 2
    assert loc.mood == before["mood"] - 3
    assert loc.danger == before["danger"] + 3
    assert loc.rumor_heat == before["rumor_heat"] + 5


def test_apply_event_impact_to_location_ignores_unknown_location() -> None:
    world = World()

    impacts = apply_event_impact_to_location(
        kind="battle",
        location_id="missing",
        location_index=world._location_id_index,
        clamp_state=_clamp,
    )

    assert impacts == []


def test_apply_event_impact_to_location_unknown_kind_is_noop() -> None:
    world = World()
    loc = world.get_location_by_id("loc_thornwood")
    before = (loc.safety, loc.mood, loc.danger, loc.rumor_heat)

    impacts = apply_event_impact_to_location(
        kind="unknown_kind",
        location_id="loc_thornwood",
        location_index=world._location_id_index,
        clamp_state=_clamp,
    )

    assert impacts == []
    assert (loc.safety, loc.mood, loc.danger, loc.rumor_heat) == before


def test_apply_event_impact_to_location_clamps_low_and_high_bounds() -> None:
    world = World()
    loc = world.get_location_by_id("loc_thornwood")
    loc.safety = 1
    loc.mood = 1
    loc.danger = 99
    loc.rumor_heat = 99

    apply_event_impact_to_location(
        kind="battle",
        location_id="loc_thornwood",
        location_index=world._location_id_index,
        clamp_state=_clamp,
    )

    assert loc.safety == 0
    assert loc.mood == 0
    assert loc.danger == 100
    assert loc.rumor_heat == 100


def test_append_canonical_event_record_prunes_records_and_indexes() -> None:
    world = World()
    max_records = 2

    r1 = WorldEventRecord(record_id="r1", kind="battle", year=1000, location_id="loc_thornwood")
    r2 = WorldEventRecord(record_id="r2", kind="battle", year=1000, location_id="loc_thornwood")
    r3 = WorldEventRecord(record_id="r3", kind="battle", year=1000, location_id="loc_thornwood")

    stored = append_canonical_event_record(
        record=r1,
        event_records=world.event_records,
        location_index=world._location_id_index,
        grid=world.grid,
        max_event_records=max_records,
    )
    append_canonical_event_record(
        record=r2,
        event_records=world.event_records,
        location_index=world._location_id_index,
        grid=world.grid,
        max_event_records=max_records,
    )
    append_canonical_event_record(
        record=r3,
        event_records=world.event_records,
        location_index=world._location_id_index,
        grid=world.grid,
        max_event_records=max_records,
    )

    assert stored.record_id == "r1"
    assert [record.record_id for record in world.event_records] == ["r2", "r3"]
    recent_ids = world.get_location_by_id("loc_thornwood").recent_event_ids
    assert recent_ids == ["r2", "r3"]


def test_append_canonical_event_record_normalizes_invalid_location_id() -> None:
    world = World()
    record = WorldEventRecord(record_id="r1", kind="battle", year=1000, location_id="invalid")

    stored = append_canonical_event_record(
        record=record,
        event_records=world.event_records,
        location_index=world._location_id_index,
        grid=world.grid,
        max_event_records=world.MAX_EVENT_RECORDS,
    )

    assert stored.location_id is None
    assert record.location_id == "invalid"
    assert world.event_records[-1].location_id is None


def test_append_canonical_event_record_keeps_identity_when_location_is_none() -> None:
    world = World()
    record = WorldEventRecord(record_id="r1", kind="battle", year=1000, location_id=None)

    stored = append_canonical_event_record(
        record=record,
        event_records=world.event_records,
        location_index=world._location_id_index,
        grid=world.grid,
        max_event_records=world.MAX_EVENT_RECORDS,
    )

    assert stored is record


def test_apply_event_impact_fails_fast_on_invalid_rule_attribute(monkeypatch) -> None:
    world = World()
    from fantasy_simulator import world_event_state as wes

    monkeypatch.setitem(wes.EVENT_IMPACT_RULES, "broken_kind", {"unknown_attr": 1})
    try:
        with pytest.raises(ValueError, match="Unsupported impact attribute"):
            apply_event_impact_to_location(
                kind="broken_kind",
                location_id="loc_thornwood",
                location_index=world._location_id_index,
                clamp_state=_clamp,
            )
    finally:
        wes.EVENT_IMPACT_RULES.pop("broken_kind", None)


def test_apply_event_impact_fails_fast_on_invalid_rule_delta_type(monkeypatch) -> None:
    world = World()
    from fantasy_simulator import world_event_state as wes

    monkeypatch.setitem(wes.EVENT_IMPACT_RULES, "broken_kind", {"danger": "1"})
    try:
        with pytest.raises(ValueError, match="Unsupported impact delta type"):
            apply_event_impact_to_location(
                kind="broken_kind",
                location_id="loc_thornwood",
                location_index=world._location_id_index,
                clamp_state=_clamp,
            )
    finally:
        wes.EVENT_IMPACT_RULES.pop("broken_kind", None)

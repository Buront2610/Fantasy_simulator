from __future__ import annotations

import re

from fantasy_simulator.event_models import EventResult, WorldEventRecord, generate_record_id


class _DeterministicRng:
    def __init__(self, value: int) -> None:
        self.value = value

    def getrandbits(self, _k: int) -> int:
        return self.value


def test_generate_record_id_is_deterministic_with_rng() -> None:
    rng = _DeterministicRng(0x1234)
    first = generate_record_id(rng)
    second = generate_record_id(rng)
    assert first == second == "00000000000000000000000000001234"


def test_generate_record_id_returns_32_char_hex() -> None:
    rid = generate_record_id()
    assert len(rid) == 32
    assert re.fullmatch(r"[0-9a-f]{32}", rid)


def test_event_result_round_trip_and_defensive_copy() -> None:
    payload = {
        "nested": {"x": 1},
    }
    result = EventResult(
        description="d",
        affected_characters=["a", "b"],
        stat_changes={"a": {"strength": 1}},
        event_type="battle",
        year=1001,
        metadata=payload,
    )

    dumped = result.to_dict()
    dumped["metadata"]["nested"]["x"] = 99
    dumped["stat_changes"]["a"]["strength"] = 7

    assert result.metadata["nested"]["x"] == 1
    assert result.stat_changes["a"]["strength"] == 1

    restored = EventResult.from_dict(result.to_dict())
    assert restored == result


def test_world_event_record_round_trip_and_defensive_copy() -> None:
    record = WorldEventRecord(
        record_id="r1",
        kind="battle",
        year=1001,
        month=3,
        day=12,
        impacts=[{"delta": {"danger": 1}}],
        tags=["combat"],
    )

    dumped = record.to_dict()
    dumped["impacts"][0]["delta"]["danger"] = 9

    assert record.impacts[0]["delta"]["danger"] == 1

    restored = WorldEventRecord.from_dict(record.to_dict())
    assert restored.to_dict() == record.to_dict()


def test_world_event_record_from_event_result_to_event_result_round_trip() -> None:
    source = EventResult(
        description="A battle happened",
        affected_characters=["c1", "c2"],
        event_type="battle",
        year=1002,
        metadata={"key": "value"},
    )
    record = WorldEventRecord.from_event_result(
        source,
        location_id="loc_thornwood",
        month=5,
        day=7,
    )

    projected = record.to_event_result()
    assert projected.to_dict() == source.to_dict()


def test_world_event_record_normalization_policy_is_lenient_not_fail_fast() -> None:
    record = WorldEventRecord(month=0, day=-10, severity=99, absolute_day=-5)
    assert record.month == 1
    assert record.day == 1
    assert record.severity == 5
    assert record.absolute_day == 0


def test_world_event_record_legacy_event_result_is_defensively_copied() -> None:
    record = WorldEventRecord(
        record_id="r1",
        legacy_event_result={"metadata": {"nested": {"value": 1}}},
    )

    dumped = record.to_dict()
    dumped["legacy_event_result"]["metadata"]["nested"]["value"] = 9
    assert record.legacy_event_result["metadata"]["nested"]["value"] == 1

    loaded = WorldEventRecord.from_dict(record.to_dict())
    loaded.legacy_event_result["metadata"]["nested"]["value"] = 5
    assert record.legacy_event_result["metadata"]["nested"]["value"] == 1


def test_world_event_record_month_day_policy_is_lower_bound_normalization_only() -> None:
    record = WorldEventRecord(month=99, day=999)
    assert record.month == 99
    assert record.day == 999

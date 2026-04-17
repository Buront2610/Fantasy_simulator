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


def test_world_event_record_rejects_string_secondary_actor_ids_at_load_boundary() -> None:
    malformed = {
        "record_id": "r2",
        "kind": "battle",
        "year": 1001,
        "description": "Malformed secondary actors",
        "secondary_actor_ids": "char_2",
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "secondary_actor_ids" in str(exc)
    else:
        raise AssertionError("Expected string secondary_actor_ids to fail fast")


def test_world_event_record_rejects_non_string_tags_at_load_boundary() -> None:
    malformed = {
        "record_id": "r3",
        "kind": "battle",
        "year": 1001,
        "description": "Malformed tags",
        "tags": {"major": True},
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "tags" in str(exc)
    else:
        raise AssertionError("Expected non-list tags to fail fast")


def test_world_event_record_rejects_non_dict_impacts_at_load_boundary() -> None:
    malformed = {
        "record_id": "r4",
        "kind": "battle",
        "year": 1001,
        "description": "Malformed impacts",
        "impacts": [{"attribute": "danger"}, "not-a-dict"],
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "impacts" in str(exc)
    else:
        raise AssertionError("Expected malformed impacts to fail fast")


def test_world_event_record_from_event_result_to_event_result_round_trip() -> None:
    source = EventResult(
        description="A battle happened",
        affected_characters=["c1", "c2"],
        stat_changes={"c1": {"strength": -2}},
        event_type="battle",
        year=1002,
        metadata={"key": "value", "nested": {"flag": True}},
    )
    record = WorldEventRecord.from_event_result(
        source,
        location_id="loc_thornwood",
        month=5,
        day=7,
    )

    projected = record.to_event_result()
    assert projected.description == source.description
    assert projected.event_type == source.event_type
    assert projected.year == source.year
    assert projected.affected_characters == source.affected_characters
    assert projected.stat_changes == source.stat_changes
    assert projected.metadata == source.metadata


def test_world_event_record_preserves_migrated_legacy_event_result_payload() -> None:
    record = WorldEventRecord.from_dict(
        {
            "record_id": "legacy_history_000001",
            "kind": "battle",
            "year": 1000,
            "month": 1,
            "day": 1,
            "description": "A legacy battle occurred.",
            "primary_actor_id": "char_1",
            "legacy_event_result": {
                "description": "A legacy battle occurred.",
                "affected_characters": ["char_1"],
                "stat_changes": {"char_1": {"strength": -1}},
                "event_type": "battle",
                "year": 1000,
                "metadata": {"source": "legacy"},
            },
        }
    )

    projected = record.to_event_result()

    assert projected.affected_characters == ["char_1"]
    assert projected.stat_changes == {"char_1": {"strength": -1}}
    assert projected.metadata == {"source": "legacy"}


def test_world_event_record_legacy_event_result_payload_is_defensively_copied() -> None:
    payload = {
        "description": "A legacy battle occurred.",
        "affected_characters": ["char_1"],
        "stat_changes": {"char_1": {"strength": -1}},
        "event_type": "battle",
        "year": 1000,
        "metadata": {"source": "legacy", "nested": {"flag": True}},
    }
    record = WorldEventRecord.from_dict(
        {
            "record_id": "legacy_history_000001",
            "kind": "battle",
            "year": 1000,
            "description": "A legacy battle occurred.",
            "legacy_event_result": payload,
        }
    )

    payload["metadata"]["nested"]["flag"] = False
    dumped = record.to_dict()
    dumped["legacy_event_result"]["metadata"]["nested"]["flag"] = "changed"

    assert record.legacy_event_result == {
        "description": "A legacy battle occurred.",
        "affected_characters": ["char_1"],
        "stat_changes": {"char_1": {"strength": -1}},
        "event_type": "battle",
        "year": 1000,
        "metadata": {"source": "legacy", "nested": {"flag": True}},
    }


def test_world_event_record_rejects_malformed_legacy_event_result_payload_at_load_boundary() -> None:
    malformed = {
        "record_id": "legacy_history_000001",
        "kind": "battle",
        "year": 1000,
        "description": "A legacy battle occurred.",
        "legacy_event_result": {
            "description": "A legacy battle occurred.",
            "affected_characters": ["char_1"],
            "stat_changes": {"char_1": {"strength": "bad"}},
            "event_type": "battle",
            "year": 1000,
            "metadata": {"source": "legacy"},
        },
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "legacy_event_result" in str(exc)
    else:
        raise AssertionError("Expected malformed legacy_event_result to fail fast")


def test_world_event_record_rejects_bool_year_in_legacy_event_result() -> None:
    malformed = {
        "record_id": "legacy_history_000003",
        "kind": "battle",
        "year": 1000,
        "description": "A legacy battle occurred.",
        "legacy_event_result": {
            "description": "A legacy battle occurred.",
            "affected_characters": ["char_1"],
            "stat_changes": {"char_1": {"strength": -1}},
            "event_type": "battle",
            "year": True,
            "metadata": {"source": "legacy"},
        },
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "year" in str(exc)
    else:
        raise AssertionError("Expected bool year to fail fast")


def test_world_event_record_rejects_bool_stat_delta_in_legacy_event_result() -> None:
    malformed = {
        "record_id": "legacy_history_000004",
        "kind": "battle",
        "year": 1000,
        "description": "A legacy battle occurred.",
        "legacy_event_result": {
            "description": "A legacy battle occurred.",
            "affected_characters": ["char_1"],
            "stat_changes": {"char_1": {"strength": False}},
            "event_type": "battle",
            "year": 1000,
            "metadata": {"source": "legacy"},
        },
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "stat deltas" in str(exc)
    else:
        raise AssertionError("Expected bool stat delta to fail fast")


def test_world_event_record_rejects_string_affected_characters_in_legacy_event_result() -> None:
    malformed = {
        "record_id": "legacy_history_000002",
        "kind": "battle",
        "year": 1000,
        "description": "A legacy battle occurred.",
        "legacy_event_result": {
            "description": "A legacy battle occurred.",
            "affected_characters": "char_1",
            "stat_changes": {"char_1": {"strength": -1}},
            "event_type": "battle",
            "year": 1000,
            "metadata": {"source": "legacy"},
        },
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "affected_characters" in str(exc)
    else:
        raise AssertionError("Expected string affected_characters to fail fast")


def test_world_event_record_preserves_legacy_event_log_entry_string_payload() -> None:
    record = WorldEventRecord.from_dict(
        {
            "record_id": "legacy_log_000001",
            "kind": "legacy_event_log",
            "year": 1000,
            "description": "Year 1000: A legacy omen spread through the capital.",
            "legacy_event_log_entry": "Year 1000: A legacy omen spread through the capital.",
        }
    )

    assert record.legacy_event_log_entry == "Year 1000: A legacy omen spread through the capital."
    assert record.to_dict()["legacy_event_log_entry"] == "Year 1000: A legacy omen spread through the capital."


def test_world_event_record_rejects_non_string_legacy_event_log_entry_at_load_boundary() -> None:
    malformed = {
        "record_id": "legacy_log_000001",
        "kind": "legacy_event_log",
        "year": 1000,
        "description": "Year 1000: A legacy omen spread through the capital.",
        "legacy_event_log_entry": {"text": "not-a-string"},
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "legacy_event_log_entry" in str(exc)
    else:
        raise AssertionError("Expected non-string legacy_event_log_entry to fail fast")


def test_world_event_record_normalization_policy_is_lenient_not_fail_fast() -> None:
    record = WorldEventRecord(month=0, day=-10, severity=99, absolute_day=-5)
    assert record.month == 1
    assert record.day == 1
    assert record.severity == 5
    assert record.absolute_day == 0


def test_world_event_record_month_day_policy_is_lower_bound_normalization_only() -> None:
    record = WorldEventRecord(month=99, day=999)
    assert record.month == 99
    assert record.day == 999

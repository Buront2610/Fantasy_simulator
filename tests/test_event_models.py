from __future__ import annotations

import re
from math import inf

import fantasy_simulator.event_rendering as event_rendering
from fantasy_simulator.event_models import EventResult, WorldEventRecord, generate_record_id
from fantasy_simulator.event_rendering import render_event_record
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.world import World


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
        summary_key="events.battle.summary",
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
        summary_key="events.battle.summary",
        render_params={"actor": "Aldric", "location": "Thornwood"},
        impacts=[{"delta": {"danger": 1}}],
        tags=["combat"],
    )

    dumped = record.to_dict()
    dumped["impacts"][0]["delta"]["danger"] = 9
    dumped["render_params"]["actor"] = "Changed"

    assert record.impacts[0]["delta"]["danger"] == 1
    assert record.render_params["actor"] == "Aldric"

    restored = WorldEventRecord.from_dict(record.to_dict())
    assert restored.to_dict() == record.to_dict()


def test_world_event_record_omits_empty_render_params_for_compatibility() -> None:
    record = WorldEventRecord(record_id="r_empty_render_params")

    assert "render_params" not in record.to_dict()


def test_world_event_record_rejects_malformed_render_params_at_load_boundary() -> None:
    malformed = {
        "record_id": "r_render_params",
        "kind": "battle",
        "year": 1001,
        "description": "Malformed render params",
        "render_params": ["not-a-dict"],
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "render_params" in str(exc)
    else:
        raise AssertionError("Expected malformed render_params to fail fast")


def test_world_event_record_rejects_non_string_render_param_keys() -> None:
    try:
        WorldEventRecord(render_params={1: "Aldric"})
    except ValueError as exc:
        assert "render_params" in str(exc)
    else:
        raise AssertionError("Expected non-string render_params keys to fail fast")


def test_world_event_record_rejects_non_json_render_param_values() -> None:
    invalid_values = [
        {"bad": object()},
        {"bad": {"nested": object()}},
        {"bad": [object()]},
        {"bad": inf},
    ]

    for render_params in invalid_values:
        try:
            WorldEventRecord(render_params=render_params)
        except ValueError as exc:
            assert "render_params" in str(exc)
            continue
        raise AssertionError(f"Expected non-JSON render_params to fail fast: {render_params!r}")


def test_render_event_record_localizes_none_faction_params_at_display_time() -> None:
    record = WorldEventRecord(
        summary_key="events.location_faction_changed.summary",
        render_params={
            "location": "Aethoria Capital",
            "location_id": "loc_aethoria_capital",
            "old_faction_id": None,
            "new_faction_id": "wardens",
        },
    )

    assert render_event_record(record, locale="en") == (
        "Aethoria Capital changed controlling faction from none to wardens."
    )
    assert render_event_record(record, locale="ja") == (
        "Aethoria Capital の支配勢力が なし から wardens に変わった。"
    )


def test_render_event_record_explicit_locale_does_not_call_global_locale_mutator(monkeypatch) -> None:
    previous = get_locale()
    set_locale("en")
    record = WorldEventRecord(
        kind="battle",
        description="A fallback battle happened.",
        summary_key="events.battle.summary",
        render_params={"actor": "Aldric", "location": "Thornwood"},
    )

    def _fail_set_locale(_locale: str) -> str:
        raise AssertionError("render_event_record should not mutate global locale")

    if hasattr(event_rendering, "set_locale"):
        monkeypatch.setattr(event_rendering, "set_locale", _fail_set_locale)

    try:
        assert render_event_record(record, locale="ja") == "Aldric は Thornwood で戦った。"
        assert get_locale() == "en"
    finally:
        set_locale(previous)


def test_render_event_record_uses_world_context_for_missing_location_name() -> None:
    world = World()
    record = WorldEventRecord(
        kind="battle",
        location_id="loc_aethoria_capital",
        description="A fallback battle happened.",
        summary_key="events.battle.summary",
        render_params={"actor": "Aldric"},
    )

    assert render_event_record(record, locale="en", world=world) == "Aldric fought at Aethoria Capital."


def test_render_event_record_uses_world_context_for_authored_faction_names() -> None:
    world = World()
    record = WorldEventRecord(
        summary_key="events.location_faction_changed.summary",
        render_params={
            "location": "Aethoria Capital",
            "location_id": "loc_aethoria_capital",
            "old_faction_id": None,
            "new_faction_id": "stormwatch_wardens",
        },
    )

    assert render_event_record(record, locale="en", world=world) == (
        "Aethoria Capital changed controlling faction from none to Stormwatch Wardens."
    )


def test_render_event_record_uses_summary_key_render_params_and_locale() -> None:
    previous = get_locale()
    set_locale("en")
    record = WorldEventRecord(
        kind="battle",
        description="A fallback battle happened.",
        summary_key="events.battle.summary",
        render_params={"actor": "Aldric", "location": "Thornwood"},
    )

    try:
        assert render_event_record(record, locale="en") == "Aldric fought at Thornwood."
        assert render_event_record(record, locale="ja") == "Aldric は Thornwood で戦った。"
        assert get_locale() == "en"
    finally:
        set_locale(previous)


def test_render_event_record_falls_back_to_description_for_missing_key_or_params() -> None:
    missing_key = WorldEventRecord(
        description="Known only by legacy text.",
        summary_key="events.unknown.summary",
        render_params={"actor": "Aldric"},
    )
    missing_params = WorldEventRecord(
        description="A fallback battle happened.",
        summary_key="events.battle.summary",
        render_params={"actor": "Aldric"},
    )

    assert render_event_record(missing_key, locale="en") == "Known only by legacy text."
    assert render_event_record(missing_params, locale="en") == "A fallback battle happened."


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


def test_world_event_record_rejects_non_string_core_scalars_at_load_boundary() -> None:
    malformed = {
        "record_id": 123,
        "kind": "battle",
        "year": 1001,
        "description": "Malformed id",
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "record_id" in str(exc)
    else:
        raise AssertionError("Expected non-string record_id to fail fast")


def test_world_event_record_rejects_non_string_optional_primary_actor_at_load_boundary() -> None:
    malformed = {
        "record_id": "r5",
        "kind": "battle",
        "year": 1001,
        "description": "Malformed primary actor",
        "primary_actor_id": 99,
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "primary_actor_id" in str(exc)
    else:
        raise AssertionError("Expected non-string primary_actor_id to fail fast")


def test_world_event_record_rejects_non_int_year_at_load_boundary() -> None:
    malformed = {
        "record_id": "r6",
        "kind": "battle",
        "year": "1001",
        "description": "Malformed year",
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "year" in str(exc)
    else:
        raise AssertionError("Expected non-int year to fail fast")


def test_world_event_record_rejects_non_string_location_id_at_load_boundary() -> None:
    malformed = {
        "record_id": "r7",
        "kind": "battle",
        "year": 1001,
        "description": "Malformed location",
        "location_id": ["loc_thornwood"],
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "location_id" in str(exc)
    else:
        raise AssertionError("Expected non-string location_id to fail fast")


def test_world_event_record_from_event_result_to_event_result_round_trip() -> None:
    source = EventResult(
        description="A battle happened",
        affected_characters=["c1", "c2"],
        stat_changes={"c1": {"strength": -2}},
        event_type="battle",
        summary_key="events.battle.summary",
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
    assert projected.summary_key == source.summary_key
    assert projected.year == source.year
    assert projected.affected_characters == source.affected_characters
    assert projected.stat_changes == source.stat_changes
    assert projected.metadata == source.metadata


def test_world_event_record_to_event_result_exposes_render_params_metadata() -> None:
    record = WorldEventRecord(
        record_id="route_blocked_1",
        kind="route_blocked",
        year=1000,
        summary_key="events.route_blocked.summary",
        render_params={
            "route_id": "route_a_b",
            "from_location_id": "loc_a",
            "to_location_id": "loc_b",
            "from_location": "Alpha",
            "to_location": "Bravo",
        },
    )

    projected = record.to_event_result()
    projected.metadata["render_params"]["from_location"] = "Changed"

    assert projected.metadata["render_params"]["route_id"] == "route_a_b"
    assert record.render_params["from_location"] == "Alpha"


def test_world_event_record_to_event_result_merges_render_params_into_legacy_metadata() -> None:
    record = WorldEventRecord(
        record_id="legacy_route_blocked_1",
        kind="route_blocked",
        year=1000,
        description="The route was blocked.",
        summary_key="events.route_blocked.summary",
        render_params={"from_location": "Alpha", "to_location": "Bravo"},
        legacy_event_result={
            "description": "Legacy route text.",
            "affected_characters": [],
            "stat_changes": {},
            "event_type": "generic",
            "year": 999,
            "metadata": {"source": "legacy"},
        },
    )

    projected = record.to_event_result()

    assert projected.metadata == {
        "source": "legacy",
        "render_params": {"from_location": "Alpha", "to_location": "Bravo"},
    }


def test_world_event_record_from_event_result_uses_metadata_summary_key_fallback() -> None:
    source = EventResult(
        description="A meeting happened",
        affected_characters=["c1"],
        event_type="meeting",
        year=1002,
        metadata={"summary_key": "events.meeting.summary"},
    )

    record = WorldEventRecord.from_event_result(source)

    assert record.summary_key == "events.meeting.summary"


def test_world_event_record_rejects_non_string_metadata_summary_key() -> None:
    source = EventResult(
        description="A meeting happened",
        affected_characters=["c1"],
        event_type="meeting",
        year=1002,
        metadata={"summary_key": {"bad": True}},
    )

    try:
        WorldEventRecord.from_event_result(source)
    except ValueError as exc:
        assert "summary_key" in str(exc)
    else:
        raise AssertionError("Expected metadata summary_key to fail fast")


def test_world_event_record_rejects_non_string_summary_key_at_load_boundary() -> None:
    malformed = {
        "record_id": "r_summary",
        "kind": "battle",
        "year": 1001,
        "description": "Malformed summary key",
        "summary_key": {"bad": True},
    }

    try:
        WorldEventRecord.from_dict(malformed)
    except ValueError as exc:
        assert "summary_key" in str(exc)
    else:
        raise AssertionError("Expected non-string summary_key to fail fast")


def test_world_event_record_rejects_invalid_summary_key_shape() -> None:
    try:
        WorldEventRecord.from_dict(
            {
                "record_id": "r_summary",
                "kind": "battle",
                "year": 1001,
                "description": "Malformed summary key",
                "summary_key": "not a dotted key",
            }
        )
    except ValueError as exc:
        assert "summary_key" in str(exc)
    else:
        raise AssertionError("Expected malformed summary_key to fail fast")


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


def test_world_event_record_constructor_rejects_invalid_canonical_fields() -> None:
    invalid_payloads = [
        {"record_id": None},
        {"kind": 3},
        {"year": "1000"},
        {"primary_actor_id": 7},
        {"secondary_actor_ids": ["char_a", 2]},
        {"tags": "watched"},
        {"impacts": ["not-a-dict"]},
    ]

    for payload in invalid_payloads:
        try:
            WorldEventRecord(**payload)
        except ValueError:
            continue
        raise AssertionError(f"Expected constructor validation to reject {payload!r}")

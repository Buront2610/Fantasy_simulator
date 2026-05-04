from __future__ import annotations

from dataclasses import dataclass, field

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.ids import LocationId
from fantasy_simulator.world_change import (
    RenameLocationCommand,
    apply_world_change_set,
    build_location_rename_change_set,
)
from fantasy_simulator.world_change.state_machines import transition_location_name


@dataclass
class _Location:
    id: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)


def _describe(summary_key: str, _render_params: dict, fallback_description: str) -> str:
    assert summary_key == "events.location_renamed.summary"
    return fallback_description


def test_location_name_state_machine_returns_noop_for_same_name() -> None:
    assert transition_location_name(
        old_name="Aethoria Capital",
        requested_name="Aethoria Capital",
        aliases=[],
        max_aliases=3,
    ) is None


def test_location_name_state_machine_preserves_old_name_as_alias() -> None:
    transition = transition_location_name(
        old_name="Aethoria Capital",
        requested_name="Aethoria March",
        aliases=["Crown City"],
        max_aliases=3,
    )

    assert transition is not None
    assert transition.old_name == "Aethoria Capital"
    assert transition.new_name == "Aethoria March"
    assert transition.old_aliases == ("Crown City",)
    assert transition.new_aliases == ("Crown City", "Aethoria Capital")
    assert transition.alias_added is True
    assert transition.event_kind == "location_renamed"


def test_location_rename_changeset_contains_event_and_location_update() -> None:
    location = _Location("loc_capital", "Aethoria Capital")
    command = RenameLocationCommand(
        location_id=LocationId(location.id),
        new_name="Aethoria March",
        year=1001,
        month=2,
        day=3,
    )

    change_set = build_location_rename_change_set(
        command,
        location_index={location.id: location},
        location_name_index={location.canonical_name: location},
        max_aliases=3,
        describe=_describe,
    )

    assert change_set is not None
    assert change_set.location_updates[0].old_name == "Aethoria Capital"
    assert change_set.location_updates[0].new_name == "Aethoria March"
    record = change_set.events[0]
    assert record.kind == "location_renamed"
    assert record.location_id == "loc_capital"
    assert record.render_params == {
        "location_id": "loc_capital",
        "old_name": "Aethoria Capital",
        "new_name": "Aethoria March",
    }
    assert record.description == "Aethoria Capital was renamed Aethoria March."


def test_location_rename_changeset_rejects_duplicate_canonical_name() -> None:
    capital = _Location("loc_capital", "Aethoria Capital")
    harbor = _Location("loc_harbor", "Silver Harbor")
    command = RenameLocationCommand(
        location_id=LocationId(capital.id),
        new_name="Silver Harbor",
        year=1001,
    )

    try:
        build_location_rename_change_set(
            command,
            location_index={capital.id: capital, harbor.id: harbor},
            location_name_index={capital.canonical_name: capital, harbor.canonical_name: harbor},
            max_aliases=3,
            describe=_describe,
        )
    except ValueError as exc:
        assert "location name already exists" in str(exc)
    else:
        raise AssertionError("Expected duplicate official location name to fail")


def test_world_change_reducer_applies_location_rename_and_records_event() -> None:
    location = _Location("loc_capital", "Aethoria Capital")
    location_index = {location.id: location}
    location_name_index = {location.canonical_name: location}
    records: list[WorldEventRecord] = []
    command = RenameLocationCommand(
        location_id=LocationId(location.id),
        new_name="Aethoria March",
        year=1001,
    )
    change_set = build_location_rename_change_set(
        command,
        location_index=location_index,
        location_name_index=location_name_index,
        max_aliases=3,
        describe=_describe,
    )
    assert change_set is not None

    stored = apply_world_change_set(
        change_set,
        routes=[],
        location_index=location_index,
        location_name_index=location_name_index,
        record_event=lambda record: records.append(record) or record,
    )

    assert location.canonical_name == "Aethoria March"
    assert location.aliases == ["Aethoria Capital"]
    assert "Aethoria Capital" not in location_name_index
    assert location_name_index["Aethoria March"] is location
    assert stored == tuple(records)


def test_world_change_reducer_rolls_back_location_rename_when_recording_fails() -> None:
    location = _Location("loc_capital", "Aethoria Capital")
    location_index = {location.id: location}
    location_name_index = {location.canonical_name: location}
    command = RenameLocationCommand(
        location_id=LocationId(location.id),
        new_name="Aethoria March",
        year=1001,
    )
    change_set = build_location_rename_change_set(
        command,
        location_index=location_index,
        location_name_index=location_name_index,
        max_aliases=3,
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
            location_name_index=location_name_index,
            record_event=_fail_record,
        )
    except ValueError as exc:
        assert "recording failed" in str(exc)
    else:
        raise AssertionError("Expected recording failure to roll back location rename")

    assert location.canonical_name == "Aethoria Capital"
    assert location.aliases == []
    assert location_name_index["Aethoria Capital"] is location
    assert "Aethoria March" not in location_name_index

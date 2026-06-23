from __future__ import annotations

from dataclasses import dataclass, field

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.world_event.history import record_world_event
from fantasy_simulator.world_event.index import EventHistoryIndex


@dataclass
class _Actor:
    favorite: bool = False
    spotlighted: bool = False
    playable: bool = False


@dataclass
class _Location:
    id: str
    recent_event_ids: list[str] = field(default_factory=list)


def test_record_world_event_adds_watched_actor_tags_without_mutating_input_record() -> None:
    record = WorldEventRecord(
        record_id="evt_1",
        primary_actor_id="char_1",
        secondary_actor_ids=["char_2"],
        tags=["initial"],
        location_id="loc_1",
    )
    original_tags = list(record.tags)
    event_records: list[WorldEventRecord] = []
    location = _Location("loc_1")

    stored = record_world_event(
        record=record,
        event_records=event_records,
        event_index=EventHistoryIndex(),
        location_index={location.id: location},
        grid={(0, 0): location},
        max_event_records=10,
        get_character_by_id=lambda actor_id: (
            _Actor(favorite=True)
            if actor_id == "char_1"
            else _Actor(spotlighted=True) if actor_id == "char_2" else None
        ),
        watched_actor_tag_prefix="watched:",
    )

    assert record.tags == original_tags
    assert record.secondary_actor_ids == ["char_2"]
    assert stored is event_records[0]
    assert stored is not record
    assert stored.tags == ["initial", "watched:char_1", "watched:char_2"]
    assert location.recent_event_ids == ["evt_1"]


def test_record_world_event_without_watched_tags_stores_original_record() -> None:
    record = WorldEventRecord(record_id="evt_2", primary_actor_id="char_2")
    event_records: list[WorldEventRecord] = []

    stored = record_world_event(
        record=record,
        event_records=event_records,
        event_index=EventHistoryIndex(),
        location_index={},
        grid={},
        max_event_records=10,
        get_character_by_id=lambda _actor_id: None,
        watched_actor_tag_prefix="watched:",
    )

    assert stored is record
    assert event_records == [record]


def test_record_world_event_updates_current_index_incrementally() -> None:
    initial = WorldEventRecord(record_id="evt_1", kind="battle", location_id="loc_1")
    event_records = [initial]
    location = _Location("loc_1")
    event_index = EventHistoryIndex()
    event_index.ensure_current(event_records)
    initial_signature = event_index.signature

    stored = record_world_event(
        record=WorldEventRecord(
            record_id="evt_2",
            kind="journey",
            location_id="loc_1",
            primary_actor_id="char_1",
        ),
        event_records=event_records,
        event_index=event_index,
        location_index={location.id: location},
        grid={(0, 0): location},
        max_event_records=10,
        get_character_by_id=lambda _actor_id: None,
        watched_actor_tag_prefix="watched:",
    )

    assert stored is event_records[-1]
    assert event_index.signature != initial_signature
    assert event_index.by_record_id(event_records, "evt_2") is stored
    assert event_index.by_location_id(event_records, "loc_1") == event_records
    assert event_index.by_actor_id(event_records, "char_1") == [stored]


def test_record_world_event_write_path_avoids_full_signature_rebuild(monkeypatch) -> None:
    initial = WorldEventRecord(record_id="evt_1", kind="battle", location_id="loc_1")
    event_records = [initial]
    location = _Location("loc_1")
    event_index = EventHistoryIndex()
    event_index.ensure_record_ids_current(event_records)

    def fail_signature(_records):
        raise AssertionError("canonical append should not rebuild the full event signature")

    monkeypatch.setattr("fantasy_simulator.world_event.index._event_signature", fail_signature)

    stored = record_world_event(
        record=WorldEventRecord(record_id="evt_2", kind="journey", location_id="loc_1"),
        event_records=event_records,
        event_index=event_index,
        location_index={location.id: location},
        grid={(0, 0): location},
        max_event_records=10,
        get_character_by_id=lambda _actor_id: None,
        watched_actor_tag_prefix="watched:",
    )

    assert stored is event_records[-1]
    assert event_index.signature == ()
    assert event_index.record_ids == {"evt_1", "evt_2"}


def test_record_world_event_duplicate_ids_follow_direct_record_id_mutation() -> None:
    initial = WorldEventRecord(record_id="evt_old", kind="battle", location_id="loc_1")
    event_records = [initial]
    location = _Location("loc_1")
    event_index = EventHistoryIndex()
    event_index.ensure_current(event_records)
    initial.record_id = "evt_mutated"

    stored = record_world_event(
        record=WorldEventRecord(record_id="evt_old", kind="journey", location_id="loc_1"),
        event_records=event_records,
        event_index=event_index,
        location_index={location.id: location},
        grid={(0, 0): location},
        max_event_records=10,
        get_character_by_id=lambda _actor_id: None,
        watched_actor_tag_prefix="watched:",
    )

    assert stored.record_id == "evt_old"
    assert event_index.record_ids == {"evt_mutated", "evt_old"}


def test_record_world_event_prunes_current_index_when_record_cap_trims_history() -> None:
    old = WorldEventRecord(record_id="evt_old", kind="battle", location_id="loc_1")
    event_records = [old]
    location = _Location("loc_1", recent_event_ids=["evt_old"])
    event_index = EventHistoryIndex()
    event_index.ensure_current(event_records)

    stored = record_world_event(
        record=WorldEventRecord(record_id="evt_new", kind="journey", location_id="loc_1"),
        event_records=event_records,
        event_index=event_index,
        location_index={location.id: location},
        grid={(0, 0): location},
        max_event_records=1,
        get_character_by_id=lambda _actor_id: None,
        watched_actor_tag_prefix="watched:",
    )

    assert event_records == [stored]
    assert event_index.by_record_id(event_records, "evt_old") is None
    assert event_index.by_record_id(event_records, "evt_new") is stored
    assert event_index.by_location_id(event_records, "loc_1") == [stored]
    assert location.recent_event_ids == ["evt_new"]

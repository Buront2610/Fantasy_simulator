from __future__ import annotations

from dataclasses import dataclass, field

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.world_event_history import record_world_event
from fantasy_simulator.world_event_index import EventHistoryIndex


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

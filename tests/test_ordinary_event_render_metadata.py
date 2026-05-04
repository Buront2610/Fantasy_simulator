import random

import pytest

from fantasy_simulator.character import Character
from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.event_rendering import render_event_record
from fantasy_simulator.events import EventSystem
from fantasy_simulator.events_activity import resolve_journey_event
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


def _make_char(name: str, *, location_id: str = "loc_aethoria_capital", age: int = 25) -> Character:
    return Character(
        name=name,
        age=age,
        gender="Male",
        race="Human",
        job="Warrior",
        strength=50,
        constitution=50,
        intelligence=50,
        dexterity=50,
        wisdom=40,
        charisma=40,
        skills={"Swordsmanship": 2},
        location_id=location_id,
    )


def _save_load_render(result, world: World, tmp_path, *, location_id: str) -> tuple[str, str]:
    record, rendered = _save_load_record(result, world, tmp_path, location_id=location_id)
    return record.summary_key, rendered


def _save_load_record(result, world: World, tmp_path, *, location_id: str):
    sim = Simulator(world, seed=0)
    sim._record_event(result, location_id=location_id)  # noqa: SLF001 - event-recording contract coverage
    path = tmp_path / "ordinary-event-render-metadata.json"
    assert save_simulation(sim, str(path)) is True

    restored = load_simulation(str(path))
    assert restored is not None
    record = restored.world.event_records[-1]
    rendered = render_event_record(record, locale="en", world=restored.world, strict=True)
    return record, rendered


def test_activity_event_renders_from_metadata_after_cross_locale_save_load(tmp_path):
    previous_locale = get_locale()
    set_locale("ja")
    try:
        world = World()
        char = _make_char("Alice")
        world.add_character(char)

        result = EventSystem().event_discovery(char, world, rng=random.Random(1))
        assert "発見" in result.description

        summary_key, rendered = _save_load_render(result, world, tmp_path, location_id=char.location_id)

        assert summary_key == "events.discovery.summary"
        assert "Alice discovered" in rendered
        assert "発見" not in rendered
    finally:
        set_locale(previous_locale)


def test_skill_training_event_renders_from_metadata_after_cross_locale_save_load(tmp_path):
    previous_locale = get_locale()
    set_locale("ja")
    try:
        world = World()
        char = _make_char("Alice")
        world.add_character(char)

        result = EventSystem().event_skill_training(char, world, rng=random.Random(0))
        assert "Swordsmanship" not in result.description

        summary_key, rendered = _save_load_render(result, world, tmp_path, location_id=char.location_id)

        assert summary_key == "events.skill_training.summary"
        assert "Alice" in rendered
        assert "Swordsmanship" in rendered
    finally:
        set_locale(previous_locale)


def test_journey_event_renders_from_stable_ids_after_cross_locale_save_load(tmp_path):
    previous_locale = get_locale()
    set_locale("ja")
    try:
        world = World()
        char = _make_char("Alice")
        start_location_id = char.location_id
        world.add_character(char)

        result = EventSystem().event_journey(char, world, rng=random.Random(0))

        record, rendered = _save_load_record(result, world, tmp_path, location_id=char.location_id)

        assert record.summary_key == "events.journey.summary"
        assert record.render_params["from_location_id"] == start_location_id
        assert record.render_params["to_location_id"] == char.location_id
        assert "road_event" not in record.render_params
        assert "Alice journeyed from" in rendered
        assert "都市" not in rendered
    finally:
        set_locale(previous_locale)


def test_journey_custom_road_event_uses_raw_fallback_without_blank_render(tmp_path):
    previous_locale = get_locale()
    set_locale("ja")
    try:
        world = World()
        char = _make_char("Alice")
        world.add_character(char)

        result = resolve_journey_event(
            char,
            world,
            journey_events=["crossed a haunted bridge"],
            rng=random.Random(0),
        )

        record, rendered = _save_load_record(result, world, tmp_path, location_id=char.location_id)

        assert record.summary_key == "events.journey.summary"
        assert "road_event_key" not in record.render_params
        assert record.render_params["road_event"] == "crossed a haunted bridge"
        assert "crossed a haunted bridge" in rendered
        assert "and ." not in rendered
    finally:
        set_locale(previous_locale)


def test_lifecycle_event_renders_from_metadata_after_cross_locale_save_load(tmp_path):
    previous_locale = get_locale()
    set_locale("ja")
    try:
        world = World()
        char = _make_char("Elder", age=24)
        world.add_character(char)

        result = EventSystem().event_aging(char, world, rng=random.Random(2))
        assert "歳になった" in result.description

        summary_key, rendered = _save_load_render(result, world, tmp_path, location_id=char.location_id)

        assert summary_key == "events.aging_young.summary"
        assert rendered == "Elder turned 25. Youth still drives them forward."
    finally:
        set_locale(previous_locale)


def test_death_location_required_cause_falls_back_without_world_context():
    record = WorldEventRecord(
        record_id="rec_death_monster",
        kind="death",
        year=1000,
        description="fallback death text",
        summary_key="events.death.summary",
        render_params={
            "name": "Elder",
            "race": "Human",
            "job": "Warrior",
            "age": 95,
            "cause_key": "death_cause_monster",
            "location_id": "loc_aethoria_capital",
        },
    )

    assert render_event_record(record, locale="en", world=None) == "fallback death text"
    with pytest.raises(KeyError, match="location"):
        render_event_record(record, locale="en", world=None, strict=True)


def test_death_event_renders_from_metadata_after_cross_locale_save_load(tmp_path):
    previous_locale = get_locale()
    set_locale("ja")
    try:
        world = World()
        char = _make_char("Elder", age=95)
        world.add_character(char)

        result = EventSystem().event_death(char, world, rng=random.Random(0))
        assert "亡くなった" in result.description

        summary_key, rendered = _save_load_render(result, world, tmp_path, location_id=char.location_id)

        assert summary_key == "events.death.summary"
        assert "Elder (Human Warrior, age 95) died" in rendered
        assert "亡くなった" not in rendered
    finally:
        set_locale(previous_locale)


def test_dying_resolution_event_renders_from_metadata_after_cross_locale_save_load(tmp_path):
    previous_locale = get_locale()
    set_locale("ja")
    try:
        world = World()
        char = _make_char("Alice")
        char.injury_status = "dying"
        world.add_character(char)

        result = EventSystem().check_dying_resolution(char, world, rng=random.Random(1))
        assert result is not None
        assert "持ち直した" in result.description

        summary_key, rendered = _save_load_render(result, world, tmp_path, location_id=char.location_id)

        assert summary_key == "events.dying_stabilized.summary"
        assert rendered == "Alice miraculously stabilized from a dying state at Aethoria Capital."
    finally:
        set_locale(previous_locale)


def test_relationship_event_renders_from_metadata_after_cross_locale_save_load(tmp_path):
    previous_locale = get_locale()
    set_locale("ja")
    try:
        world = World()
        char_a = _make_char("Alice")
        char_b = _make_char("Bob")
        world.add_character(char_a)
        world.add_character(char_b)

        result = EventSystem().event_marriage(char_a, char_b, world, rng=random.Random(3))
        assert result.event_type == "romance"
        assert "関係を深めた" in result.description

        summary_key, rendered = _save_load_render(result, world, tmp_path, location_id=char_a.location_id)

        assert summary_key == "events.romance_growing_closer.summary"
        assert rendered == "Alice and Bob spent time together at Aethoria Capital, growing closer."
    finally:
        set_locale(previous_locale)

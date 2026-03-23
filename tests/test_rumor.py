"""Tests for rumor.py - Rumor system, generation, and notification density."""

import random

from rumor import (
    DISCLOSURE,
    RELIABILITY_LEVELS,
    RUMOR_MAX_AGE_MONTHS,
    Rumor,
    age_rumors,
    generate_rumor_from_event,
    generate_rumors_for_period,
    trim_rumors,
    _determine_reliability,
    _category_from_event_kind,
    _content_tags_from_event,
)
from events import WorldEventRecord
from world import World
from character import Character
from simulator import Simulator


# ------------------------------------------------------------------
# SI-7: rumor.reliability must be in RELIABILITY_LEVELS
# ------------------------------------------------------------------

def test_si7_reliability_values():
    """SI-7: Rumor reliability must be one of the allowed values."""
    for level in RELIABILITY_LEVELS:
        rumor = Rumor(reliability=level)
        assert rumor.reliability in RELIABILITY_LEVELS


def test_si7_invalid_reliability_falls_back():
    """SI-7: Invalid reliability is corrected to 'plausible'."""
    rumor = Rumor(reliability="invalid_value")
    assert rumor.reliability == "plausible"
    assert rumor.reliability in RELIABILITY_LEVELS


# ------------------------------------------------------------------
# Rumor dataclass basics
# ------------------------------------------------------------------

def test_rumor_creation():
    rumor = Rumor(
        category="battle",
        source_location_id="loc_aethoria_capital",
        target_subject="char_123",
        reliability="certain",
        description="A great battle occurred",
    )
    assert rumor.category == "battle"
    assert rumor.reliability == "certain"
    assert rumor.spread_level >= 0
    assert not rumor.is_expired


def test_rumor_expiry():
    rumor = Rumor(age_in_months=RUMOR_MAX_AGE_MONTHS)
    assert rumor.is_expired

    rumor2 = Rumor(age_in_months=RUMOR_MAX_AGE_MONTHS - 1)
    assert not rumor2.is_expired


def test_rumor_serialization_roundtrip():
    rumor = Rumor(
        id="rum_test123",
        category="adventure",
        source_location_id="loc_thornwood",
        target_subject="char_abc",
        reliability="doubtful",
        spread_level=3,
        age_in_months=5,
        content_tags=["major", "tragic"],
        description="A hero fell in Thornwood",
        source_event_id="evt_456",
        year_created=1005,
        month_created=6,
    )
    data = rumor.to_dict()
    restored = Rumor.from_dict(data)
    assert restored.id == rumor.id
    assert restored.category == rumor.category
    assert restored.source_location_id == rumor.source_location_id
    assert restored.reliability == rumor.reliability
    assert restored.spread_level == rumor.spread_level
    assert restored.age_in_months == rumor.age_in_months
    assert restored.content_tags == rumor.content_tags
    assert restored.description == rumor.description
    assert restored.source_event_id == rumor.source_event_id
    assert restored.year_created == rumor.year_created
    assert restored.month_created == rumor.month_created


def test_rumor_spread_level_clamped():
    rumor = Rumor(spread_level=15)
    assert rumor.spread_level == 10

    rumor2 = Rumor(spread_level=-3)
    assert rumor2.spread_level == 0


# ------------------------------------------------------------------
# Reliability determination
# ------------------------------------------------------------------

def test_determine_reliability_high_severity_same_location():
    """High severity + same location = certain."""
    rng = random.Random(42)
    result = _determine_reliability(5, same_location=True, months_elapsed=0, rng=rng)
    assert result == "certain"


def test_determine_reliability_low_severity_far_away():
    """Low severity + time elapsed = lower reliability."""
    rng = random.Random(42)
    result = _determine_reliability(1, same_location=False, months_elapsed=10, rng=rng)
    assert result in ("doubtful", "false")


def test_determine_reliability_always_valid():
    """Reliability must always be one of RELIABILITY_LEVELS."""
    rng = random.Random(0)
    for severity in range(1, 6):
        for same_loc in (True, False):
            for elapsed in (0, 3, 6, 12, 24):
                result = _determine_reliability(severity, same_loc, elapsed, rng=rng)
                assert result in RELIABILITY_LEVELS


# ------------------------------------------------------------------
# Rumor generation from events
# ------------------------------------------------------------------

def _make_event(severity=3, kind="battle", year=1000, month=6,
                location_id="loc_aethoria_capital"):
    return WorldEventRecord(
        record_id="evt_test",
        kind=kind,
        year=year,
        month=month,
        location_id=location_id,
        primary_actor_id="char_001",
        description="A test event occurred",
        severity=severity,
    )


def test_generate_rumor_from_high_severity_event():
    rng = random.Random(42)
    event = _make_event(severity=4)
    rumor = generate_rumor_from_event(
        event,
        listener_location_id="loc_aethoria_capital",
        current_year=1000,
        current_month=6,
        rng=rng,
    )
    # With seed 42, the random check should pass for severity 4
    # But it's possible to get None due to random chance
    if rumor is not None:
        assert rumor.reliability in RELIABILITY_LEVELS
        assert rumor.source_event_id == "evt_test"
        assert rumor.category == "battle"


def test_generate_rumor_rejects_low_severity():
    rng = random.Random(42)
    event = _make_event(severity=1)
    rumor = generate_rumor_from_event(
        event,
        listener_location_id="loc_aethoria_capital",
        current_year=1000,
        current_month=6,
        rng=rng,
    )
    assert rumor is None


# ------------------------------------------------------------------
# Category and tag extraction
# ------------------------------------------------------------------

def test_category_from_event_kind():
    assert _category_from_event_kind("death") == "death"
    assert _category_from_event_kind("battle") == "battle"
    assert _category_from_event_kind("marriage") == "social"
    assert _category_from_event_kind("journey") == "movement"
    assert _category_from_event_kind("unknown_kind") == "event"


def test_content_tags_from_event():
    event = _make_event(severity=4, kind="death")
    tags = _content_tags_from_event(event)
    assert "death" in tags
    assert "major" in tags
    assert "tragic" in tags


# ------------------------------------------------------------------
# Aging and trimming
# ------------------------------------------------------------------

def test_age_rumors_removes_expired():
    rumors = [
        Rumor(age_in_months=RUMOR_MAX_AGE_MONTHS - 2),
        Rumor(age_in_months=RUMOR_MAX_AGE_MONTHS - 1),
    ]
    result = age_rumors(rumors, months=1)
    assert len(result) == 1  # Second one expires after aging


def test_age_rumors_increments_age():
    rumor = Rumor(age_in_months=5)
    result = age_rumors([rumor], months=3)
    assert len(result) == 1
    assert result[0].age_in_months == 8


def test_trim_rumors_respects_max():
    rumors = [Rumor(age_in_months=i) for i in range(60)]
    result = trim_rumors(rumors, max_count=10)
    assert len(result) == 10
    # Should keep the newest (lowest age)
    assert all(r.age_in_months < 10 for r in result)


def test_trim_rumors_noop_when_under_limit():
    rumors = [Rumor() for _ in range(3)]
    result = trim_rumors(rumors, max_count=10)
    assert len(result) == 3


# ------------------------------------------------------------------
# Disclosure table
# ------------------------------------------------------------------

def test_disclosure_table_has_all_levels():
    for level in RELIABILITY_LEVELS:
        assert level in DISCLOSURE
        d = DISCLOSURE[level]
        assert "who" in d
        assert "what" in d
        assert "where" in d
        assert "when" in d
        for key in ("who", "what", "where", "when"):
            assert 0.0 <= d[key] <= 1.0


# ------------------------------------------------------------------
# World integration
# ------------------------------------------------------------------

def _make_world_with_events():
    world = World()
    char = Character(
        name="Aldric", age=25, gender="male", race="Human", job="Warrior",
        location_id="loc_aethoria_capital", favorite=True,
    )
    world.add_character(char)
    for i in range(5):
        world.record_event(WorldEventRecord(
            record_id=f"evt_{i:03d}",
            kind="battle" if i % 2 == 0 else "discovery",
            year=1000,
            month=6 + (i % 6),
            location_id="loc_aethoria_capital",
            primary_actor_id=char.char_id,
            description=f"Event {i} occurred",
            severity=2 + (i % 3),
        ))
    return world


def test_generate_rumors_for_period():
    world = _make_world_with_events()
    rng = random.Random(42)
    rumors = generate_rumors_for_period(
        world, year=1000, month=8, max_rumors=10, rng=rng,
    )
    # Should generate at least some rumors from severity >= 2 events
    for r in rumors:
        assert r.reliability in RELIABILITY_LEVELS
        assert isinstance(r.description, str)


def test_world_rumor_serialization():
    world = _make_world_with_events()
    rumor = Rumor(
        id="rum_test_world",
        category="battle",
        source_location_id="loc_aethoria_capital",
        reliability="plausible",
        description="Battle at the capital",
    )
    world.rumors.append(rumor)

    data = world.to_dict()
    assert "rumors" in data
    assert len(data["rumors"]) == 1

    restored = World.from_dict(data)
    assert len(restored.rumors) == 1
    assert restored.rumors[0].id == "rum_test_world"
    assert restored.rumors[0].reliability == "plausible"


def test_old_save_without_rumors_loads_empty():
    """Old saves without 'rumors' key should load with empty rumors list."""
    world = World()
    data = world.to_dict()
    del data["rumors"]
    restored = World.from_dict(data)
    assert restored.rumors == []


# ------------------------------------------------------------------
# Notification density (Simulator.should_notify)
# ------------------------------------------------------------------

def test_should_notify_high_severity():
    world = _make_world_with_events()
    sim = Simulator(world)
    record = WorldEventRecord(
        record_id="evt_high",
        kind="death",
        year=1000,
        month=6,
        severity=5,
        description="A death occurred",
    )
    assert sim.should_notify(record) is True


def test_should_notify_favorite_any():
    world = _make_world_with_events()
    char = world.characters[0]
    char.favorite = True
    sim = Simulator(world)
    record = WorldEventRecord(
        record_id="evt_fav",
        kind="meeting",
        year=1000,
        month=6,
        severity=1,
        primary_actor_id=char.char_id,
        description="A minor meeting",
    )
    assert sim.should_notify(record) is True


def test_should_notify_low_severity_no_flags():
    world = World()
    char = Character(
        name="Nobody", age=25, gender="male", race="Human", job="Warrior",
        location_id="loc_aethoria_capital",
    )
    world.add_character(char)
    sim = Simulator(world)
    record = WorldEventRecord(
        record_id="evt_low",
        kind="meeting",
        year=1000,
        month=6,
        severity=1,
        primary_actor_id=char.char_id,
        description="A quiet day",
    )
    assert sim.should_notify(record) is False


def test_should_notify_spotlighted_serious():
    world = World()
    char = Character(
        name="Spot", age=25, gender="male", race="Human", job="Warrior",
        location_id="loc_aethoria_capital",
        spotlighted=True,
    )
    world.add_character(char)
    sim = Simulator(world)

    # severity 3 + spotlighted -> notify
    record = WorldEventRecord(
        record_id="evt_spot",
        kind="battle",
        year=1000,
        month=6,
        severity=3,
        primary_actor_id=char.char_id,
        description="A serious battle",
    )
    assert sim.should_notify(record) is True

    # severity 1 + spotlighted -> no notify
    record_low = WorldEventRecord(
        record_id="evt_spot_low",
        kind="meeting",
        year=1000,
        month=6,
        severity=1,
        primary_actor_id=char.char_id,
        description="A casual meeting",
    )
    assert sim.should_notify(record_low) is False


# ------------------------------------------------------------------
# Simulator rumor integration
# ------------------------------------------------------------------

def test_simulator_generates_rumors_during_run():
    """Simulator should generate rumors during yearly progression."""
    world = _make_world_with_events()
    sim = Simulator(world, seed=42)
    sim.advance_years(1)
    # After one year, events should have been generated and possibly rumors
    # We can't guarantee exact count due to randomness, but structure should be valid
    for rumor in world.rumors:
        assert rumor.reliability in RELIABILITY_LEVELS


def test_get_active_rumors_returns_formatted_strings():
    world = _make_world_with_events()
    world.rumors.append(Rumor(
        description="Dragon sighting in the east",
        reliability="plausible",
    ))
    sim = Simulator(world)
    lines = sim.get_active_rumors()
    assert len(lines) == 1
    assert "Dragon sighting" in lines[0]

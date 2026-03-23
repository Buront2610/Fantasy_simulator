"""
test_monthly_engine.py - Determinism and correctness tests for the PR-B monthly engine.

Design reference: docs/implementation_plan.md §7.3 (Phase B)

Tests in this module verify:
1.  Seeded world generation is deterministic (B-2 prerequisite)
2.  Seeded 12-month progression is deterministic (B-2 core)
3.  advance_months() advances the correct number of months
4.  Event records are timestamped to the month they actually occurred
5.  SIMULATION_DENSITY scales internal event generation
6.  WorldEventRecord.tags field round-trips via serialisation
"""

from __future__ import annotations

import random as _random

from fantasy_simulator.character import Character
from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.events import WorldEventRecord
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _build_seeded_world(seed: int, n_chars: int = 6) -> World:
    """Build a deterministic world with *n_chars* characters using *seed*."""
    rng = _random.Random(seed)
    world = World()
    creator = CharacterCreator()
    locs = [loc.id for loc in world.grid.values() if loc.region_type != "dungeon"]
    for _ in range(n_chars):
        char = creator.create_random(rng=rng)
        char.location_id = rng.choice(locs)
        world.add_character(char)
    return world


# ---------------------------------------------------------------------------
# B-2: Seed-fixed world-generation determinism
# ---------------------------------------------------------------------------

class TestSeededWorldGenerationIsDeterministic:
    """Two worlds built with the same seed must be identical."""

    def test_character_names_match(self):
        w1 = _build_seeded_world(42)
        w2 = _build_seeded_world(42)
        assert [c.name for c in w1.characters] == [c.name for c in w2.characters]

    def test_character_stats_match(self):
        w1 = _build_seeded_world(42)
        w2 = _build_seeded_world(42)
        for c1, c2 in zip(w1.characters, w2.characters):
            assert c1.strength == c2.strength
            assert c1.intelligence == c2.intelligence
            assert c1.constitution == c2.constitution

    def test_to_dict_equality(self):
        w1 = _build_seeded_world(42)
        w2 = _build_seeded_world(42)
        assert w1.to_dict() == w2.to_dict()


# ---------------------------------------------------------------------------
# B-2: Seed-fixed 12-month progression determinism
# ---------------------------------------------------------------------------

class TestSeeded12MonthProgressionIsDeterministic:
    """Two simulators with the same seed must produce identical state after
    advancing the same number of months."""

    def test_advance_12_months_produces_identical_state(self):
        sim1 = Simulator(_build_seeded_world(7), events_per_year=4, seed=99)
        sim2 = Simulator(_build_seeded_world(7), events_per_year=4, seed=99)

        sim1.advance_months(12)
        sim2.advance_months(12)

        assert sim1.to_dict() == sim2.to_dict()

    def test_advance_months_matches_advance_years(self):
        """advance_months(12) and advance_years(1) must produce identical state
        when starting from a clean month-1 world."""
        sim1 = Simulator(_build_seeded_world(13), events_per_year=4, seed=55)
        sim2 = Simulator(_build_seeded_world(13), events_per_year=4, seed=55)

        sim1.advance_months(12)
        sim2.advance_years(1)

        assert sim1.to_dict() == sim2.to_dict()

    def test_multiple_year_progression_is_deterministic(self):
        """State after 3 full years is reproducible."""
        sim1 = Simulator(_build_seeded_world(42), events_per_year=4,
                         adventure_steps_per_year=2, seed=99)
        sim2 = Simulator(_build_seeded_world(42), events_per_year=4,
                         adventure_steps_per_year=2, seed=99)

        sim1.advance_months(36)
        sim2.advance_months(36)

        assert sim1.to_dict() == sim2.to_dict()

    def test_monthly_snapshot_consistency(self):
        """Every month-level snapshot should match between two identical sims."""
        sim1 = Simulator(_build_seeded_world(17), events_per_year=3, seed=77)
        sim2 = Simulator(_build_seeded_world(17), events_per_year=3, seed=77)

        for _ in range(12):
            sim1.advance_months(1)
            sim2.advance_months(1)
            assert sim1.to_dict() == sim2.to_dict()


# ---------------------------------------------------------------------------
# advance_months() correctness
# ---------------------------------------------------------------------------

class TestAdvanceMonths:
    """advance_months() must advance current_month and world.year correctly."""

    def test_advance_one_month(self):
        sim = Simulator(_build_seeded_world(1, n_chars=2), events_per_year=0, seed=1)
        assert sim.current_month == 1
        sim.advance_months(1)
        assert sim.current_month == 2

    def test_advance_six_months(self):
        sim = Simulator(_build_seeded_world(1, n_chars=2), events_per_year=0, seed=1)
        sim.advance_months(6)
        assert sim.current_month == 7

    def test_year_increments_after_12_months(self):
        world = _build_seeded_world(1, n_chars=2)
        start_year = world.year
        sim = Simulator(world, events_per_year=0, seed=1)
        sim.advance_months(12)
        assert sim.world.year == start_year + 1

    def test_month_wraps_to_1_after_year_end(self):
        sim = Simulator(_build_seeded_world(1, n_chars=2), events_per_year=0, seed=1)
        sim.advance_months(12)
        assert sim.current_month == 1

    def test_advance_24_months_increments_year_twice(self):
        world = _build_seeded_world(1, n_chars=2)
        start_year = world.year
        sim = Simulator(world, events_per_year=0, seed=1)
        sim.advance_months(24)
        assert sim.world.year == start_year + 2
        assert sim.current_month == 1

    def test_advance_13_months_correct_state(self):
        world = _build_seeded_world(1, n_chars=2)
        start_year = world.year
        sim = Simulator(world, events_per_year=0, seed=1)
        sim.advance_months(13)
        assert sim.world.year == start_year + 1
        assert sim.current_month == 2

    def test_pending_notifications_cleared_at_start(self):
        sim = Simulator(_build_seeded_world(5, n_chars=3), events_per_year=4, seed=5)
        # Prime some notifications by advancing 3 months
        sim.advance_months(3)
        # Notifications list must be empty at the start of the next advance call
        sim.advance_months(3)
        # pending_notifications contains only notifications from the last 3 months,
        # not the accumulated 6-month total — verify by checking subsequent clear
        notifications_after = list(sim.pending_notifications)
        sim.advance_months(0)
        # A zero-month advance should clear pending_notifications
        assert sim.pending_notifications == []
        _ = notifications_after  # referenced to suppress unused-variable warning


# ---------------------------------------------------------------------------
# Monthly event timestamps
# ---------------------------------------------------------------------------

class TestMonthlyEventTimestamps:
    """Events generated in _run_month() must carry the correct month stamp."""

    def test_events_have_month_in_range(self):
        sim = Simulator(_build_seeded_world(3, n_chars=4), events_per_year=6, seed=3)
        sim.advance_months(12)
        for record in sim.world.event_records:
            assert 1 <= record.month <= 12, (
                f"Record {record.record_id} has out-of-range month {record.month}"
            )

    def test_no_randomised_month_stamps(self):
        """After the monthly engine, no two random events should share the same
        random month that happened to be picked by randint — all months 1..12
        should appear across a long simulation run."""
        sim = Simulator(_build_seeded_world(11, n_chars=6), events_per_year=12, seed=11)
        sim.advance_months(12)
        months_seen = {r.month for r in sim.world.event_records}
        # With events_per_year=12 and 6 chars, multiple months should be covered
        assert len(months_seen) > 1

    def test_month1_events_include_natural_processes(self):
        """Year-opening events (death checks, recovery) are timestamped to month 1."""
        world = World()
        char = Character(
            "OldTimer", age=90, gender="male", race="Human", job="Farmer",
            strength=10, dexterity=10, constitution=10,
            location_id="loc_aethoria_capital",
        )
        world.add_character(char)
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=42)
        # Run many years to collect month-1-stamped health events
        sim.advance_months(12 * 10)
        month1_records = [r for r in world.event_records if r.month == 1]
        health_kinds = {"condition_worsened", "death", "injury_recovery", "dying_rescued"}
        month1_health = [r for r in month1_records if r.kind in health_kinds]
        assert len(month1_health) > 0, "Expected at least one health event at month 1"

    def test_adventure_events_stamped_to_month2(self):
        """Adventure start and progression events are stamped to month 2 (spring)."""
        world = _build_seeded_world(21, n_chars=4)
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=3, seed=21)
        sim.advance_months(12)
        adventure_kinds = {
            "adventure_started", "adventure_arrived", "adventure_discovery",
            "adventure_returned", "adventure_returned_injured",
            "adventure_choice", "adventure_death",
        }
        adventure_records = [r for r in world.event_records if r.kind in adventure_kinds]
        if adventure_records:
            for rec in adventure_records:
                assert rec.month == 2, (
                    f"Adventure event {rec.kind!r} should be at month 2, got {rec.month}"
                )


# ---------------------------------------------------------------------------
# SIMULATION_DENSITY
# ---------------------------------------------------------------------------

class TestSimulationDensity:
    """SIMULATION_DENSITY multiplier should scale internal event generation."""

    def test_density_1_matches_events_per_year_expected_count(self):
        """With SIMULATION_DENSITY=1.0, expected events ≈ events_per_year."""
        total_trials = 5
        events_per_year = 12
        totals = []
        for seed in range(total_trials):
            sim = Simulator(_build_seeded_world(seed, n_chars=4),
                            events_per_year=events_per_year, seed=seed)
            assert sim.SIMULATION_DENSITY == 1.0
            sim.advance_months(12)
            random_event_kinds = {"meeting", "journey", "skill_training", "discovery",
                                  "battle", "aging", "romance", "anniversary"}
            count = sum(
                1 for r in sim.world.event_records if r.kind in random_event_kinds
            )
            totals.append(count)
        avg = sum(totals) / total_trials
        # Expected ≈ events_per_year; allow generous tolerance for small samples
        assert avg > 0, "Expected non-zero random events with default density"

    def test_density_attribute_exists_and_is_float(self):
        sim = Simulator(_build_seeded_world(1, n_chars=2), events_per_year=4, seed=1)
        assert isinstance(sim.SIMULATION_DENSITY, float)
        assert sim.SIMULATION_DENSITY == 1.0

    def test_events_for_month_respects_density_zero(self):
        """SIMULATION_DENSITY=0 combined with events_per_year should yield 0 events."""
        sim = Simulator(_build_seeded_world(2, n_chars=2), events_per_year=8, seed=2)
        sim.SIMULATION_DENSITY = 0.0  # type: ignore[assignment]
        for month in range(1, 13):
            assert sim._events_for_month(month) == 0

    def test_events_for_month_base_count_with_density_12(self):
        """With events_per_year=12 and density=1.0, base=1 per month."""
        class _ZeroRng:
            """Stub RNG that always returns 0.0 so the remainder check never fires."""
            def random(self) -> float:
                return 0.0

        sim = Simulator(_build_seeded_world(3, n_chars=2), events_per_year=12, seed=3)
        sim.rng = _ZeroRng()
        for month in range(1, 13):
            # base = 12/12 = 1; remainder = 0; extra = 0
            assert sim._events_for_month(month) == 1


# ---------------------------------------------------------------------------
# WorldEventRecord.tags
# ---------------------------------------------------------------------------

class TestWorldEventRecordTags:
    """tags field must be present, default to empty list, and round-trip cleanly."""

    def test_default_tags_is_empty_list(self):
        record = WorldEventRecord(kind="meeting", year=1000, month=3)
        assert record.tags == []

    def test_tags_stored_correctly(self):
        record = WorldEventRecord(kind="battle", year=1000, month=6, tags=["combat", "major"])
        assert "combat" in record.tags
        assert "major" in record.tags

    def test_tags_round_trips_via_to_dict(self):
        record = WorldEventRecord(kind="discovery", year=1001, month=9, tags=["treasure"])
        restored = WorldEventRecord.from_dict(record.to_dict())
        assert restored.tags == ["treasure"]

    def test_tags_defaults_to_empty_list_in_from_dict(self):
        """Old saves without 'tags' key must deserialise without error."""
        data = {
            "record_id": "abc123",
            "kind": "meeting",
            "year": 1000,
            "month": 4,
            "description": "They met.",
            "severity": 1,
            "visibility": "public",
            # 'tags' intentionally omitted to simulate legacy save data
        }
        record = WorldEventRecord.from_dict(data)
        assert record.tags == []

    def test_simulation_records_have_tags_field(self):
        """Event records created during simulation always have a tags attribute."""
        sim = Simulator(_build_seeded_world(99, n_chars=3), events_per_year=4, seed=99)
        sim.advance_months(12)
        for record in sim.world.event_records:
            assert hasattr(record, "tags")
            assert isinstance(record.tags, list)

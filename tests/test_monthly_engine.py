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
        # Inject a synthetic notification so we can verify clearing
        sim.pending_notifications.append(
            WorldEventRecord(kind="test_marker", year=1000, month=1)
        )
        assert len(sim.pending_notifications) == 1
        # Any advance_months() call must clear pending_notifications at entry
        sim.advance_months(0)
        assert sim.pending_notifications == []


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
        """After the monthly engine, events should be spread across multiple months
        rather than all sharing a single randomly-chosen month."""
        sim = Simulator(_build_seeded_world(11, n_chars=6), events_per_year=12, seed=11)
        sim.advance_months(12)
        months_seen = {r.month for r in sim.world.event_records}
        # With events_per_year=12 and 6 chars, at least 4 distinct months should
        # appear (health events at 1, recovery at 2, adventure at 3, random events)
        assert len(months_seen) >= 4, (
            f"Expected broad month coverage, got only months {sorted(months_seen)}"
        )

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

    def test_adventure_events_stamped_to_month3(self):
        """Adventure start and progression events are stamped to month 3 (spring)."""
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
                assert rec.month == 3, (
                    f"Adventure event {rec.kind!r} should be at month 3, got {rec.month}"
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
        # Expected ≈ events_per_year; use a wide band so randomness does not
        # cause flaky failures.
        lower_bound = 0.5 * events_per_year
        upper_bound = 1.5 * events_per_year
        assert lower_bound <= avg <= upper_bound, (
            f"Average random event count {avg} not within expected range "
            f"[{lower_bound}, {upper_bound}] for events_per_year={events_per_year}"
        )

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


# ---------------------------------------------------------------------------
# Monthly auto-pause
# ---------------------------------------------------------------------------

class TestMonthlyAutoPause:
    """advance_until_pause() should now operate at monthly granularity,
    pausing at the exact month a condition occurs rather than waiting
    until the end of the year."""

    def test_dying_char_pauses_immediately(self):
        """A dying character should cause auto-pause before the year ends."""
        world = World(name="TestWorld", year=1000)
        char = Character(
            "Fragile", age=25, gender="male", race="Human", job="Warrior",
            strength=50, dexterity=50, constitution=50,
            char_id="frag_01",
        )
        char.injury_status = "dying"
        world.add_character(char)
        sim = Simulator(world, events_per_year=0, seed=1)
        result = sim.advance_until_pause(max_years=3)
        # Preexisting dying condition should pause immediately (0 months)
        assert result["months_advanced"] == 0
        assert result["pause_reason"] == "dying_any"

    def test_auto_pause_returns_months_advanced(self):
        """Result dict must include months_advanced and years_advanced."""
        sim = Simulator(_build_seeded_world(7, n_chars=3), events_per_year=4, seed=7)
        result = sim.advance_until_pause(max_years=1)
        assert "months_advanced" in result
        assert "years_advanced" in result
        assert result["months_advanced"] >= 1

    def test_auto_pause_mid_year_does_not_complete_year(self):
        """A very old, low-constitution character must trigger dying_any
        before 5 years elapse — the auto-pause should fire mid-year."""
        world = World(name="TestWorld", year=1000)
        char = Character(
            "Doomed", age=95, gender="male", race="Human", job="Farmer",
            strength=10, dexterity=10, constitution=10,
            char_id="doomed_01",
        )
        world.add_character(char)
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=0, seed=42)
        result = sim.advance_until_pause(max_years=5)
        # With seed=42, age=95, constitution=10, the character reliably
        # degrades to "dying" within 5 years, triggering dying_any.
        assert result["pause_reason"] == "dying_any", (
            f"Expected dying_any but got {result['pause_reason']}"
        )

    def test_pending_decision_pauses_at_month_3(self):
        """Pending adventure choices should trigger pause at month 3 (spring)."""
        from fantasy_simulator.adventure import AdventureChoice, AdventureRun
        world = World(name="TestWorld", year=1000)
        char = Character(
            "Adventurer", age=25, gender="male", race="Human", job="Warrior",
            strength=50, dexterity=50, constitution=50,
            char_id="adv_01",
        )
        world.add_character(char)
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=3, seed=1)
        # Inject active adventure with pending choice
        run = AdventureRun(
            character_id="adv_01",
            character_name="Adventurer",
            origin="loc_aethoria_capital",
            destination="loc_thornwood",
            year_started=1000,
            adventure_id="adv_test_pause",
        )
        run.pending_choice = AdventureChoice(
            prompt="Test?",
            options=["press_on", "retreat"],
            default_option="retreat",
            context="approach",
        )
        world.add_adventure(run)
        result = sim.advance_until_pause(max_years=1)
        assert result["months_advanced"] == 0
        assert result["pause_reason"] == "pending_decision"


# ---------------------------------------------------------------------------
# Mid-year save/load consistency
# ---------------------------------------------------------------------------

class TestMidYearSaveLoad:
    """Saving and loading mid-year should preserve month state and produce
    consistent subsequent simulation."""

    def test_mid_year_save_preserves_current_month(self):
        from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
        sim = Simulator(_build_seeded_world(10, n_chars=3), events_per_year=4, seed=10)
        sim.advance_months(5)
        assert sim.current_month == 6
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_simulation(sim, path)
            restored = load_simulation(path)
            assert restored.current_month == 6
        finally:
            os.unlink(path)

    def test_mid_year_save_load_continues_deterministically(self):
        """After saving at month 6, loading and continuing should produce
        the same state as running without interruption."""
        from fantasy_simulator.persistence.save_load import load_simulation, save_simulation
        import tempfile
        import os
        # Run 1: straight through 12 months
        sim1 = Simulator(_build_seeded_world(22, n_chars=3), events_per_year=2, seed=22)
        sim1.advance_months(12)
        state_full = sim1.to_dict()

        # Run 2: save at month 6, load, continue to month 12
        sim2 = Simulator(_build_seeded_world(22, n_chars=3), events_per_year=2, seed=22)
        sim2.advance_months(5)
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        try:
            save_simulation(sim2, path)
            restored = load_simulation(path)
            restored.advance_months(7)
            state_resumed = restored.to_dict()
        finally:
            os.unlink(path)

        assert state_full == state_resumed

    def test_advance_years_from_mid_year_does_not_replay_early_months(self):
        """advance_years() from current_month=6 should advance exactly 12 months
        from that position, not restart from month 1 in the same year."""
        sim = Simulator(_build_seeded_world(33, n_chars=2), events_per_year=0, seed=33)
        sim.advance_months(5)
        assert sim.current_month == 6
        start_year = sim.world.year
        sim.advance_years(1)
        # advance_years(1) = advance_months(12). From month 6:
        # 6→7→8→9→10→11→12 (year+1) →1→2→3→4→5 → current_month = 6
        assert sim.current_month == 6
        assert sim.world.year == start_year + 1


# ---------------------------------------------------------------------------
# Adventure month / season alignment
# ---------------------------------------------------------------------------

class TestAdventureSeasonAlignment:
    """Adventure events must occur at month 3 (spring), not month 2 (winter)."""

    def test_month_3_is_spring(self):
        assert World.get_season(3) == "spring"

    def test_month_2_is_winter(self):
        assert World.get_season(2) == "winter"

    def test_adventure_starts_in_spring(self):
        """Adventures should start at month 3 which is spring, matching the
        seasonal modifier expectations for safer travel."""
        world = _build_seeded_world(55, n_chars=4)
        sim = Simulator(world, events_per_year=0, adventure_steps_per_year=3, seed=55)
        # Run several years to ensure at least one adventure starts
        sim.advance_months(12 * 5)
        adventure_kinds = {"adventure_started", "adventure_arrived", "adventure_discovery",
                           "adventure_returned"}
        adventure_records = [r for r in world.event_records if r.kind in adventure_kinds]
        if adventure_records:
            for rec in adventure_records:
                assert rec.month == 3, (
                    f"Adventure event {rec.kind} at month {rec.month}, expected 3 (spring)"
                )

    def test_spring_modifiers_active_during_adventure(self):
        """Spring seasonal modifiers should be active when adventures process."""
        world = World(name="TestWorld", year=1000)
        sim = Simulator(world, events_per_year=0, seed=1)
        applied_seasons = []
        original_apply = sim._apply_seasonal_modifiers

        def _tracking_apply(month):
            applied_seasons.append((month, world.get_season(month)))
            return original_apply(month)

        sim._apply_seasonal_modifiers = _tracking_apply
        sim.advance_months(12)
        # Month 3 should have spring modifiers
        month3_seasons = [(m, s) for m, s in applied_seasons if m == 3]
        assert month3_seasons
        assert month3_seasons[0][1] == "spring"


# ---------------------------------------------------------------------------
# Event log monthly prefix
# ---------------------------------------------------------------------------

class TestEventLogMonthlyPrefix:
    """Event log entries should now include month information for player
    visibility of monthly causality."""

    def test_event_log_entries_contain_month(self):
        """After advancing with events, log entries should contain month info."""
        from fantasy_simulator.i18n import set_locale, get_locale
        prev = get_locale()
        set_locale("en")
        try:
            sim = Simulator(_build_seeded_world(44, n_chars=4), events_per_year=6, seed=44)
            sim.advance_months(12)
            # At least some entries should have month prefix
            month_entries = [e for e in sim.world.event_log if "Month" in e]
            assert len(month_entries) > 0, (
                "Expected at least some event log entries with month prefix"
            )
        finally:
            set_locale(prev)

    def test_event_log_month_prefix_in_japanese(self):
        """Japanese locale should show month as 月."""
        from fantasy_simulator.i18n import set_locale, get_locale
        prev = get_locale()
        set_locale("ja")
        try:
            sim = Simulator(_build_seeded_world(45, n_chars=4), events_per_year=6, seed=45)
            sim.advance_months(12)
            month_entries = [e for e in sim.world.event_log if "月]" in e]
            assert len(month_entries) > 0, (
                "Expected at least some event log entries with 月 prefix"
            )
        finally:
            set_locale(prev)

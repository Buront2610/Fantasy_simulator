"""Tests for PR-C: simulation/ sub-package split and event store normalization.

Verifies:
- simulation/ sub-package imports work correctly
- Backward-compatible import from simulator.py still works
- WorldEventRecord.impacts field is populated by event recording
- events_by_kind() reads from event_records (canonical source)
- World.apply_event_impact() returns impact data
- _record_world_event() vs _record_event() store-coverage gap
- Old save data without impacts field loads safely
"""

import random

from fantasy_simulator.character_creator import CharacterCreator
from fantasy_simulator.world import World


def _first_location_id(world):
    """Return a valid location_id from the world using the public grid API."""
    return next(iter(world.grid.values())).id


def _make_sim(seed=42):
    """Create a Simulator with an empty seeded World for deterministic testing.

    The World has no characters by default, which is intentional for tests
    that verify structural behavior (imports, serialization, impact tracking).
    Tests that need events to be generated should add characters explicitly.
    """
    from fantasy_simulator.simulation import Simulator
    world = World()
    return Simulator(world, events_per_year=12, seed=seed)


def _make_sim_with_characters(n_chars=6, seed=42):
    """Create a Simulator with *n_chars* random characters for event testing.

    Characters are assigned to non-dungeon locations so that random-event
    generation can actually fire.
    """
    from fantasy_simulator.simulation import Simulator
    world = World()
    creator = CharacterCreator()
    rng = random.Random(seed)
    locs = [loc.id for loc in world.grid.values() if loc.region_type != "dungeon"]
    for i in range(n_chars):
        c = creator.create_random(name=f"Hero{i}", rng=rng)
        c.location_id = locs[i % len(locs)]
        world.add_character(c)
    return Simulator(world, events_per_year=12, seed=seed)


class TestSimulationSubPackageImport:
    """Verify that all public import paths for Simulator work."""

    def test_import_from_simulation_package(self):
        from fantasy_simulator.simulation import Simulator
        assert Simulator is not None

    def test_import_from_simulation_engine(self):
        from fantasy_simulator.simulation.engine import Simulator
        assert Simulator is not None

    def test_import_from_simulator_compat(self):
        from fantasy_simulator.simulator import Simulator
        assert Simulator is not None

    def test_all_paths_resolve_to_same_class(self):
        from fantasy_simulator.simulation import Simulator as A
        from fantasy_simulator.simulation.engine import Simulator as B
        from fantasy_simulator.simulator import Simulator as C
        assert A is B
        assert B is C

    def test_mixin_modules_importable(self):
        from fantasy_simulator.simulation.timeline import TimelineMixin
        from fantasy_simulator.simulation.notifications import NotificationMixin
        from fantasy_simulator.simulation.event_recorder import EventRecorderMixin
        from fantasy_simulator.simulation.adventure_coordinator import AdventureMixin
        from fantasy_simulator.simulation.queries import QueryMixin
        assert TimelineMixin is not None
        assert NotificationMixin is not None
        assert EventRecorderMixin is not None
        assert AdventureMixin is not None
        assert QueryMixin is not None

    def test_simulator_inherits_all_mixins(self):
        from fantasy_simulator.simulation.engine import Simulator
        from fantasy_simulator.simulation.timeline import TimelineMixin
        from fantasy_simulator.simulation.notifications import NotificationMixin
        from fantasy_simulator.simulation.event_recorder import EventRecorderMixin
        from fantasy_simulator.simulation.adventure_coordinator import AdventureMixin
        from fantasy_simulator.simulation.queries import QueryMixin
        assert issubclass(Simulator, TimelineMixin)
        assert issubclass(Simulator, NotificationMixin)
        assert issubclass(Simulator, EventRecorderMixin)
        assert issubclass(Simulator, AdventureMixin)
        assert issubclass(Simulator, QueryMixin)


class TestImpactTracking:
    """Verify WorldEventRecord.impacts field and causal tracking."""

    def test_world_event_record_has_impacts_field(self):
        from fantasy_simulator.events import WorldEventRecord
        rec = WorldEventRecord(kind="battle", description="test")
        assert hasattr(rec, "impacts")
        assert rec.impacts == []

    def test_impacts_serialization_round_trip(self):
        from fantasy_simulator.events import WorldEventRecord
        impacts = [
            {"target_type": "location", "target_id": "loc_1",
             "attribute": "danger", "old_value": 50, "new_value": 55, "delta": 5}
        ]
        rec = WorldEventRecord(kind="battle", description="test", impacts=impacts)
        data = rec.to_dict()
        assert "impacts" in data
        assert len(data["impacts"]) == 1
        restored = WorldEventRecord.from_dict(data)
        assert restored.impacts == impacts

    def test_impacts_default_empty_on_deserialization(self):
        """Old saves without 'impacts' key should load safely with []."""
        from fantasy_simulator.events import WorldEventRecord
        data = {"kind": "battle", "description": "test"}
        rec = WorldEventRecord.from_dict(data)
        assert rec.impacts == []

    def test_apply_event_impact_battle_returns_nonempty(self):
        """'battle' is in _EVENT_IMPACT and must produce actual impact dicts."""
        world = World()
        loc_id = _first_location_id(world)
        location = world.get_location_by_id(loc_id)
        original_danger = location.danger
        impacts = world.apply_event_impact("battle", loc_id)
        assert isinstance(impacts, list)
        assert len(impacts) > 0, "battle should produce at least one impact"
        imp = impacts[0]
        assert "target_type" in imp
        assert "attribute" in imp
        assert "old_value" in imp
        assert "new_value" in imp
        assert "delta" in imp
        assert imp["delta"] == imp["new_value"] - imp["old_value"]
        # Verify the danger attribute was actually changed
        danger_impacts = [i for i in impacts if i["attribute"] == "danger"]
        assert danger_impacts, "battle should impact the danger attribute"
        assert danger_impacts[0]["old_value"] == original_danger

    def test_apply_event_impact_returns_empty_for_none_location(self):
        world = World()
        impacts = world.apply_event_impact("battle", None)
        assert impacts == []

    def test_apply_event_impact_returns_empty_for_unknown_location(self):
        world = World()
        impacts = world.apply_event_impact("battle", "nonexistent_loc_id")
        assert impacts == []

    def test_apply_event_impact_returns_empty_for_unknown_kind(self):
        world = World()
        loc_id = _first_location_id(world)
        impacts = world.apply_event_impact("totally_unknown_kind", loc_id)
        assert impacts == []

    def test_record_world_event_stores_impacts_with_content(self):
        """_record_world_event with 'battle' kind must produce impact dicts."""
        sim = _make_sim()
        loc_id = _first_location_id(sim.world)
        record = sim._record_world_event(
            "A battle occurred",
            kind="battle",
            location_id=loc_id,
        )
        assert record.impacts, "Expected at least one impact for 'battle' event"
        first_impact = record.impacts[0]
        assert first_impact["target_type"] == "location"
        assert first_impact["target_id"] == loc_id
        assert "attribute" in first_impact
        assert "delta" in first_impact
        assert first_impact["delta"] == first_impact["new_value"] - first_impact["old_value"]


class TestEventStoreStoreCoverage:
    """Verify which stores are written by _record_world_event vs _record_event.

    This is the critical gap documented in PR-C review:
    - _record_world_event() -> event_records + event_log, but NOT history
    - _record_event() -> event_records + event_log + history
    """

    def test_record_world_event_writes_event_records_and_event_log(self):
        """_record_world_event populates event_records and event_log."""
        sim = _make_sim()
        loc_id = _first_location_id(sim.world)
        sim._record_world_event(
            "An adventure started",
            kind="adventure_started",
            location_id=loc_id,
        )
        assert len(sim.world.event_records) == 1
        assert sim.world.event_records[0].kind == "adventure_started"
        assert len(sim.world.event_log) == 1
        assert "adventure" in sim.world.event_log[0].lower() or len(sim.world.event_log[0]) > 0

    def test_record_world_event_does_NOT_write_history(self):
        """_record_world_event must NOT populate history — this is intentional."""
        sim = _make_sim()
        loc_id = _first_location_id(sim.world)
        sim._record_world_event(
            "Injury recovery happened",
            kind="injury_recovery",
            location_id=loc_id,
        )
        assert len(sim.history) == 0, (
            "_record_world_event should not write to history; "
            "only _record_event does"
        )

    def test_record_event_writes_to_all_three_stores(self):
        """_record_event populates history, event_records, AND event_log."""
        from fantasy_simulator.events import EventResult
        sim = _make_sim()
        result = EventResult(
            description="A battle took place",
            affected_characters=["char_1"],
            event_type="battle",
            year=sim.world.year,
        )
        sim._record_event(result, location_id=None)
        assert len(sim.history) == 1
        assert sim.history[0].event_type == "battle"
        assert len(sim.world.event_records) == 1
        assert sim.world.event_records[0].kind == "battle"
        assert len(sim.world.event_log) == 1

    def test_events_by_type_excludes_record_world_event_entries(self):
        """events_by_type() only sees events that went through _record_event().

        Events created via _record_world_event() directly (adventure lifecycle,
        injury recovery) are invisible to events_by_type() — this is a known
        limitation documented in the docstring.
        """
        sim = _make_sim()
        loc_id = _first_location_id(sim.world)
        # This goes through _record_world_event only -> not in history
        sim._record_world_event(
            "Adventure started",
            kind="adventure_started",
            location_id=loc_id,
        )
        assert sim.events_by_type("adventure_started") == []
        # But events_by_kind CAN see it
        assert len(sim.events_by_kind("adventure_started")) == 1


class TestEventStoreUnification:
    """Verify event store normalization (C-2) with populated worlds."""

    def test_events_by_kind_returns_actual_results(self):
        """events_by_kind() must find events when characters exist."""
        sim = _make_sim_with_characters(n_chars=6, seed=42)
        sim.advance_months(12)
        # After a full year with 6 characters and 12 events_per_year, there
        # must be at least some events in event_records.
        assert len(sim.world.event_records) > 0, (
            "A full year with 6 characters should produce events"
        )
        # Pick the first event's kind and verify events_by_kind finds it
        first_kind = sim.world.event_records[0].kind
        matches = sim.events_by_kind(first_kind)
        assert len(matches) > 0
        assert all(r.kind == first_kind for r in matches)

    def test_events_by_type_returns_actual_results(self):
        """events_by_type() must find events for types routed via _record_event."""
        sim = _make_sim_with_characters(n_chars=6, seed=42)
        sim.advance_months(12)
        assert len(sim.history) > 0, (
            "A full year with 6 characters should populate history"
        )
        first_type = sim.history[0].event_type
        matches = sim.events_by_type(first_type)
        assert len(matches) > 0
        assert all(ev.event_type == first_type for ev in matches)

    def test_event_records_is_superset_of_history_types(self):
        """event_records should contain all event types from history, plus more."""
        sim = _make_sim_with_characters(n_chars=6, seed=42)
        sim.advance_months(12)
        history_types = {ev.event_type for ev in sim.history}
        record_kinds = {rec.kind for rec in sim.world.event_records}
        # Everything in history must be in event_records
        assert history_types.issubset(record_kinds), (
            f"history types {history_types - record_kinds} not in event_records"
        )
        # event_records may have MORE kinds than history (adventure_started, etc.)

    def test_history_and_event_records_both_populated(self):
        """Both stores should be populated during simulation."""
        sim = _make_sim_with_characters(n_chars=6, seed=42)
        sim.advance_months(12)
        assert len(sim.history) > 0
        assert len(sim.world.event_records) > 0

    def test_event_log_populated_as_display_derived(self):
        """event_log should still be populated for display compatibility."""
        sim = _make_sim_with_characters(n_chars=6, seed=42)
        sim.advance_months(12)
        assert len(sim.world.event_log) > 0

    def test_get_event_log_returns_display_buffer(self):
        """get_event_log() reads from the display-derived buffer."""
        sim = _make_sim_with_characters(n_chars=4, seed=42)
        sim.advance_months(3)
        log = sim.get_event_log()
        assert isinstance(log, list)

    def test_get_event_log_last_n(self):
        """get_event_log(last_n=N) returns exactly N entries when available."""
        sim = _make_sim_with_characters(n_chars=6, seed=42)
        sim.advance_months(12)
        log_all = sim.get_event_log()
        assert len(log_all) > 2, "Need >2 log entries for this test"
        log_2 = sim.get_event_log(last_n=2)
        assert len(log_2) == 2
        assert log_2 == log_all[-2:]


class TestSaveLoadCompatibility:
    """Verify save/load backward compatibility with impacts and old data."""

    def test_serialization_round_trip_with_characters(self):
        """Full round-trip with populated event stores."""
        from fantasy_simulator.simulation import Simulator
        sim = _make_sim_with_characters(n_chars=6, seed=42)
        sim.advance_months(6)
        data = sim.to_dict()
        restored = Simulator.from_dict(data)
        assert restored.current_month == sim.current_month
        assert restored.world.year == sim.world.year
        assert len(restored.history) == len(sim.history)
        assert len(restored.world.event_records) == len(sim.world.event_records)
        assert len(restored.world.event_log) == len(sim.world.event_log)

    def test_old_save_without_impacts_loads_safely(self):
        """Simulate loading a save from before PR-C (no impacts field)."""
        from fantasy_simulator.simulation import Simulator
        import copy
        sim = _make_sim_with_characters(n_chars=4, seed=42)
        sim.advance_months(3)
        data = sim.to_dict()
        # Strip impacts from all event_records to simulate old save
        old_data = copy.deepcopy(data)
        for rec_data in old_data["world"]["event_records"]:
            rec_data.pop("impacts", None)
        restored = Simulator.from_dict(old_data)
        # All records should have empty impacts (safe default)
        for rec in restored.world.event_records:
            assert rec.impacts == [], f"Expected empty impacts, got {rec.impacts}"

    def test_serialization_round_trip_preserves_impacts(self):
        """Impacts recorded during simulation survive save/load."""
        from fantasy_simulator.simulation import Simulator
        sim = _make_sim()
        loc_id = _first_location_id(sim.world)
        # Create an event with known impacts (battle triggers _EVENT_IMPACT)
        sim._record_world_event(
            "A fierce battle", kind="battle", location_id=loc_id,
        )
        assert len(sim.world.event_records) == 1
        original_impacts = sim.world.event_records[0].impacts
        assert len(original_impacts) > 0
        # Round-trip
        data = sim.to_dict()
        restored = Simulator.from_dict(data)
        assert restored.world.event_records[0].impacts == original_impacts

    def test_serialization_round_trip_basic(self):
        """Basic round-trip without characters."""
        sim = _make_sim()
        sim.advance_months(3)
        data = sim.to_dict()
        from fantasy_simulator.simulation import Simulator
        restored = Simulator.from_dict(data)
        assert restored.current_month == sim.current_month
        assert restored.world.year == sim.world.year
        assert len(restored.history) == len(sim.history)


class TestSimulatorFunctionality:
    """Verify core simulation still works after split."""

    def test_advance_months_basic(self):
        sim = _make_sim()
        sim.advance_months(6)
        assert sim.current_month == 7

    def test_advance_years_basic(self):
        sim = _make_sim()
        initial_year = sim.world.year
        sim.advance_years(1)
        assert sim.world.year == initial_year + 1

    def test_run_year_basic(self):
        sim = _make_sim()
        initial_year = sim.world.year
        sim._run_year()
        assert sim.world.year == initial_year + 1

    def test_get_summary(self):
        sim = _make_sim_with_characters(n_chars=4, seed=42)
        sim.advance_months(12)
        summary = sim.get_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_should_notify(self):
        from fantasy_simulator.events import WorldEventRecord
        sim = _make_sim()
        record = WorldEventRecord(kind="death", severity=5, description="Someone died")
        assert sim.should_notify(record) is True

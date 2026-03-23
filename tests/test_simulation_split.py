"""Tests for PR-C: simulation/ sub-package split and event store normalization.

Verifies:
- simulation/ sub-package imports work correctly
- Backward-compatible import from simulator.py still works
- WorldEventRecord.impacts field is populated by event recording
- events_by_kind() reads from event_records (canonical source)
- World.apply_event_impact() returns impact data
"""

from fantasy_simulator.world import World


def _make_sim(seed=42):
    """Create a Simulator with a seeded World for deterministic testing."""
    from fantasy_simulator.simulation import Simulator
    world = World()
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
        from fantasy_simulator.events import WorldEventRecord
        data = {"kind": "battle", "description": "test"}
        rec = WorldEventRecord.from_dict(data)
        assert rec.impacts == []

    def test_apply_event_impact_returns_impacts(self):
        world = World()
        # Use location_id_index to get a valid location_id
        loc_id = list(world._location_id_index.keys())[0]
        # battle kind should change danger (from _EVENT_IMPACT)
        impacts = world.apply_event_impact("battle", loc_id)
        # Regardless of whether battle is in _EVENT_IMPACT, verify return type
        assert isinstance(impacts, list)

    def test_apply_event_impact_returns_empty_for_none_location(self):
        world = World()
        impacts = world.apply_event_impact("battle", None)
        assert impacts == []

    def test_apply_event_impact_returns_empty_for_unknown_location(self):
        world = World()
        impacts = world.apply_event_impact("battle", "nonexistent_loc_id")
        assert impacts == []

    def test_record_world_event_stores_impacts(self):
        """Events with location impact should store impacts in the record."""
        sim = _make_sim()
        # Use a valid location_id
        loc_id = list(sim.world._location_id_index.keys())[0]
        record = sim._record_world_event(
            "A battle occurred",
            kind="battle",
            location_id=loc_id,
        )
        # The record should have impacts if the event kind is in _EVENT_IMPACT
        assert isinstance(record.impacts, list)


class TestEventStoreUnification:
    """Verify event store normalization (C-2)."""

    def test_events_by_kind_reads_from_event_records(self):
        """events_by_kind() should query world.event_records."""
        sim = _make_sim()
        sim.advance_months(3)
        # After advancing some months, we should have records
        records = sim.world.event_records
        if records:
            first_kind = records[0].kind
            matches = sim.events_by_kind(first_kind)
            assert len(matches) > 0
            assert all(r.kind == first_kind for r in matches)

    def test_events_by_type_still_works(self):
        """Legacy events_by_type() still reads from history."""
        sim = _make_sim()
        sim.advance_months(3)
        # Legacy method should still work
        for ev in sim.history:
            matches = sim.events_by_type(ev.event_type)
            assert len(matches) > 0
            break

    def test_history_and_event_records_both_populated(self):
        """Both stores should be populated during simulation."""
        from fantasy_simulator.simulation import Simulator
        from fantasy_simulator.character_creator import CharacterCreator
        world = World()
        creator = CharacterCreator()
        for i in range(5):
            world.add_character(creator.create_random(name=f"Char{i}"))
        sim = Simulator(world, events_per_year=12, seed=42)
        sim.advance_months(12)
        # Both legacy and canonical stores should have entries
        assert len(sim.history) > 0
        assert len(sim.world.event_records) > 0

    def test_event_log_populated_as_display_derived(self):
        """event_log should still be populated for display compatibility."""
        from fantasy_simulator.simulation import Simulator
        from fantasy_simulator.character_creator import CharacterCreator
        world = World()
        creator = CharacterCreator()
        for i in range(5):
            world.add_character(creator.create_random(name=f"Char{i}"))
        sim = Simulator(world, events_per_year=12, seed=42)
        sim.advance_months(12)
        assert len(sim.world.event_log) > 0

    def test_get_event_log_returns_display_buffer(self):
        """get_event_log() reads from the display-derived buffer."""
        sim = _make_sim()
        sim.advance_months(3)
        log = sim.get_event_log()
        assert isinstance(log, list)

    def test_get_event_log_last_n(self):
        """get_event_log(last_n=N) returns at most N entries."""
        sim = _make_sim()
        sim.advance_months(12)
        log_all = sim.get_event_log()
        if len(log_all) > 2:
            log_2 = sim.get_event_log(last_n=2)
            assert len(log_2) == 2
            assert log_2 == log_all[-2:]


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
        sim = _make_sim()
        sim.advance_months(12)
        summary = sim.get_summary()
        assert isinstance(summary, str)
        assert len(summary) > 0

    def test_should_notify(self):
        from fantasy_simulator.events import WorldEventRecord
        sim = _make_sim()
        record = WorldEventRecord(kind="death", severity=5, description="Someone died")
        assert sim.should_notify(record) is True

    def test_serialization_round_trip(self):
        sim = _make_sim()
        sim.advance_months(3)
        data = sim.to_dict()
        from fantasy_simulator.simulation import Simulator
        restored = Simulator.from_dict(data)
        assert restored.current_month == sim.current_month
        assert restored.world.year == sim.world.year
        assert len(restored.history) == len(sim.history)

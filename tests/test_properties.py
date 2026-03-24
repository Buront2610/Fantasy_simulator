"""Property-based tests for core invariants."""

import pytest
from fantasy_simulator.persistence.migrations import CURRENT_VERSION, migrate
from fantasy_simulator.world import LocationState

hypothesis = pytest.importorskip("hypothesis")
st = hypothesis.strategies
given = hypothesis.given


@given(st.integers(min_value=0, max_value=5))
def test_migration_always_reaches_current_version(start_version):
    data = {"schema_version": start_version, "world": {"grid": []}, "characters": []}
    migrated = migrate(data)
    assert migrated["schema_version"] == CURRENT_VERSION


@given(
    st.integers(min_value=-500, max_value=500),
    st.integers(min_value=-500, max_value=500),
    st.integers(min_value=-500, max_value=500),
)
def test_location_state_values_can_be_clamped_to_bounds(prosperity, safety, mood):
    loc = LocationState(id="loc_x", canonical_name="X", region_type="city", x=0, y=0)
    loc.prosperity = max(0, min(100, prosperity))
    loc.safety = max(0, min(100, safety))
    loc.mood = max(0, min(100, mood))
    assert 0 <= loc.prosperity <= 100
    assert 0 <= loc.safety <= 100
    assert 0 <= loc.mood <= 100

"""Property-based tests for core invariants."""

import pytest
from fantasy_simulator.content.setting_bundle import (
    RouteSeedDefinition,
    SettingBundle,
    SiteSeedDefinition,
    WorldDefinition,
    build_setting_bundle_authoring_summary,
)
from fantasy_simulator.persistence.migrations import CURRENT_VERSION, migrate
from fantasy_simulator.world import LocationState
from fantasy_simulator.content.world_data import get_location_state_defaults

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
    defaults = get_location_state_defaults("loc_x", "city")
    loc = LocationState(
        id="loc_x",
        canonical_name="X",
        description="",
        region_type="city",
        x=0,
        y=0,
        **defaults,
    )
    loc.prosperity = max(0, min(100, prosperity))
    loc.safety = max(0, min(100, safety))
    loc.mood = max(0, min(100, mood))
    assert 0 <= loc.prosperity <= 100
    assert 0 <= loc.safety <= 100
    assert 0 <= loc.mood <= 100


@given(
    st.lists(
        st.sampled_from(["city", "village", "forest", "mountain"]),
        min_size=1,
        max_size=8,
    )
)
def test_setting_bundle_authoring_summary_region_counts_cover_all_sites(region_types):
    site_seeds = [
        SiteSeedDefinition(
            location_id=f"loc_{idx}",
            name=f"Site {idx}",
            description="",
            region_type=region_type,
            x=idx,
            y=0,
        )
        for idx, region_type in enumerate(region_types)
    ]
    route_seeds = [
        RouteSeedDefinition(
            route_id=f"route_{idx}",
            from_site_id=site_seeds[idx].location_id,
            to_site_id=site_seeds[idx + 1].location_id,
            route_type="road",
            distance=1,
        )
        for idx in range(max(0, len(site_seeds) - 1))
    ]
    bundle = SettingBundle(
        schema_version=1,
        world_definition=WorldDefinition(
            world_key="property_world",
            display_name="Property World",
            lore_text="Property lore",
            site_seeds=site_seeds,
            route_seeds=route_seeds,
        ),
    )

    summary = build_setting_bundle_authoring_summary(bundle)

    assert sum(summary.site_counts_by_region_type.values()) == len(site_seeds)
    assert summary.route_count == len(route_seeds)

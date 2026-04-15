from __future__ import annotations

from fantasy_simulator.world import World
from fantasy_simulator.world_state_propagation import decay_toward_baseline, propagate_state_changes


def _clamp(value: int) -> int:
    return max(0, min(100, int(value)))


def test_decay_toward_baseline_moves_state_toward_defaults() -> None:
    world = World()
    loc = world.get_location_by_id("loc_thornwood")
    default_danger = world.location_state_defaults(loc.id, loc.region_type)["danger"]
    loc.danger = min(100, default_danger + 20)

    decay_toward_baseline(
        locations=world.grid.values(),
        months=12,
        months_per_year=world.months_per_year,
        state_decay_rate=0.30,
        location_defaults=world.location_state_defaults,
        clamp_state=_clamp,
    )

    assert loc.danger < default_danger + 20


def test_propagate_state_changes_spreads_high_danger_to_neighbors() -> None:
    world = World()
    source = world.get_location_by_id("loc_thornwood")
    neighbors = world.get_neighboring_locations(source.id)
    assert neighbors, "test requires at least one neighboring location"

    source.danger = 90
    for neighbor in neighbors:
        neighbor.danger = 10

    propagate_state_changes(
        locations=world.grid.values(),
        location_index=world._location_id_index,
        get_neighbors=world.get_neighboring_locations,
        months=12,
        months_per_year=world.months_per_year,
        clamp_state=_clamp,
    )

    assert any(neighbor.danger > 10 for neighbor in neighbors)

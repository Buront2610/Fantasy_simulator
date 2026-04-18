from __future__ import annotations

from dataclasses import dataclass

import pytest

from fantasy_simulator.world import World
from fantasy_simulator.world_state_propagation import (
    decay_toward_baseline,
    propagate_state_changes,
)


@dataclass
class _FakeLoc:
    id: str
    region_type: str = "plains"
    prosperity: int = 50
    danger: int = 0
    traffic: int = 0
    mood: int = 50
    safety: int = 50
    rumor_heat: int = 0
    road_condition: int = 80


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


def test_threshold_below_min_source_does_not_propagate_danger_or_traffic() -> None:
    src = _FakeLoc(id="src", danger=39, traffic=34)
    n1 = _FakeLoc(id="n1", danger=0, traffic=0)
    index = {"src": src, "n1": n1}

    def _neighbors(_loc_id: str) -> list[_FakeLoc]:
        return [n1] if _loc_id == "src" else []

    propagate_state_changes(
        locations=[src, n1],
        location_index=index,
        get_neighbors=_neighbors,
        months=12,
        months_per_year=12,
        clamp_state=_clamp,
    )

    assert n1.danger == 0
    assert n1.traffic == 0


def test_small_months_still_apply_minimum_non_zero_change() -> None:
    src = _FakeLoc(id="src", danger=40)
    n1 = _FakeLoc(id="n1", danger=39)
    index = {"src": src, "n1": n1}

    def _neighbors(_loc_id: str) -> list[_FakeLoc]:
        return [n1] if _loc_id == "src" else []

    propagate_state_changes(
        locations=[src, n1],
        location_index=index,
        get_neighbors=_neighbors,
        months=1,
        months_per_year=12,
        clamp_state=_clamp,
    )

    assert n1.danger == 40


def test_road_condition_degrades_when_danger_threshold_crossed() -> None:
    src = _FakeLoc(id="src", danger=70, road_condition=80)
    n1 = _FakeLoc(id="n1")
    index = {"src": src, "n1": n1}

    def _neighbors(_loc_id: str) -> list[_FakeLoc]:
        return [n1] if _loc_id == "src" else []

    propagate_state_changes(
        locations=[src, n1],
        location_index=index,
        get_neighbors=_neighbors,
        months=12,
        months_per_year=12,
        clamp_state=_clamp,
    )

    assert src.road_condition == 72


def test_mood_from_ruin_is_capped_by_max_neighbors() -> None:
    src = _FakeLoc(id="src", prosperity=10)
    neighbors = [_FakeLoc(id=f"n{i}", mood=50) for i in range(6)]
    index = {"src": src, **{loc.id: loc for loc in neighbors}}

    def _neighbors(_loc_id: str) -> list[_FakeLoc]:
        return neighbors if _loc_id == "src" else []

    propagate_state_changes(
        locations=[src, *neighbors],
        location_index=index,
        get_neighbors=_neighbors,
        months=12,
        months_per_year=12,
        clamp_state=_clamp,
    )

    changed = [loc.id for loc in neighbors if loc.mood < 50]
    assert changed == ["n0", "n1", "n2", "n3"]


def test_mood_from_ruin_uses_stable_neighbor_order_before_capping() -> None:
    src = _FakeLoc(id="src", prosperity=10)
    neighbors_a = [_FakeLoc(id=f"n{i}", mood=50) for i in range(6)]
    neighbors_b = [_FakeLoc(id=loc.id, mood=50) for loc in reversed(neighbors_a)]

    def _run(neighbors: list[_FakeLoc]) -> list[str]:
        index = {"src": src, **{loc.id: loc for loc in neighbors}}

        def _neighbors(_loc_id: str) -> list[_FakeLoc]:
            return neighbors if _loc_id == "src" else []

        propagate_state_changes(
            locations=[src, *neighbors],
            location_index=index,
            get_neighbors=_neighbors,
            months=12,
            months_per_year=12,
            clamp_state=_clamp,
        )
        return sorted(loc.id for loc in neighbors if loc.mood < 50)

    assert _run(neighbors_a) == _run(neighbors_b) == ["n0", "n1", "n2", "n3"]


def test_propagation_rules_fail_fast_on_invalid_delta_type() -> None:
    src = _FakeLoc(id="src", danger=40)
    n1 = _FakeLoc(id="n1", danger=10)
    index = {"src": src, "n1": n1}

    def _neighbors(_loc_id: str) -> list[_FakeLoc]:
        return [n1] if _loc_id == "src" else []

    from fantasy_simulator import world_state_propagation as wsp

    custom_rules = wsp.clone_default_propagation_rules()
    custom_rules["danger"]["cap"] = "15"
    try:
        with pytest.raises(ValueError, match="must be int"):
            propagate_state_changes(
                locations=[src, n1],
                location_index=index,
                get_neighbors=_neighbors,
                months=12,
                months_per_year=12,
                clamp_state=_clamp,
                propagation_rules=custom_rules,
            )
    finally:
        custom_rules["danger"]["cap"] = 15

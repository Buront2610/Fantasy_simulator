"""Location-state decay/propagation helpers for ``World``.

TD-3 split: isolate state propagation mechanics from world orchestration.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, MutableMapping, Tuple


PROPAGATION_RULES: Dict[str, Dict[str, Any]] = {
    "danger": {
        "decay": 0.30,
        "cap": 15,
        "min_source": 40,
    },
    "traffic": {
        "decay": 0.20,
        "cap": 10,
        "min_source": 35,
    },
    "mood_from_ruin": {
        "source_threshold": 20,
        "neighbor_penalty": 5,
        "max_neighbors": 4,
    },
    "road_damage_from_danger": {
        "danger_threshold": 70,
        "road_penalty": 8,
    },
}


def decay_toward_baseline(
    *,
    locations: Iterable[Any],
    months: int,
    months_per_year: int,
    state_decay_rate: float,
    location_defaults: Callable[[str, str], Dict[str, int]],
    clamp_state: Callable[[int], int],
) -> None:
    """Pull volatile state fields toward region defaults."""
    period_months = max(1, months)
    decay_rate = 1.0 - ((1.0 - state_decay_rate) ** (period_months / months_per_year))

    for loc in locations:
        defaults = location_defaults(loc.id, loc.region_type)
        for attr in ("danger", "traffic", "mood", "safety", "rumor_heat"):
            current = getattr(loc, attr)
            baseline = defaults[attr]
            diff = baseline - current
            if diff == 0:
                continue
            adjustment = int(diff * decay_rate)
            if adjustment == 0:
                adjustment = 1 if diff > 0 else -1
            setattr(loc, attr, clamp_state(current + adjustment))


def propagate_state_changes(
    *,
    locations: Iterable[Any],
    location_index: MutableMapping[str, Any],
    get_neighbors: Callable[[str], List[Any]],
    months: int,
    months_per_year: int,
    clamp_state: Callable[[int], int],
) -> None:
    """Propagate danger/traffic/mood/road-condition across neighboring locations."""
    period_months = max(1, months)
    period_fraction = period_months / months_per_year

    def _scaled(value: int) -> int:
        scaled = int(round(value * period_fraction))
        if value != 0 and scaled == 0:
            scaled = 1 if value > 0 else -1
        return scaled

    pending_changes: List[Tuple[str, str, int]] = []

    for loc in locations:
        neighbors = get_neighbors(loc.id)
        if not neighbors:
            continue

        rule = PROPAGATION_RULES["danger"]
        if loc.danger >= rule["min_source"]:
            spread = _scaled(min(int(loc.danger * rule["decay"]), rule["cap"]))
            for neighbor in neighbors:
                if neighbor.danger < loc.danger:
                    pending_changes.append((neighbor.id, "danger", min(spread, loc.danger - neighbor.danger)))

        rule = PROPAGATION_RULES["traffic"]
        if loc.traffic >= rule["min_source"]:
            spread = _scaled(min(int(loc.traffic * rule["decay"]), rule["cap"]))
            for neighbor in neighbors:
                if neighbor.traffic < loc.traffic:
                    pending_changes.append((neighbor.id, "traffic", min(spread, loc.traffic - neighbor.traffic)))

        rule = PROPAGATION_RULES["mood_from_ruin"]
        if loc.prosperity < rule["source_threshold"]:
            penalty = _scaled(-rule["neighbor_penalty"])
            for neighbor in neighbors[:rule["max_neighbors"]]:
                pending_changes.append((neighbor.id, "mood", penalty))

        rule = PROPAGATION_RULES["road_damage_from_danger"]
        if loc.danger >= rule["danger_threshold"]:
            pending_changes.append((loc.id, "road_condition", _scaled(-rule["road_penalty"])))

    for loc_id, attr, delta in pending_changes:
        location = location_index.get(loc_id)
        if location is None:
            continue
        old = getattr(location, attr)
        setattr(location, attr, clamp_state(old + delta))

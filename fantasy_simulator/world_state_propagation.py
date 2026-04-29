"""Location-state decay/propagation helpers for ``World``.

TD-3 split: isolate state propagation mechanics from world orchestration.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Protocol, Tuple

from .rule_override_resolution import (
    DEFAULT_PROPAGATION_RULES,
    clone_default_propagation_rules as _clone_default_propagation_rules,
    is_disabled_threshold,
    validate_propagation_rules,
)


class SupportsPropagationLocation(Protocol):
    id: str
    region_type: str
    prosperity: int
    danger: int
    traffic: int
    mood: int
    safety: int
    rumor_heat: int
    road_condition: int


def decay_toward_baseline(
    *,
    locations: Iterable[SupportsPropagationLocation],
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
    locations: Iterable[SupportsPropagationLocation],
    location_index: Mapping[str, SupportsPropagationLocation],
    get_neighbors: Callable[[str], List[SupportsPropagationLocation]],
    months: int,
    months_per_year: int,
    clamp_state: Callable[[int], int],
    propagation_rules: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> None:
    """Propagate danger/traffic/mood/road-condition across neighboring locations."""
    rules = DEFAULT_PROPAGATION_RULES if propagation_rules is None else propagation_rules
    validate_propagation_rules(rules)
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

        rule = rules["danger"]
        if loc.danger >= rule["min_source"]:
            spread = _scaled(min(int(loc.danger * rule["decay"]), rule["cap"]))
            for neighbor in neighbors:
                if neighbor.danger < loc.danger:
                    pending_changes.append((neighbor.id, "danger", min(spread, loc.danger - neighbor.danger)))

        rule = rules["traffic"]
        if loc.traffic >= rule["min_source"]:
            spread = _scaled(min(int(loc.traffic * rule["decay"]), rule["cap"]))
            for neighbor in neighbors:
                if neighbor.traffic < loc.traffic:
                    pending_changes.append((neighbor.id, "traffic", min(spread, loc.traffic - neighbor.traffic)))

        rule = rules["mood_from_ruin"]
        if loc.prosperity < rule["source_threshold"]:
            penalty = _scaled(-rule["neighbor_penalty"])
            for neighbor in sorted(neighbors, key=lambda item: item.id)[:rule["max_neighbors"]]:
                pending_changes.append((neighbor.id, "mood", penalty))

        rule = rules["road_damage_from_danger"]
        if not is_disabled_threshold(rule["danger_threshold"]) and loc.danger >= rule["danger_threshold"]:
            pending_changes.append((loc.id, "road_condition", _scaled(-rule["road_penalty"])))

    for loc_id, attr, delta in pending_changes:
        location = location_index.get(loc_id)
        if location is None:
            continue
        old = getattr(location, attr)
        setattr(location, attr, clamp_state(old + delta))


def clone_default_propagation_rules() -> Dict[str, Dict[str, Any]]:
    """Compatibility wrapper around the shared rule-table owner."""
    return _clone_default_propagation_rules()

"""World-level state decay and propagation orchestration."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Mapping, Protocol

from .world_state_propagation import decay_toward_baseline, propagate_state_changes


class SupportsRuntimeStateLocation(Protocol):
    id: str
    region_type: str
    prosperity: int
    danger: int
    traffic: int
    mood: int
    safety: int
    rumor_heat: int
    road_condition: int


def decay_world_state(
    *,
    locations: Iterable[SupportsRuntimeStateLocation],
    months: int,
    months_per_year: int,
    state_decay_rate: float,
    location_defaults: Callable[[str, str], Dict[str, int]],
    clamp_state: Callable[[int], int],
) -> None:
    """Pull volatile state fields back toward their region-type defaults."""
    decay_toward_baseline(
        locations=locations,
        months=months,
        months_per_year=months_per_year,
        state_decay_rate=state_decay_rate,
        location_defaults=location_defaults,
        clamp_state=clamp_state,
    )


def propagate_world_state(
    *,
    locations: Iterable[SupportsRuntimeStateLocation],
    location_index: Mapping[str, SupportsRuntimeStateLocation],
    get_neighbors: Callable[[str], List[SupportsRuntimeStateLocation]],
    months: int,
    months_per_year: int,
    clamp_state: Callable[[int], int],
    propagation_rules: Dict[str, Dict[str, Any]],
) -> None:
    """Propagate location state using the configured propagation topology."""
    propagate_state_changes(
        locations=locations,
        location_index=location_index,
        get_neighbors=get_neighbors,
        months=months,
        months_per_year=months_per_year,
        clamp_state=clamp_state,
        propagation_rules=propagation_rules,
    )

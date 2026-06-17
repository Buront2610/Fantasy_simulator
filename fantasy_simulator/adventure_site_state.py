"""Persistent site-state updates derived from resolved adventures."""

from __future__ import annotations

from typing import Any

from .world_location_state import clamp_reputation, clamp_state


_OUTCOME_DELTAS: dict[str, tuple[int, int]] = {
    "safe_return": (15, 8),
    "injury": (8, -2),
    "death": (5, -8),
    "retreat": (3, 0),
}


def apply_adventure_site_state(world: Any, run: Any) -> None:
    """Persist exploration progress and local reputation on an adventure destination."""
    location = world.get_location_by_id(run.destination)
    if location is None:
        return
    progress_delta, reputation_delta = _OUTCOME_DELTAS.get(str(run.outcome), (1, 0))
    if getattr(run, "loot_summary", []):
        progress_delta += 10
        reputation_delta += 4

    location.visited = True
    location.exploration_progress = clamp_state(location.exploration_progress + progress_delta)
    location.adventure_reputation = clamp_reputation(location.adventure_reputation + reputation_delta)
    location.rumor_heat = clamp_state(location.rumor_heat + _rumor_delta(run))


def _rumor_delta(run: Any) -> int:
    if getattr(run, "outcome", "") == "death":
        return 8
    if getattr(run, "loot_summary", []):
        return 6
    if getattr(run, "outcome", "") == "injury":
        return 4
    return 2

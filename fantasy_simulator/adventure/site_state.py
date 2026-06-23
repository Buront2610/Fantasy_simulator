"""Persistent site-state updates derived from resolved adventures."""

from __future__ import annotations

from typing import Any

from ..world_location.state import clamp_reputation, clamp_state


_OUTCOME_DELTAS: dict[str, tuple[int, int]] = {
    "safe_return": (15, 8),
    "injury": (8, -2),
    "death": (5, -8),
    "retreat": (3, 0),
}

_DUNGEON_CLEARANCE_DELTAS: dict[str, int] = {
    "safe_return": 18,
    "injury": 8,
    "death": 3,
    "retreat": 4,
}

_HAZARD_REGROWTH_DELTAS: dict[str, int] = {
    "safe_return": -8,
    "injury": 5,
    "death": 12,
    "retreat": 6,
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
    location.last_adventure_id = str(getattr(run, "adventure_id", "") or "")
    resolution_year = getattr(run, "resolution_year", None)
    if resolution_year is None:
        resolution_year = getattr(world, "year", 0)
    if resolution_year is None:
        resolution_year = 0
    location.last_adventure_year = int(resolution_year)
    location.last_adventure_outcome = str(getattr(run, "outcome", "") or "")
    location.adventure_count = max(0, int(getattr(location, "adventure_count", 0))) + 1
    location.exploration_progress = clamp_state(location.exploration_progress + progress_delta)
    location.adventure_reputation = clamp_reputation(location.adventure_reputation + reputation_delta)
    location.rumor_heat = clamp_state(location.rumor_heat + _rumor_delta(run))
    if location.region_type == "dungeon":
        location.dungeon_clearance = clamp_state(
            location.dungeon_clearance + _dungeon_clearance_delta(run)
        )
        location.hazard_regrowth = clamp_state(
            location.hazard_regrowth + _hazard_regrowth_delta(run)
        )


def _rumor_delta(run: Any) -> int:
    if getattr(run, "outcome", "") == "death":
        return 8
    if getattr(run, "loot_summary", []):
        return 6
    if getattr(run, "outcome", "") == "injury":
        return 4
    return 2


def _dungeon_clearance_delta(run: Any) -> int:
    delta = _DUNGEON_CLEARANCE_DELTAS.get(str(getattr(run, "outcome", "")), 1)
    if getattr(run, "loot_summary", []):
        delta += 10
    return delta


def _hazard_regrowth_delta(run: Any) -> int:
    delta = _HAZARD_REGROWTH_DELTAS.get(str(getattr(run, "outcome", "")), 2)
    if getattr(run, "loot_summary", []):
        delta -= 6
    return delta

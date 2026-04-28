"""Seasonal location modifier helpers for timeline processing."""

from __future__ import annotations

from typing import Any, Dict


SEASONAL_MODIFIERS: Dict[tuple, Dict[str, int]] = {
    ("winter", "mountain"): {"danger": +30, "road_condition": -20},
    ("winter", "forest"): {"danger": +15, "road_condition": -15},
    ("winter", "sea"): {"traffic": -20},
    ("winter", "plains"): {"road_condition": -10},
    ("spring", "village"): {"mood": +10, "traffic": +10},
    ("spring", "city"): {"mood": +5, "traffic": +10},
    ("spring", "forest"): {"danger": -10},
    ("summer", "city"): {"traffic": +20},
    ("summer", "sea"): {"traffic": +20, "danger": -10},
    ("summer", "plains"): {"traffic": +15},
    ("autumn", "plains"): {"danger": +10},
    ("autumn", "forest"): {"danger": +10},
    ("autumn", "dungeon"): {"danger": +15},
}

SeasonalDelta = tuple[Any, str, int]


def apply_seasonal_modifiers(world, month: int) -> list[SeasonalDelta]:
    """Apply seasonal modifiers to locations and return reversible deltas."""
    season = world.season_for_month(month)
    active_deltas: list[SeasonalDelta] = []
    for (modifier_season, region), deltas in SEASONAL_MODIFIERS.items():
        if modifier_season != season:
            continue
        for loc in world.grid.values():
            if loc.region_type != region:
                continue
            for attr, delta in deltas.items():
                if not hasattr(loc, attr):
                    continue
                old_val = getattr(loc, attr)
                new_val = max(0, min(100, old_val + delta))
                setattr(loc, attr, new_val)
                active_deltas.append((loc, attr, new_val - old_val))
    return active_deltas


def revert_seasonal_modifiers(active_deltas: list[SeasonalDelta]) -> None:
    """Revert seasonal modifier deltas in place."""
    for loc, attr, applied_delta in active_deltas:
        old_val = getattr(loc, attr)
        setattr(loc, attr, max(0, min(100, old_val - applied_delta)))
    active_deltas.clear()

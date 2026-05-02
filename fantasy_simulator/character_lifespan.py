"""Legacy character lifespan compatibility helpers."""

from __future__ import annotations


_LEGACY_RACE_LIFESPANS = {
    "Human": 80,
    "Elf": 600,
    "Dwarf": 250,
    "Halfling": 130,
    "Orc": 60,
    "Tiefling": 100,
    "Dragonborn": 80,
}


def legacy_lifespan_years(race: str) -> int:
    """Return the legacy built-in lifespan for a race."""
    return _LEGACY_RACE_LIFESPANS.get(race, 80)

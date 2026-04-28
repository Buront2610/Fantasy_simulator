"""Rumor lifecycle helpers for timeline month-end processing."""

from __future__ import annotations

from ..rumor import age_rumors, generate_rumors_for_period, trim_rumors


def generate_and_age_rumors_for_month(world, *, year: int, month: int, rng, max_rumors: int = 3) -> None:
    """Age, generate, and trim rumors for one month-end batch."""
    active, expired = age_rumors(world.rumors, months=1)
    world.rumors = active
    world.rumor_archive.extend(expired)

    new_rumors = generate_rumors_for_period(
        world,
        year=year,
        month=month,
        max_rumors=max_rumors,
        rng=rng,
    )
    world.rumors.extend(new_rumors)

    kept, trimmed = trim_rumors(world.rumors)
    world.rumors = kept
    world.rumor_archive.extend(trimmed)


def generate_and_age_rumors_for_year(world, *, rng, max_rumors: int = 3) -> None:
    """Perform the full annual rumor cycle as month-end batches."""
    for month in range(1, world.months_per_year + 1):
        generate_and_age_rumors_for_month(
            world,
            year=world.year,
            month=month,
            rng=rng,
            max_rumors=max_rumors,
        )

"""Shared calendar and rate helpers for simulation time progression."""

from __future__ import annotations

MONTHS_PER_YEAR = 12
DAYS_PER_MONTH = 30
DAYS_PER_YEAR = MONTHS_PER_YEAR * DAYS_PER_MONTH
_FLOAT_EPS = 1e-9


def annual_probability_to_fraction(annual_probability: float, year_fraction: float) -> float:
    """Convert an annual probability into the equivalent probability for a sub-period."""
    annual_probability = max(0.0, min(1.0, annual_probability))
    year_fraction = max(0.0, year_fraction)
    if annual_probability <= 0.0 or year_fraction <= 0.0:
        return 0.0
    if annual_probability >= 1.0:
        return 1.0
    return 1.0 - ((1.0 - annual_probability) ** year_fraction)


def distributed_budget(total_per_year: float, periods_per_year: int, rng) -> int:
    """Distribute an annual integer-ish budget across equal periods stochastically."""
    if periods_per_year <= 0:
        return 0
    total = max(0.0, total_per_year)
    base = int(total / periods_per_year)
    remainder = total / periods_per_year - base
    extra = 1 if (remainder > _FLOAT_EPS and rng.random() < remainder) else 0
    return base + extra

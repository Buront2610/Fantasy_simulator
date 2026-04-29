"""Calendar calculations used by timeline processing."""

from __future__ import annotations


def propagation_month_window(month: int, months_per_year: int) -> int:
    """Return how many months of state propagation to apply at this month-end."""
    if months_per_year % 4 == 0:
        interval = max(1, months_per_year // 4)
        if month % interval == 0:
            return interval
        return 0
    if month == months_per_year:
        return months_per_year
    return 0

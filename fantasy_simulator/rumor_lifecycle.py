"""Aging and retention helpers for rumors."""

from __future__ import annotations

from typing import List

from .rumor_constants import MAX_ACTIVE_RUMORS
from .rumor_models import Rumor


def age_rumors(
    rumors: List[Rumor], months: int = 1,
) -> tuple:
    """Age all rumors, returning (active, newly_expired).

    Expired rumors are separated so they can be archived for stable
    historical report generation.
    """
    active: List[Rumor] = []
    expired: List[Rumor] = []
    for rumor in rumors:
        rumor.age_in_months += months
        if rumor.is_expired:
            expired.append(rumor)
        else:
            active.append(rumor)
    return active, expired


def trim_rumors(
    rumors: List[Rumor], max_count: int = MAX_ACTIVE_RUMORS,
) -> tuple:
    """Keep only the most recent rumors up to max_count.

    Returns (kept, trimmed) so trimmed rumors can be archived.
    """
    if len(rumors) <= max_count:
        return rumors, []
    sorted_rumors = sorted(rumors, key=lambda r: r.age_in_months)
    return sorted_rumors[:max_count], sorted_rumors[max_count:]

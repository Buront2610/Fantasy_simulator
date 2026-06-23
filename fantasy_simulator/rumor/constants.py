"""Shared constants for the rumor system."""

from __future__ import annotations

from typing import Dict

RELIABILITY_LEVELS = ("certain", "plausible", "doubtful", "false")

DISCLOSURE: Dict[str, Dict[str, float]] = {
    "certain": {"who": 1.0, "what": 1.0, "where": 1.0, "when": 1.0},
    "plausible": {"who": 0.9, "what": 0.8, "where": 0.7, "when": 0.5},
    "doubtful": {"who": 0.5, "what": 0.6, "where": 0.3, "when": 0.2},
    "false": {"who": 0.3, "what": 0.0, "where": 0.5, "when": 0.1},
}

# Minimum severity for an event to spawn a rumor.
MIN_SEVERITY_FOR_RUMOR = 2

# Base probability of generating a rumor from a qualifying event.
RUMOR_BASE_CHANCE = 0.6

# Maximum number of active rumors per world.
MAX_ACTIVE_RUMORS = 50

# Months before a rumor expires.
RUMOR_MAX_AGE_MONTHS = 24

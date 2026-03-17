"""
save_load.py - Save/load helpers for simulation snapshots.
"""

from __future__ import annotations

import json
from typing import Any

from simulator import Simulator


def save_simulation(simulator: Simulator, path: str) -> None:
    """Write the full simulator state to a JSON file."""
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(simulator.to_dict(), handle, indent=2)


def load_simulation(path: str) -> Simulator:
    """Load a simulator snapshot from a JSON file."""
    with open(path, "r", encoding="utf-8") as handle:
        data: Any = json.load(handle)
    return Simulator.from_dict(data)

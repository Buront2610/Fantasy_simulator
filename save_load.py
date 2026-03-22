"""
save_load.py - Save/load helpers for simulation snapshots.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from simulator import Simulator

logger = logging.getLogger(__name__)


def save_simulation(simulator: Simulator, path: str) -> bool:
    """Write the full simulator state to a JSON file.

    Returns True on success, False on failure.
    """
    try:
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(simulator.to_dict(), handle, indent=2)
        return True
    except (OSError, TypeError, ValueError) as exc:
        logger.error("Failed to save simulation to %s: %s", path, exc)
        return False


def load_simulation(path: str) -> Optional[Simulator]:
    """Load a simulator snapshot from a JSON file.

    Returns the Simulator on success, or None on failure.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data: Any = json.load(handle)
        return Simulator.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError, AttributeError) as exc:
        logger.error("Failed to load simulation from %s: %s", path, exc)
        return None

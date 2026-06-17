"""
save_load.py - Save/load helpers for simulation snapshots.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from typing import Any, Optional

from .migrations import CURRENT_VERSION, migrate
from ..simulator import Simulator

logger = logging.getLogger(__name__)


def save_simulation(simulator: Simulator, path: str) -> bool:
    """Write the full simulator state to a JSON file.

    Returns True on success, False on failure.
    """
    temp_path: Optional[str] = None
    try:
        payload = simulator.to_dict()
        payload["schema_version"] = CURRENT_VERSION
        directory = os.path.dirname(os.path.abspath(path)) or "."
        fd, temp_path = tempfile.mkstemp(prefix=".save-", suffix=".tmp", dir=directory, text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
        temp_path = None
        return True
    except (OSError, TypeError, ValueError) as exc:
        logger.error("Failed to save simulation to %s: %s", path, exc)
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except OSError:
                logger.debug("Failed to remove temporary save file %s", temp_path, exc_info=True)
        return False


def load_simulation(path: str) -> Optional[Simulator]:
    """Load a simulator snapshot from a JSON file.

    Returns the Simulator on success, or None on failure.
    """
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data: Any = json.load(handle)
        data = migrate(data)
        return Simulator.from_dict(data)
    except (OSError, json.JSONDecodeError, KeyError, ValueError, TypeError, AttributeError) as exc:
        logger.error("Failed to load simulation from %s: %s", path, exc)
        return None

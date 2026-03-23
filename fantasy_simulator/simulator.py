"""simulator.py - Backward-compatible import path for Simulator.

Canonical location: ``fantasy_simulator.simulation.engine``

This module re-exports the Simulator class so that existing imports like
``from fantasy_simulator.simulator import Simulator`` continue to work.
"""

from .simulation import Simulator  # noqa: F401

__all__ = ["Simulator"]

"""simulation sub-package — Simulator class split across responsibility modules.

The Simulator class is composed from several mixins, each in its own module:

- engine.py: Core orchestration, loop control, serialization
- timeline.py: Monthly processing, seasonal modifiers, dying/injury resolution
- notifications.py: Notification threshold evaluation
- event_recorder.py: Event recording across all event stores
- adventure_coordinator.py: Adventure lifecycle management
- queries.py: Summary, report, story, and event-log access

Import the assembled Simulator from this package::

    from fantasy_simulator.simulation import Simulator
"""

from .engine import Simulator

__all__ = ["Simulator"]

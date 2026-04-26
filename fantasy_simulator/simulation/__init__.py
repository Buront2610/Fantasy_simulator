"""simulation sub-package — Simulator class split across responsibility modules.

The Simulator class is composed from several mixins, each in its own module:

- engine.py: Core orchestration, loop control, serialization
- timeline.py: Monthly processing, seasonal modifiers, dying/injury resolution
- notifications.py: Notification threshold evaluation
- event_recorder.py: Event recording across transitional event stores
- adventure_coordinator.py: Adventure lifecycle management
- queries.py: Summary, report, story, and event-log access

``world.event_records`` is the canonical event store by policy.  ``history``
and ``event_log`` are runtime compatibility adapters projected from canonical
records for older query paths.

Import the assembled Simulator from this package::

    from fantasy_simulator.simulation import Simulator
"""

__all__ = ["Simulator"]


def __getattr__(name: str):
    if name == "Simulator":
        from .engine import Simulator

        return Simulator
    raise AttributeError(name)

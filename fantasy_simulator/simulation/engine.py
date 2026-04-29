"""Core Simulator class — assembles the world simulation loop.

The Simulator is composed from several mixins that separate concerns:

- :class:`~.engine_progression.EngineProgressionMixin`: calendar advancement
- :class:`~.engine_pause.EnginePauseMixin`: conditional auto-pause handling
- :class:`~.engine_persistence.EnginePersistenceMixin`: serialization
- :class:`~.event_recorder.EventRecorderMixin`: event recording
- :class:`~.timeline.TimelineMixin`: monthly processing
- :class:`~.notifications.NotificationMixin`: notification evaluation
- :class:`~.adventure_coordinator.AdventureMixin`: adventure management
- :class:`~.queries.QueryMixin`: summary / report / story access

This module contains only Simulator assembly, initialisation, and the legacy
``history`` adapter.
"""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, List, Optional

from ..adventure import AdventureRun
from ..event_models import EventResult, WorldEventRecord
from ..events import EventSystem
from ..narrative.template_history import TemplateHistory

from .adventure_coordinator import AdventureMixin
from .engine_pause import EnginePauseMixin
from .engine_persistence import EnginePersistenceMixin
from .engine_progression import EngineProgressionMixin
from .event_recorder import EventRecorderMixin
from .notifications import NotificationMixin
from .queries import QueryMixin
from .timeline import TimelineMixin

if TYPE_CHECKING:
    from ..world import World


class Simulator(
    EngineProgressionMixin,
    EnginePauseMixin,
    EnginePersistenceMixin,
    EventRecorderMixin,
    TimelineMixin,
    NotificationMixin,
    AdventureMixin,
    QueryMixin,
):
    """Drives the world simulation forward in time.

    Parameters
    ----------
    world : World
        The World instance to simulate.
    events_per_year : int
        How many random events to generate each in-world year.
    seed : Optional[int]
        If provided, seeds the random number generator for reproducibility.
    """

    def __init__(
        self,
        world: World,
        events_per_year: int = 8,
        adventure_steps_per_year: int = 3,
        seed: Optional[int] = None,
    ) -> None:
        self.world = world
        self.events_per_year = events_per_year
        self.adventure_steps_per_year = adventure_steps_per_year
        self.event_system = EventSystem()
        # Mutable progress marker for structured event timestamps within the
        # current simulated year. This value is serialized and restored as-is
        # to preserve in-progress context across save/load.
        self.current_month: int = 1
        self.current_day: int = 1
        self.elapsed_days: int = 0
        # Baseline year used for "latest completed report year" fallback when
        # the simulation has not yet completed a full year.
        self.start_year: int = world.year
        self.rng = random.Random(seed)
        self.id_rng = random.Random(self._id_seed_from_seed(seed))
        # Events that passed the should_notify() threshold during the
        # most recent advance_years() call, available for the UI layer.
        self.pending_notifications: List[WorldEventRecord] = []
        # Adventures completed during the current year, used by
        # _check_pause_conditions() for the party_returned condition.
        self._recently_completed_adventures: List[AdventureRun] = []
        # Favorites whose condition worsened this year, used for
        # event-based condition_worsened_favorite pause checks.
        self._favorites_worsened_this_year: set[str] = set()
        # Accumulated seasonal delta tuples for _revert_seasonal_modifiers()
        self._active_seasonal_deltas: List[tuple] = []
        # PR-I: deterministic cooldown history for world-memory text selection.
        self.memorial_template_history = TemplateHistory(cooldown_size=4)
        self.alias_template_history = TemplateHistory(cooldown_size=4)

    @property
    def history(self) -> List[EventResult]:
        """Project the legacy EventResult adapter from canonical world records.

        Compatibility note:
        This property intentionally survives until save/load and legacy callers
        no longer require `EventResult` snapshots. New logic must consume
        `world.event_records` instead of this adapter.
        """
        return [record.to_event_result() for record in self.world.event_records]

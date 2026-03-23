"""Core Simulator class — orchestrates the world simulation loop.

The Simulator is composed from several mixins that separate concerns:

- :class:`~.event_recorder.EventRecorderMixin`: event recording
- :class:`~.timeline.TimelineMixin`: monthly processing
- :class:`~.notifications.NotificationMixin`: notification evaluation
- :class:`~.adventure_coordinator.AdventureMixin`: adventure management
- :class:`~.queries.QueryMixin`: summary / report / story access

This module contains the core orchestration: initialisation, the main
advance loops, pause-condition checking, and serialization.
"""

from __future__ import annotations

import ast
import random
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..adventure import AdventureRun
from ..events import EventResult, EventSystem, WorldEventRecord
from ..i18n import get_locale, set_locale

from .adventure_coordinator import AdventureMixin
from .event_recorder import EventRecorderMixin
from .notifications import NotificationMixin
from .queries import QueryMixin
from .timeline import TimelineMixin

if TYPE_CHECKING:
    from ..world import World


class Simulator(
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

    # Conditional auto-advance pause priorities (design §4.5)
    AUTO_PAUSE_PRIORITIES: Dict[str, int] = {
        "dying_spotlighted": 100,
        "pending_decision": 90,
        "dying_favorite": 80,
        "party_returned": 70,
        "dying_any": 60,
        "condition_worsened_favorite": 50,
        "years_elapsed": 10,
    }

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
        # Compatibility cache of EventResult objects.  Only populated via
        # _record_event(); events that go directly through _record_world_event()
        # (adventure lifecycle, injury recovery) do NOT appear here.  The
        # canonical structured history lives in world.event_records.  This
        # list is still persisted for save/load compatibility but should be
        # treated as an incomplete, gradually-retiring adapter.
        self.history: List[EventResult] = []
        # Mutable progress marker for structured event timestamps within the
        # current simulated year. This value is serialized and restored as-is
        # to preserve in-progress context across save/load.
        self.current_month: int = 1
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

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _id_seed_from_seed(seed: Optional[int]) -> int:
        base_seed = 0 if seed is None else seed
        return base_seed ^ 0x5EED5EED

    @staticmethod
    def _legacy_id_seed(data: Dict[str, Any]) -> int:
        world_data = data.get("world", {})
        seed = world_data.get("year", 0)
        for count in (
            len(data.get("history", [])),
            len(world_data.get("event_records", [])),
            len(world_data.get("active_adventures", [])),
            len(world_data.get("completed_adventures", [])),
        ):
            seed = (seed * 1_000_003 + count) & ((1 << 64) - 1)
        return seed ^ 0x5EED5EED

    @staticmethod
    def _restore_rng_state(rng: random.Random, state_repr: Optional[str]) -> bool:
        if state_repr is None:
            return False
        try:
            parsed = ast.literal_eval(state_repr)
            if (
                isinstance(parsed, tuple)
                and len(parsed) == 3
                and isinstance(parsed[0], int)
                and isinstance(parsed[1], tuple)
            ):
                rng.setstate(parsed)
                return True
        except (ValueError, SyntaxError, TypeError):
            return False
        return False

    # ------------------------------------------------------------------
    # Main simulation loop
    # ------------------------------------------------------------------

    def run(self, years: int = 10) -> None:
        """Simulate *years* years of in-world history.

        Each year:
        1. Check for natural deaths.
        2. Generate *events_per_year* random events.
        3. Advance the world clock.
        """
        self.advance_years(years)

    def advance_years(self, years: int = 1) -> None:
        """Advance the simulation by exactly *years × 12* months.

        Implemented via ``advance_months(years * 12)`` so that mid-year state
        is always respected: processing starts from ``current_month`` and
        advances exactly ``years * 12`` months forward, wrapping across year
        boundaries naturally.
        """
        self.advance_months(years * 12)

    def advance_months(self, months: int = 1) -> None:
        """Advance the simulation by *months* in-world months.

        Handles year-end transitions automatically: when month 12 completes,
        world.advance_time(1) is called and per-year tracking sets are cleared,
        then processing continues with month 1 of the next year.

        Always respects the current position within the year so partial-year
        advancement is supported.  ``advance_years()`` delegates here.
        """
        self.pending_notifications.clear()
        for _ in range(months):
            if self.current_month == 1:
                # Reset per-year tracking at the start of each new year
                self._recently_completed_adventures.clear()
                self._favorites_worsened_this_year.clear()
            self._run_month(self.current_month)
            if self.current_month == 12:
                self.world.advance_time(1)
            self.current_month = (self.current_month % 12) + 1

    def advance_until_pause(self, max_years: int = 12) -> Dict[str, Any]:
        """Advance the simulation month-by-month until a pause condition triggers.

        Returns a dict with 'months_advanced', 'years_advanced', 'pause_reason',
        and 'pause_priority'.  The monthly granularity allows pause conditions
        (e.g. dying, pending decisions) to fire at the exact month they occur
        rather than waiting until the end of the year.

        This implements the conditional auto-advance system (design §4.4).
        """
        self.pending_notifications.clear()
        self._favorites_worsened_this_year.clear()
        self._recently_completed_adventures.clear()
        preexisting_reason = self._check_pause_conditions()
        if preexisting_reason is not None:
            return {
                "months_advanced": 0,
                "years_advanced": 0,
                "pause_reason": preexisting_reason,
                "pause_priority": self.AUTO_PAUSE_PRIORITIES.get(preexisting_reason, 0),
            }
        max_months = max_years * 12
        months_advanced = 0
        for _ in range(max_months):
            if self.current_month == 1:
                self._recently_completed_adventures.clear()
                self._favorites_worsened_this_year.clear()
            self._run_month(self.current_month)
            if self.current_month == 12:
                self.world.advance_time(1)
            self.current_month = (self.current_month % 12) + 1
            months_advanced += 1
            reason = self._check_pause_conditions()
            if reason is not None:
                return {
                    "months_advanced": months_advanced,
                    "years_advanced": months_advanced // 12,
                    "pause_reason": reason,
                    "pause_priority": self.AUTO_PAUSE_PRIORITIES.get(reason, 0),
                }
        return {
            "months_advanced": months_advanced,
            "years_advanced": months_advanced // 12,
            "pause_reason": "years_elapsed",
            "pause_priority": self.AUTO_PAUSE_PRIORITIES["years_elapsed"],
        }

    def _check_pause_conditions(self) -> Optional[str]:
        """Check if any auto-pause condition is met. Returns highest-priority reason."""
        reasons: List[tuple] = []

        for char in self.world.characters:
            if not char.alive:
                continue
            if char.is_dying:
                if char.spotlighted:
                    reasons.append(("dying_spotlighted",
                                    self.AUTO_PAUSE_PRIORITIES["dying_spotlighted"]))
                elif char.favorite:
                    reasons.append(("dying_favorite",
                                    self.AUTO_PAUSE_PRIORITIES["dying_favorite"]))
                else:
                    reasons.append(("dying_any",
                                    self.AUTO_PAUSE_PRIORITIES["dying_any"]))
            if char.favorite and char.char_id in self._favorites_worsened_this_year:
                reasons.append(("condition_worsened_favorite",
                                self.AUTO_PAUSE_PRIORITIES["condition_worsened_favorite"]))

        # Pending adventure choices
        for run in self.world.active_adventures:
            if run.pending_choice is not None:
                reasons.append(("pending_decision",
                                self.AUTO_PAUSE_PRIORITIES["pending_decision"]))
                break

        # Party returned (design §4.4: check recently completed adventures)
        if self._recently_completed_adventures:
            for run in self._recently_completed_adventures:
                char = self.world.get_character_by_id(run.character_id)
                if char and (char.favorite or char.spotlighted):
                    reasons.append(("party_returned",
                                    self.AUTO_PAUSE_PRIORITIES["party_returned"]))
                    break

        if not reasons:
            return None
        reasons.sort(key=lambda x: -x[1])
        return reasons[0][0]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialise simulator state.

        ``event_records`` is the canonical store by policy, but ``history``
        and ``event_log`` (inside ``world.to_dict()``) are still persisted
        for save/load backward compatibility.  Reducing to a single
        persisted representation is a future task.
        """
        return {
            "world": self.world.to_dict(),
            "characters": [char.to_dict() for char in self.world.characters],
            "events_per_year": self.events_per_year,
            "adventure_steps_per_year": self.adventure_steps_per_year,
            "current_month": self.current_month,
            "start_year": self.start_year,
            "locale": get_locale(),
            "rng_state": repr(self.rng.getstate()),
            "id_rng_state": repr(self.id_rng.getstate()),
            "history": [ev.to_dict() for ev in self.history],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Simulator":
        """Rebuild a simulator from a serialised snapshot."""
        from ..character import Character
        from ..world import World

        world = World.from_dict(data["world"])
        characters = [
            Character.from_dict(char_data) for char_data in data.get("characters", [])
        ]
        world.characters = characters
        world.normalize_after_load()
        sim = cls(
            world,
            events_per_year=data.get("events_per_year", 8),
            adventure_steps_per_year=data.get("adventure_steps_per_year", 3),
        )
        set_locale(data.get("locale", get_locale()))
        sim._restore_rng_state(sim.rng, data.get("rng_state"))
        if not sim._restore_rng_state(sim.id_rng, data.get("id_rng_state")):
            sim.id_rng.seed(sim._legacy_id_seed(data))
        sim.current_month = max(1, min(12, data.get("current_month", 1)))
        sim.start_year = data.get("start_year", sim.world.year)
        sim.history = [
            EventResult.from_dict(ev) for ev in data.get("history", [])
        ]
        return sim

"""Monthly timeline processing for the Simulator.

Contains the month-by-month simulation logic: dying resolution, injury
recovery, seasonal modifiers, random event generation, rumor lifecycle,
adventure scheduling, and year-end state propagation.
"""

from __future__ import annotations

from typing import Dict, List

from ..i18n import tr
from ..rumor import age_rumors, generate_rumors_for_period, trim_rumors


class TimelineMixin:
    """Mixin providing monthly processing methods for the Simulator.

    Expected attributes on *self* (provided by ``engine.Simulator``):
    - ``world``: the World instance
    - ``current_month``: current in-world month (1–12)
    - ``events_per_year``: target event count per year
    - ``event_system``: EventSystem instance
    - ``rng``: RNG for simulation decisions
    - ``_favorites_worsened_this_year``: set of char IDs
    - ``_active_seasonal_deltas``: list of (loc, attr, delta) tuples
    """

    # Seasonal modifiers applied to locations each year (design §5.7).
    SEASONAL_MODIFIERS: Dict[tuple, Dict[str, int]] = {
        # Winter: mountains & forests become treacherous, sea routes close
        ("winter", "mountain"): {"danger": +30, "road_condition": -20},
        ("winter", "forest"): {"danger": +15, "road_condition": -15},
        ("winter", "sea"): {"traffic": -20},
        ("winter", "plains"): {"road_condition": -10},
        # Spring: settlements brighten, forests become safer
        ("spring", "village"): {"mood": +10, "traffic": +10},
        ("spring", "city"): {"mood": +5, "traffic": +10},
        ("spring", "forest"): {"danger": -10},
        # Summer: cities & sea routes thrive, plains easy to traverse
        ("summer", "city"): {"traffic": +20},
        ("summer", "sea"): {"traffic": +20, "danger": -10},
        ("summer", "plains"): {"traffic": +15},
        # Autumn: wilds grow dangerous, dungeons more active
        ("autumn", "plains"): {"danger": +10},
        ("autumn", "forest"): {"danger": +10},
        ("autumn", "dungeon"): {"danger": +15},
    }

    # Internal event-generation density multiplier (§B-1).
    SIMULATION_DENSITY: float = 1.0

    def _run_year(self) -> None:
        """Run the remaining months of the current year through to month 12.

        If ``current_month`` is 1, this processes a full 12-month cycle.
        If called mid-year (e.g. ``current_month == 6``), only months 6..12
        are processed — earlier months are **not** replayed.

        Implemented via ``advance_months()`` so all simulation advancement
        shares the same code path.  Kept as a convenience for legacy callers
        (e.g. older tests that call ``_run_year()`` directly).
        """
        remaining = 12 - self.current_month + 1
        self.advance_months(remaining)

    def _events_for_month(self, month: int) -> int:
        """Number of random events to generate this month.

        Distributes ``events_per_year * SIMULATION_DENSITY`` evenly across
        12 months.  When the per-month quota has a fractional part, the
        remainder is resolved probabilistically so the *expected* yearly
        total equals ``events_per_year * SIMULATION_DENSITY`` exactly.

        :param month: current in-world month (1–12); reserved for future
            month-weight variations (e.g. more events in summer).
        """
        total = self.events_per_year * self.SIMULATION_DENSITY
        base = int(total / 12)
        remainder = total / 12 - base
        _FLOAT_EPS = 1e-9
        extra = 1 if (remainder > _FLOAT_EPS and self.rng.random() < remainder) else 0
        return base + extra

    def _run_month(self, month: int) -> None:
        """Process a single in-world month in strict chronological order.

        All events recorded inside this method are timestamped to *month*.
        Seasonal modifiers are applied at entry and reverted on exit (even on
        exception) via a try/finally guard.

        Processing is distributed across the year to avoid concentrating
        everything in a single month:

        - Month 1 (winter): Dying resolution, natural-death checks. Rumor aging.
        - Month 2 (winter): Injury recovery (early year, before adventure season).
        - Month 3 (spring): Adventure start and full-year progression.
        - Month 12 (winter): State propagation and rumor trim.
        - All months: Random events (density-scaled), rumor generation.

        Season mapping (``World.get_season``):
            12/1/2 = winter, 3/4/5 = spring, 6/7/8 = summer, 9/10/11 = autumn.
        """
        self.current_month = month
        self._apply_seasonal_modifiers(month)
        try:
            # --- Year-opening: dying resolution and natural death (month 1, winter) ---
            if month == 1:
                self._resolve_dying_characters()
                for char in list(self.world.characters):
                    result = self.event_system.check_natural_death(
                        char, self.world, rng=self.rng
                    )
                    if result is not None:
                        if result.event_type == "condition_worsened" and char.favorite:
                            self._favorites_worsened_this_year.add(char.char_id)
                        self._record_event(result, location_id=char.location_id)
                # Age existing rumors once per year at year-start
                active, expired = age_rumors(self.world.rumors, months=12)
                self.world.rumors = active
                self.world.rumor_archive.extend(expired)

            # --- Injury recovery (month 2, before adventure season) ---
            if month == 2:
                self._recover_injuries()

            # --- Adventure start and progression (month 3, spring) ---
            if month == 3:
                self._maybe_start_adventure()
                self._advance_adventures()

            # --- Random events distributed by SIMULATION_DENSITY (all months) ---
            for _ in range(self._events_for_month(month)):
                result = self.event_system.generate_random_event(
                    self.world.characters, self.world, rng=self.rng
                )
                if result is None:
                    break
                primary_id = result.affected_characters[0] if result.affected_characters else None
                primary_char = self.world.get_character_by_id(primary_id) if primary_id else None
                loc_id = primary_char.location_id if primary_char else None
                self._record_event(result, location_id=loc_id)

            # --- Rumor generation from this month's events (all months) ---
            new_rumors = generate_rumors_for_period(
                self.world, year=self.world.year, month=month, max_rumors=3, rng=self.rng,
            )
            self.world.rumors.extend(new_rumors)

            # --- Year-end processing (month 12) ---
            if month == 12:
                self.world.propagate_state()
                kept, trimmed = trim_rumors(self.world.rumors)
                self.world.rumors = kept
                self.world.rumor_archive.extend(trimmed)
        finally:
            self._revert_seasonal_modifiers()

    def _resolve_dying_characters(self) -> None:
        """Give dying characters a chance at rescue or death (design §8.3)."""
        for char in list(self.world.characters):
            if not char.alive or char.injury_status != "dying":
                continue
            result = self.event_system.check_dying_resolution(
                char, self.world, rng=self.rng
            )
            if result is not None:
                self._record_event(result, location_id=char.location_id)

    def _recover_injuries(self) -> None:
        """Give injured/serious characters a chance to recover during normal life.

        Recovery is staged (design §8): serious→injured (30%), injured→none (50%).
        Dying characters are handled separately in _resolve_dying_characters.
        """
        for char in self.world.characters:
            if not char.alive or char.injury_status not in ("injured", "serious"):
                continue
            # Serious: 30% chance to recover to injured
            if char.injury_status == "serious":
                if self.rng.random() < 0.3:
                    char.injury_status = "injured"
                    message = tr("condition_improved", name=char.name,
                                 status=tr("injury_status_injured"))
                    char.add_history(tr("history_condition_improved", year=self.world.year,
                                        status=tr("injury_status_injured")))
                    self._record_world_event(
                        message,
                        kind="injury_recovery",
                        location_id=char.location_id,
                        primary_actor_id=char.char_id,
                    )
                continue
            # Injured: 50% chance to recover to none
            if self.rng.random() < 0.5:
                char.injury_status = "none"
                message = tr("recovered_from_injuries", name=char.name)
                char.add_history(tr("history_recovered_from_injuries", year=self.world.year))
                self._record_world_event(
                    message,
                    kind="injury_recovery",
                    location_id=char.location_id,
                    primary_actor_id=char.char_id,
                )

    def _apply_seasonal_modifiers(self, month: int) -> None:
        """Apply seasonal modifiers to locations based on current month (design §5.7).

        Modifiers are temporary adjustments applied before events/adventures
        and reversed after, so they influence outcomes without permanently
        drifting location stats.
        """
        season = self.world.get_season(month)
        # Reset per-month: each invocation builds its own delta set so that
        # _revert_seasonal_modifiers() reverses exactly this month's changes.
        self._active_seasonal_deltas: List[tuple] = []
        for (s, region), deltas in self.SEASONAL_MODIFIERS.items():
            if s != season:
                continue
            for loc in self.world.grid.values():
                if loc.region_type != region:
                    continue
                for attr, delta in deltas.items():
                    if not hasattr(loc, attr):
                        continue
                    old_val = getattr(loc, attr)
                    new_val = max(0, min(100, old_val + delta))
                    setattr(loc, attr, new_val)
                    self._active_seasonal_deltas.append((loc, attr, new_val - old_val))

    def _revert_seasonal_modifiers(self) -> None:
        """Revert seasonal modifiers applied by _apply_seasonal_modifiers."""
        for loc, attr, applied_delta in self._active_seasonal_deltas:
            old_val = getattr(loc, attr)
            setattr(loc, attr, max(0, min(100, old_val - applied_delta)))
        self._active_seasonal_deltas.clear()

    def _generate_and_age_rumors(self) -> None:
        """Perform the full annual rumor cycle as a single batch operation.

        .. deprecated::
            The per-month rumor cycle is now handled incrementally inside
            ``_run_month()``: aging at month 1, generation each month, and
            trim at month 12.  This method is kept for callers that need to
            apply the full yearly cycle in one shot (e.g. external tooling or
            legacy tests); it is no longer called from ``_run_year()``.
        """
        active, expired = age_rumors(self.world.rumors, months=12)
        self.world.rumors = active
        self.world.rumor_archive.extend(expired)

        for gen_month in range(1, 13):
            new_rumors = generate_rumors_for_period(
                self.world,
                year=self.world.year,
                month=gen_month,
                max_rumors=3,
                rng=self.rng,
            )
            self.world.rumors.extend(new_rumors)

        kept, trimmed = trim_rumors(self.world.rumors)
        self.world.rumors = kept
        self.world.rumor_archive.extend(trimmed)

"""Daily timeline processing for the Simulator.

Contains the day-by-day simulation logic. Reports and high-level summaries
remain month-based, but the underlying world clock is now granular enough to
advance by day and to distribute health, adventure, and random-event activity
across the full year instead of pinning them to a few scripted months.
"""

from __future__ import annotations

from typing import Dict, List

from ..i18n import tr
from ..rumor import age_rumors, generate_rumors_for_period, trim_rumors
from .calendar import annual_probability_to_fraction, distributed_budget


class TimelineMixin:
    """Mixin providing daily processing methods for the Simulator.

    Expected attributes on *self* (provided by ``engine.Simulator``):
    - ``world``: the World instance
    - ``current_month``: current in-world month (1–12)
    - ``current_day``: current in-world day within month (1–30)
    - ``events_per_year``: target event count per year
    - ``adventure_steps_per_year``: target adventure step budget per year
    - ``event_system``: EventSystem instance
    - ``rng``: RNG for simulation decisions
    - ``_favorites_worsened_this_year``: set of char IDs
    - ``_active_seasonal_deltas``: list of (loc, attr, delta) tuples
    """

    # Seasonal modifiers applied to locations each month (design §5.7).
    SEASONAL_MODIFIERS: Dict[tuple, Dict[str, int]] = {
        ("winter", "mountain"): {"danger": +30, "road_condition": -20},
        ("winter", "forest"): {"danger": +15, "road_condition": -15},
        ("winter", "sea"): {"traffic": -20},
        ("winter", "plains"): {"road_condition": -10},
        ("spring", "village"): {"mood": +10, "traffic": +10},
        ("spring", "city"): {"mood": +5, "traffic": +10},
        ("spring", "forest"): {"danger": -10},
        ("summer", "city"): {"traffic": +20},
        ("summer", "sea"): {"traffic": +20, "danger": -10},
        ("summer", "plains"): {"traffic": +15},
        ("autumn", "plains"): {"danger": +10},
        ("autumn", "forest"): {"danger": +10},
        ("autumn", "dungeon"): {"danger": +15},
    }

    # Internal event-generation density multiplier (§B-1).
    SIMULATION_DENSITY: float = 1.0

    def _run_year(self) -> None:
        """Run from the current in-world day through the end of the current year."""
        self.advance_days(self.world.remaining_days_in_year(self.current_month, self.current_day))

    def _events_for_month(self, month: int) -> int:
        """Compatibility helper exposing the old month-level random-event budget."""
        return distributed_budget(
            self.events_per_year * self.SIMULATION_DENSITY,
            self.world.months_per_year,
            self.rng,
        )

    def _events_for_day(self, month: int, day: int) -> int:
        """Number of random events to generate on this in-world day."""
        del month, day
        return distributed_budget(
            self.events_per_year * self.SIMULATION_DENSITY,
            self.world.days_per_year,
            self.rng,
        )

    def _adventure_steps_for_day(self) -> int:
        """Number of adventure progression steps to process on this day."""
        return distributed_budget(
            self.adventure_steps_per_year,
            self.world.days_per_year,
            self.rng,
        )

    def _run_month(self, month: int) -> None:
        """Compatibility wrapper that processes an entire month day-by-day."""
        for day in range(1, self.world.days_in_month(month) + 1):
            self._run_day(month, day)

    def _run_day(self, month: int, day: int) -> None:
        """Process a single in-world day in chronological order."""
        year_fraction_per_day = 1.0 / self.world.days_per_year
        self.current_month = month
        self.current_day = day
        if day == 1:
            self._apply_seasonal_modifiers(month)
        try:
            self._resolve_dying_characters()

            for char in list(self.world.characters):
                active_adventure_id = char.active_adventure_id
                result = self.event_system.check_natural_death(
                    char,
                    self.world,
                    rng=self.rng,
                    year_fraction=year_fraction_per_day,
                )
                if result is not None:
                    if result.event_type == "condition_worsened" and char.favorite:
                        self._favorites_worsened_this_year.add(char.char_id)
                    self._record_event(result, location_id=char.location_id)
                    if result.event_type == "death" and active_adventure_id is not None:
                        self._finalize_completed_adventure_death(active_adventure_id)

            self._recover_injuries(year_fraction=year_fraction_per_day)

            self._maybe_start_adventure(year_fraction=year_fraction_per_day)
            adventure_steps = self._adventure_steps_for_day()
            if adventure_steps > 0:
                self._advance_adventures(steps=adventure_steps)

            for _ in range(self._events_for_day(month, day)):
                result = self.event_system.generate_random_event(
                    self.world.characters, self.world, rng=self.rng
                )
                if result is None:
                    break
                primary_id = result.affected_characters[0] if result.affected_characters else None
                primary_char = self.world.get_character_by_id(primary_id) if primary_id else None
                loc_id = primary_char.location_id if primary_char else None
                self._record_event(result, location_id=loc_id)

            if day == self.world.days_in_month(month):
                active, expired = age_rumors(self.world.rumors, months=1)
                self.world.rumors = active
                self.world.rumor_archive.extend(expired)

                new_rumors = generate_rumors_for_period(
                    self.world,
                    year=self.world.year,
                    month=month,
                    max_rumors=3,
                    rng=self.rng,
                )
                self.world.rumors.extend(new_rumors)

                propagation_months = self._propagation_month_window(month)
                if propagation_months > 0:
                    self.world.propagate_state(months=propagation_months)

                kept, trimmed = trim_rumors(self.world.rumors)
                self.world.rumors = kept
                self.world.rumor_archive.extend(trimmed)

                if month == self.world.months_per_year:
                    self._age_characters()
        finally:
            if day == self.world.days_in_month(month):
                self._revert_seasonal_modifiers()

    def _age_characters(self) -> None:
        """Advance every living character by one year exactly once per 360 days."""
        for char in self.world.characters:
            if not char.alive:
                continue
            result = self.event_system.event_aging(char, self.world, rng=self.rng)
            self._record_event(result, location_id=char.location_id)

    def _resolve_dying_characters(self) -> None:
        """Give dying characters a daily chance at rescue, decline, or stasis."""
        for char in list(self.world.characters):
            if not char.alive or char.injury_status != "dying":
                continue
            active_adventure_id = char.active_adventure_id
            result = self.event_system.check_dying_resolution(
                char,
                self.world,
                rng=self.rng,
                year_fraction=1.0 / self.world.days_per_year,
            )
            if result is not None:
                self._record_event(result, location_id=char.location_id)
                if result.event_type == "death" and active_adventure_id is not None:
                    self._finalize_completed_adventure_death(active_adventure_id)

    def _finalize_completed_adventure_death(self, adventure_id: str) -> None:
        """Apply world-memory side effects for a run that died outside normal step flow."""
        run = self.world.get_adventure_by_id(adventure_id)
        if run is None or run.outcome != "death":
            return
        self._apply_world_memory(run)
        if run not in self._recently_completed_adventures:
            self._recently_completed_adventures.append(run)

    def _recover_injuries(self, year_fraction: float = 1.0) -> None:
        """Apply recovery checks for the given fraction of an in-world year."""
        serious_daily = annual_probability_to_fraction(0.30, year_fraction)
        injured_daily = annual_probability_to_fraction(0.50, year_fraction)

        for char in self.world.characters:
            if not char.alive or char.injury_status not in ("injured", "serious"):
                continue
            if char.injury_status == "serious":
                if self.rng.random() < serious_daily:
                    char.injury_status = "injured"
                    message = tr(
                        "condition_improved",
                        name=char.name,
                        status=tr("injury_status_injured"),
                    )
                    char.add_history(
                        tr(
                            "history_condition_improved",
                            year=self.world.year,
                            status=tr("injury_status_injured"),
                        )
                    )
                    self._record_world_event(
                        message,
                        kind="injury_recovery",
                        location_id=char.location_id,
                        primary_actor_id=char.char_id,
                    )
                continue
            if self.rng.random() < injured_daily:
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
        """Apply seasonal modifiers to locations for the duration of one month."""
        season = self.world.season_for_month(month)
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
        """Perform the full annual rumor cycle as 12 month-end batches."""
        for gen_month in range(1, self.world.months_per_year + 1):
            active, expired = age_rumors(self.world.rumors, months=1)
            self.world.rumors = active
            self.world.rumor_archive.extend(expired)
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

    def _propagation_month_window(self, month: int) -> int:
        """Return how many months of state propagation to apply at this month-end."""
        months_per_year = self.world.months_per_year
        if months_per_year % 4 == 0:
            interval = max(1, months_per_year // 4)
            if month % interval == 0:
                return interval
            return 0
        if month == months_per_year:
            return months_per_year
        return 0

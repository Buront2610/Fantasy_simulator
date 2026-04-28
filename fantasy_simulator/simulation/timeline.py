"""Daily timeline processing for the Simulator.

Contains the day-by-day simulation logic. Reports and high-level summaries
remain month-based, but the underlying world clock is now granular enough to
advance by day and to distribute health, adventure, and random-event activity
across the full year instead of pinning them to a few scripted months.
"""

from __future__ import annotations

from ..i18n import tr
from .calendar import annual_probability_to_fraction, distributed_budget
from .timeline_calendar import propagation_month_window
from .timeline_pipeline import (
    DayPhaseContext,
    DayPhaseKind,
    build_day_phase_context,
    build_day_phase_plan,
)
from .timeline_rumors import generate_and_age_rumors_for_month, generate_and_age_rumors_for_year
from .timeline_seasons import (
    SEASONAL_MODIFIERS as DEFAULT_SEASONAL_MODIFIERS,
    apply_seasonal_modifiers,
    revert_seasonal_modifiers,
)


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
    SEASONAL_MODIFIERS = DEFAULT_SEASONAL_MODIFIERS

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
        day_context = self._build_day_phase_context(month, day)
        self.current_month = day_context.month
        self.current_day = day_context.day
        phase_handlers = {
            DayPhaseKind.MONTH_START: self._run_month_start_phase,
            DayPhaseKind.DYING_RESOLUTION: self._run_dying_resolution_phase,
            DayPhaseKind.NATURAL_HEALTH: self._run_natural_health_phase,
            DayPhaseKind.INJURY_RECOVERY: self._run_injury_recovery_phase,
            DayPhaseKind.ADVENTURE: self._run_adventure_phase,
            DayPhaseKind.RANDOM_EVENTS: self._run_random_event_phase,
            DayPhaseKind.MONTH_END: self._run_month_end_phase,
        }
        try:
            for phase in self._day_phase_plan(day_context):
                phase_handlers[phase.kind](day_context)
        finally:
            self._finish_day(day_context)

    def _build_day_phase_context(self, month: int, day: int) -> DayPhaseContext:
        """Build immutable date metadata shared by daily processing phases."""
        return build_day_phase_context(
            month=month,
            day=day,
            days_in_month=self.world.days_in_month(month),
            days_per_year=self.world.days_per_year,
        )

    def _day_phase_plan(self, day_context: DayPhaseContext):
        """Return the explicit chronological pipeline for one in-world day."""
        return build_day_phase_plan(day_context)

    def _finish_day(self, day_context: DayPhaseContext) -> None:
        """Run cleanup that must happen even if a day phase raises."""
        if day_context.is_month_end:
            self._revert_seasonal_modifiers()

    def _run_month_start_phase(self, day_context: DayPhaseContext) -> None:
        """Apply month-opening effects before other daily activity."""
        self._apply_seasonal_modifiers(day_context.month)

    def _run_dying_resolution_phase(self, day_context: DayPhaseContext) -> None:
        """Resolve existing dying states before new daily checks occur."""
        self._resolve_dying_characters(year_fraction=day_context.year_fraction_per_day)

    def _run_natural_health_phase(self, day_context: DayPhaseContext) -> None:
        """Process daily natural death and condition-worsening checks."""
        for char in list(self.world.characters):
            self._process_natural_health_check(char, day_context.year_fraction_per_day)

    def _process_natural_health_check(self, char, year_fraction: float) -> None:
        """Run the daily natural-health check for a single character."""
        active_adventure_id = char.active_adventure_id
        result = self.event_system.check_natural_death(
            char,
            self.world,
            rng=self.rng,
            year_fraction=year_fraction,
        )
        if result is None:
            return
        if result.event_type == "condition_worsened" and char.favorite:
            self._favorites_worsened_this_year.add(char.char_id)
        self._record_event(result, location_id=char.location_id)
        if result.event_type == "death" and active_adventure_id is not None:
            self._finalize_completed_adventure_death(active_adventure_id)

    def _run_injury_recovery_phase(self, day_context: DayPhaseContext) -> None:
        """Apply non-fatal injury recovery after daily health degradation."""
        self._recover_injuries(year_fraction=day_context.year_fraction_per_day)

    def _run_adventure_phase(self, day_context: DayPhaseContext) -> None:
        """Start and advance adventures after health changes settle."""
        self._maybe_start_adventure(year_fraction=day_context.year_fraction_per_day)
        adventure_steps = self._adventure_steps_for_day()
        if adventure_steps > 0:
            self._advance_adventures(steps=adventure_steps)

    def _run_random_event_phase(self, day_context: DayPhaseContext) -> None:
        """Generate free-form random events after deterministic daily systems."""
        for _ in range(self._events_for_day(day_context.month, day_context.day)):
            result = self.event_system.generate_random_event(
                self.world.characters, self.world, rng=self.rng
            )
            if result is None:
                break
            primary_id = result.affected_characters[0] if result.affected_characters else None
            primary_char = self.world.get_character_by_id(primary_id) if primary_id else None
            loc_id = primary_char.location_id if primary_char else None
            self._record_event(result, location_id=loc_id)

    def _run_month_end_phase(self, day_context: DayPhaseContext) -> None:
        """Run month-closing rumor, propagation, and year-end updates."""
        self._run_month_end_rumor_phase(day_context.month)
        self._run_month_end_state_phase(day_context.month)
        self._run_year_end_phase(day_context.month)

    def _run_month_end_rumor_phase(self, month: int) -> None:
        """Age, generate, and trim rumors at month end."""
        generate_and_age_rumors_for_month(
            self.world,
            year=self.world.year,
            month=month,
            rng=self.rng,
        )

    def _run_month_end_state_phase(self, month: int) -> None:
        """Propagate world state on configured month-end intervals."""
        propagation_months = self._propagation_month_window(month)
        if propagation_months > 0:
            self.world.propagate_state(months=propagation_months)

    def _run_year_end_phase(self, month: int) -> None:
        """Advance annual character aging only at the last month of the year."""
        if month == self.world.months_per_year:
            self._age_characters()

    def _age_characters(self) -> None:
        """Advance every living character by one year exactly once per 360 days."""
        for char in self.world.characters:
            if not char.alive:
                continue
            result = self.event_system.event_aging(char, self.world, rng=self.rng)
            self._record_event(result, location_id=char.location_id)

    def _resolve_dying_characters(self, year_fraction: float | None = None) -> None:
        """Give dying characters a daily chance at rescue, decline, or stasis."""
        effective_year_fraction = (
            1.0 / self.world.days_per_year
            if year_fraction is None
            else year_fraction
        )
        for char in list(self.world.characters):
            if not char.alive or char.injury_status != "dying":
                continue
            active_adventure_id = char.active_adventure_id
            result = self.event_system.check_dying_resolution(
                char,
                self.world,
                rng=self.rng,
                year_fraction=effective_year_fraction,
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
        self._active_seasonal_deltas = apply_seasonal_modifiers(self.world, month)

    def _revert_seasonal_modifiers(self) -> None:
        """Revert seasonal modifiers applied by _apply_seasonal_modifiers."""
        revert_seasonal_modifiers(self._active_seasonal_deltas)

    def _generate_and_age_rumors(self) -> None:
        """Perform the full annual rumor cycle as 12 month-end batches."""
        generate_and_age_rumors_for_year(self.world, rng=self.rng)

    def _propagation_month_window(self, month: int) -> int:
        """Return how many months of state propagation to apply at this month-end."""
        return propagation_month_window(month, self.world.months_per_year)

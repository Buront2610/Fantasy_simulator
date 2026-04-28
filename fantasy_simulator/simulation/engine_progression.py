"""Calendar advancement helpers for :class:`~.engine.Simulator`."""

from __future__ import annotations


class EngineProgressionMixin:
    """Run and advance the world simulation clock."""

    def run(self, years: int = 10) -> None:
        """Simulate *years* years of in-world history."""
        self.advance_years(years)

    def advance_years(self, years: int = 1) -> None:
        """Advance the simulation by exactly *years x 360* in-world days."""
        self.advance_days(years * self.world.days_per_year)

    def advance_months(self, months: int = 1) -> None:
        """Advance the simulation by *months* in-world months."""
        total_days = 0
        month_cursor = self.current_month
        day_cursor = self.current_day
        for _ in range(months):
            total_days += self.world.days_in_month(month_cursor) - day_cursor + 1
            month_cursor += 1
            if month_cursor > self.world.months_per_year:
                month_cursor = 1
            day_cursor = 1
        self.advance_days(total_days)

    def advance_days(self, days: int = 1) -> None:
        """Advance the simulation by *days* in-world days.

        This is the canonical progression path. Month and year helpers
        delegate here so that partial-month state is preserved naturally.
        """
        self.pending_notifications.clear()
        for _ in range(days):
            if self.current_month == 1 and self.current_day == 1:
                self._reset_yearly_trackers()
            self._run_day(self.current_month, self.current_day)
            self.current_month, self.current_day, year_delta = self.world.advance_calendar_position(
                self.current_month,
                self.current_day,
                days=1,
            )
            self.elapsed_days += 1
            if year_delta:
                self.world.advance_time(year_delta)

    def _reset_yearly_trackers(self) -> None:
        """Clear per-year transient state at a new in-world year boundary."""
        self._recently_completed_adventures.clear()
        self._favorites_worsened_this_year.clear()

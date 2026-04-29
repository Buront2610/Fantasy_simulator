"""Calendar-facing API methods mixed into ``World``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Optional, Tuple

from . import world_calendar_facade as calendar_facade
from .content.setting_bundle import CalendarDefinition
from .world_records import CalendarChangeRecord

if TYPE_CHECKING:
    from .content.setting_bundle import SettingBundle


CloneCalendar = Callable[[CalendarDefinition], CalendarDefinition]


def clone_calendar(calendar: CalendarDefinition) -> CalendarDefinition:
    return CalendarDefinition.from_dict(calendar.to_dict())


class WorldCalendarMixin:
    """Compatibility API surface for world calendar helpers."""

    if TYPE_CHECKING:
        _setting_bundle: SettingBundle
        calendar_baseline: CalendarDefinition
        calendar_history: List[CalendarChangeRecord]
        year: int

        def _maybe_evolve_languages_for_year(self, year: int) -> None: ...

    def months_elapsed_between(
        self,
        start_year: int,
        start_month: int,
        end_year: int,
        end_month: int,
        *,
        start_day: int = 1,
        end_day: int = 1,
        start_calendar_key: str = "",
    ) -> int:
        """Return completed month boundaries between two in-world dates."""
        return calendar_facade.months_elapsed_between(
            self,
            start_year=start_year,
            start_month=start_month,
            end_year=end_year,
            end_month=end_month,
            start_day=start_day,
            end_day=end_day,
            start_calendar_key=start_calendar_key,
        )

    def _base_calendar_ref(self) -> CalendarDefinition:
        return calendar_facade.base_calendar_ref(self)

    @property
    def calendar_definition(self):
        return calendar_facade.calendar_definition(self, clone_calendar=clone_calendar)

    @property
    def months_per_year(self) -> int:
        return calendar_facade.months_per_year(self)

    @property
    def days_per_year(self) -> int:
        return calendar_facade.days_per_year(self)

    def days_in_month(self, month: int) -> int:
        return calendar_facade.days_in_month(self, month)

    def month_display_name(self, month: int) -> str:
        return calendar_facade.month_display_name(self, month)

    def _calendar_definition_by_key_ref(self, calendar_key: str) -> CalendarDefinition:
        return calendar_facade.calendar_definition_by_key_ref(self, calendar_key)

    def calendar_definition_by_key(self, calendar_key: str) -> CalendarDefinition:
        return calendar_facade.calendar_definition_by_key(
            self,
            calendar_key,
            clone_calendar=clone_calendar,
        )

    def _calendar_definition_for_date_ref(
        self,
        year: int,
        month: int = 1,
        day: int = 1,
        *,
        calendar_key: str = "",
    ) -> CalendarDefinition:
        return calendar_facade.calendar_definition_for_date_ref(
            self,
            year=year,
            month=month,
            day=day,
            calendar_key=calendar_key,
        )

    def calendar_definition_for_date(
        self,
        year: int,
        month: int = 1,
        day: int = 1,
        *,
        calendar_key: str = "",
    ) -> CalendarDefinition:
        return calendar_facade.calendar_definition_for_date(
            self,
            year,
            month,
            day,
            calendar_key=calendar_key,
            clone_calendar=clone_calendar,
        )

    def months_per_year_for_date(
        self, year: int, month: int = 1, day: int = 1, *, calendar_key: str = ""
    ) -> int:
        return calendar_facade.months_per_year_for_date(
            self,
            year,
            month,
            day,
            calendar_key=calendar_key,
        )

    def month_display_name_for_date(
        self, year: int, month: int, day: int = 1, *, calendar_key: str = ""
    ) -> str:
        return calendar_facade.month_display_name_for_date(
            self,
            year,
            month,
            day,
            calendar_key=calendar_key,
        )

    @staticmethod
    def get_season(month: int) -> str:
        """Return the default season mapping used by the built-in calendar."""
        return calendar_facade.default_season(month)

    def season_for_month(self, month: int) -> str:
        """Return the season for a month in the active world definition."""
        return calendar_facade.season_for_month(self, month)

    def season_for_date(
        self, year: int, month: int, day: int = 1, *, calendar_key: str = ""
    ) -> str:
        """Return the season for a historical date using the relevant calendar."""
        return calendar_facade.season_for_date(
            self,
            year=year,
            month=month,
            day=day,
            calendar_key=calendar_key,
        )

    def clamp_calendar_position(self, month: int, day: int) -> Tuple[int, int]:
        """Clamp month/day into the active calendar's valid ranges."""
        return calendar_facade.clamp_calendar_position(self, month, day)

    def apply_calendar_definition(
        self,
        calendar: CalendarDefinition,
        *,
        changed_year: Optional[int] = None,
        changed_month: int = 1,
        changed_day: int = 1,
    ) -> None:
        """Apply a new active calendar immediately and record its change date."""
        calendar_facade.apply_calendar_definition(
            self,
            calendar=calendar,
            clone_calendar=clone_calendar,
            build_change_record=lambda year, month, day, changed_calendar: CalendarChangeRecord(
                year=year,
                month=month,
                day=day,
                calendar=changed_calendar,
            ),
            changed_year=changed_year,
            changed_month=changed_month,
            changed_day=changed_day,
        )

    def remaining_days_in_year(self, month: int, day: int) -> int:
        """Return how many in-world days remain including the current date."""
        return calendar_facade.remaining_days_in_year(self, month, day)

    def advance_calendar_position(self, month: int, day: int, days: int = 1) -> Tuple[int, int, int]:
        """Advance a month/day position and return ``(month, day, year_delta)``."""
        return calendar_facade.advance_calendar_position(
            self,
            month,
            day,
            days=days,
        )

    def advance_time(self, years: int = 1) -> None:
        for _ in range(max(0, int(years))):
            self.year += 1
            self._maybe_evolve_languages_for_year(self.year)

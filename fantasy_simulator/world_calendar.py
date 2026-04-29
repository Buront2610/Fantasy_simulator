"""Historical calendar helpers for ``World``.

This module isolates calendar resolution and date arithmetic from the world
aggregate so ``World`` can remain a facade over its calendar state.
"""

from __future__ import annotations

from typing import Callable, Iterable, List, Optional, Protocol, Tuple, TypeVar

from .content.setting_bundle import CalendarDefinition


class SupportsCalendarChange(Protocol):
    year: int
    month: int
    day: int
    calendar: CalendarDefinition


TCalendarChange = TypeVar("TCalendarChange", bound=SupportsCalendarChange)


def clone_calendar(calendar: CalendarDefinition) -> CalendarDefinition:
    return CalendarDefinition.from_dict(calendar.to_dict())


def sort_calendar_history(history: Iterable[TCalendarChange]) -> List[TCalendarChange]:
    return sorted(history, key=lambda item: (item.year, item.month, item.day))


def default_season(month: int) -> str:
    """Return the default season mapping used by the built-in calendar."""
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    return "autumn"


def calendar_definition_by_key_ref(
    *,
    base_calendar: CalendarDefinition,
    calendar_baseline: CalendarDefinition,
    calendar_history: Iterable[SupportsCalendarChange],
    calendar_key: str,
) -> CalendarDefinition:
    if not calendar_key:
        return base_calendar
    if base_calendar.calendar_key == calendar_key:
        return base_calendar
    if calendar_baseline.calendar_key == calendar_key:
        return calendar_baseline
    for entry in reversed(sort_calendar_history(calendar_history)):
        if entry.calendar.calendar_key == calendar_key:
            return entry.calendar
    return base_calendar


def calendar_definition_for_date_ref(
    *,
    base_calendar: CalendarDefinition,
    calendar_baseline: CalendarDefinition,
    calendar_history: Iterable[SupportsCalendarChange],
    year: int,
    month: int = 1,
    day: int = 1,
    calendar_key: str = "",
) -> CalendarDefinition:
    if calendar_key:
        return calendar_definition_by_key_ref(
            base_calendar=base_calendar,
            calendar_baseline=calendar_baseline,
            calendar_history=calendar_history,
            calendar_key=calendar_key,
        )
    target = (int(year), max(1, int(month)), max(1, int(day)))
    selected = calendar_baseline
    for entry in sort_calendar_history(calendar_history):
        if (entry.year, entry.month, entry.day) <= target:
            selected = entry.calendar
        else:
            break
    return selected


def months_elapsed_between(
    *,
    calendar_definition_for_date_ref_fn: Callable[..., CalendarDefinition],
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
    start_day: int = 1,
    end_day: int = 1,
    start_calendar_key: str = "",
) -> int:
    """Return completed month boundaries between two in-world dates."""
    start = (int(start_year), max(1, int(start_month)), max(1, int(start_day)))
    end = (int(end_year), max(1, int(end_month)), max(1, int(end_day)))
    if end < start:
        return 0

    elapsed = 0
    cursor_year, cursor_month, cursor_day = start
    cursor_calendar_key = start_calendar_key

    while True:
        calendar = calendar_definition_for_date_ref_fn(
            cursor_year,
            cursor_month,
            cursor_day,
            calendar_key=cursor_calendar_key,
        )
        next_year = cursor_year
        next_month = cursor_month + 1
        if next_month > calendar.months_per_year:
            next_month = 1
            next_year += 1
        if (next_year, next_month, 1) > end:
            break
        elapsed += 1
        cursor_year, cursor_month, cursor_day = next_year, next_month, 1
        cursor_calendar_key = ""

    return elapsed


def season_for_month(calendar: CalendarDefinition, month: int) -> str:
    season = calendar.season_for_month(month)
    if season != "unknown":
        return season
    return default_season(month)


def season_for_date(
    *,
    base_calendar: CalendarDefinition,
    calendar_baseline: CalendarDefinition,
    calendar_history: Iterable[SupportsCalendarChange],
    year: int,
    month: int,
    day: int = 1,
    calendar_key: str = "",
) -> str:
    calendar = calendar_definition_for_date_ref(
        base_calendar=base_calendar,
        calendar_baseline=calendar_baseline,
        calendar_history=calendar_history,
        year=year,
        month=month,
        day=day,
        calendar_key=calendar_key,
    )
    return season_for_month(calendar, month)


def clamp_calendar_position(calendar: CalendarDefinition, month: int, day: int) -> Tuple[int, int]:
    clamped_month = max(1, min(calendar.months_per_year, int(month)))
    clamped_day = max(1, min(calendar.days_in_month(clamped_month), int(day)))
    return clamped_month, clamped_day


def apply_calendar_definition_history(
    *,
    calendar: CalendarDefinition,
    current_year: int,
    calendar_history: Iterable[TCalendarChange],
    build_change_record: Callable[[int, int, int, CalendarDefinition], TCalendarChange],
    changed_year: Optional[int] = None,
    changed_month: int = 1,
    changed_day: int = 1,
) -> List[TCalendarChange]:
    month = max(1, min(calendar.months_per_year, int(changed_month)))
    day = max(1, min(calendar.days_in_month(month), int(changed_day)))
    updated = list(calendar_history)
    updated.append(
        build_change_record(
            current_year if changed_year is None else changed_year,
            month,
            day,
            clone_calendar(calendar),
        )
    )
    return sort_calendar_history(updated)


def remaining_days_in_year(calendar: CalendarDefinition, month: int, day: int) -> int:
    clamped_month, clamped_day = clamp_calendar_position(calendar, month, day)
    remaining = calendar.days_in_month(clamped_month) - clamped_day + 1
    for month_index in range(clamped_month + 1, calendar.months_per_year + 1):
        remaining += calendar.days_in_month(month_index)
    return remaining


def advance_calendar_position(
    calendar: CalendarDefinition,
    month: int,
    day: int,
    *,
    days: int = 1,
) -> Tuple[int, int, int]:
    """Advance a month/day position and return ``(month, day, year_delta)``."""
    current_month, current_day = clamp_calendar_position(calendar, month, day)
    year_delta = 0
    for _ in range(max(0, int(days))):
        current_day += 1
        if current_day > calendar.days_in_month(current_month):
            current_day = 1
            current_month += 1
            if current_month > calendar.months_per_year:
                current_month = 1
                year_delta += 1
    return current_month, current_day, year_delta

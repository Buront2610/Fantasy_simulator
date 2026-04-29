"""Facade helpers for calendar methods exposed by ``World``."""

from __future__ import annotations

from typing import Any, Callable, Optional, Tuple

from .content.setting_bundle import CalendarDefinition
from .world_calendar import (
    advance_calendar_position as advance_calendar_position_for_calendar,
    apply_calendar_definition_history,
    calendar_definition_by_key_ref as resolve_calendar_definition_by_key_ref,
    calendar_definition_for_date_ref as resolve_calendar_definition_for_date_ref,
    clamp_calendar_position as clamp_calendar_position_for_calendar,
    default_season as default_calendar_season,
    months_elapsed_between as months_elapsed_between_for_calendar,
    remaining_days_in_year as remaining_days_in_year_for_calendar,
    season_for_date as season_for_calendar_date,
    season_for_month as season_for_calendar,
)


CloneCalendar = Callable[[CalendarDefinition], CalendarDefinition]
BuildCalendarChangeRecord = Callable[[int, int, int, CalendarDefinition], Any]


def default_season(month: int) -> str:
    return default_calendar_season(month)


def base_calendar_ref(world: Any) -> CalendarDefinition:
    return world._setting_bundle.world_definition.calendar


def calendar_definition(world: Any, *, clone_calendar: CloneCalendar) -> CalendarDefinition:
    return clone_calendar(base_calendar_ref(world))


def months_per_year(world: Any) -> int:
    return base_calendar_ref(world).months_per_year


def days_per_year(world: Any) -> int:
    return base_calendar_ref(world).days_per_year


def days_in_month(world: Any, month: int) -> int:
    return base_calendar_ref(world).days_in_month(month)


def month_display_name(world: Any, month: int) -> str:
    return base_calendar_ref(world).month_display_name(month)


def calendar_definition_by_key_ref(world: Any, calendar_key: str) -> CalendarDefinition:
    return resolve_calendar_definition_by_key_ref(
        base_calendar=base_calendar_ref(world),
        calendar_baseline=world.calendar_baseline,
        calendar_history=world.calendar_history,
        calendar_key=calendar_key,
    )


def calendar_definition_by_key(
    world: Any,
    calendar_key: str,
    *,
    clone_calendar: CloneCalendar,
) -> CalendarDefinition:
    return clone_calendar(calendar_definition_by_key_ref(world, calendar_key))


def calendar_definition_for_date_ref(
    world: Any,
    year: int,
    month: int = 1,
    day: int = 1,
    *,
    calendar_key: str = "",
) -> CalendarDefinition:
    return resolve_calendar_definition_for_date_ref(
        base_calendar=base_calendar_ref(world),
        calendar_baseline=world.calendar_baseline,
        calendar_history=world.calendar_history,
        year=year,
        month=month,
        day=day,
        calendar_key=calendar_key,
    )


def calendar_definition_for_date(
    world: Any,
    year: int,
    month: int = 1,
    day: int = 1,
    *,
    calendar_key: str = "",
    clone_calendar: CloneCalendar,
) -> CalendarDefinition:
    return clone_calendar(
        calendar_definition_for_date_ref(
            world,
            year,
            month,
            day,
            calendar_key=calendar_key,
        )
    )


def months_elapsed_between(
    world: Any,
    *,
    start_year: int,
    start_month: int,
    end_year: int,
    end_month: int,
    start_day: int = 1,
    end_day: int = 1,
    start_calendar_key: str = "",
) -> int:
    return months_elapsed_between_for_calendar(
        calendar_definition_for_date_ref_fn=world._calendar_definition_for_date_ref,
        start_year=start_year,
        start_month=start_month,
        end_year=end_year,
        end_month=end_month,
        start_day=start_day,
        end_day=end_day,
        start_calendar_key=start_calendar_key,
    )


def months_per_year_for_date(
    world: Any,
    year: int,
    month: int = 1,
    day: int = 1,
    *,
    calendar_key: str = "",
) -> int:
    return calendar_definition_for_date_ref(
        world,
        year,
        month,
        day,
        calendar_key=calendar_key,
    ).months_per_year


def month_display_name_for_date(
    world: Any,
    year: int,
    month: int,
    day: int = 1,
    *,
    calendar_key: str = "",
) -> str:
    calendar = calendar_definition_for_date_ref(
        world,
        year,
        month,
        day,
        calendar_key=calendar_key,
    )
    return calendar.month_display_name(month)


def season_for_month(world: Any, month: int) -> str:
    return season_for_calendar(base_calendar_ref(world), month)


def season_for_date(
    world: Any,
    year: int,
    month: int,
    day: int = 1,
    *,
    calendar_key: str = "",
) -> str:
    return season_for_calendar_date(
        base_calendar=base_calendar_ref(world),
        calendar_baseline=world.calendar_baseline,
        calendar_history=world.calendar_history,
        year=year,
        month=month,
        day=day,
        calendar_key=calendar_key,
    )


def clamp_calendar_position(world: Any, month: int, day: int) -> Tuple[int, int]:
    return clamp_calendar_position_for_calendar(base_calendar_ref(world), month, day)


def apply_calendar_definition(
    world: Any,
    calendar: CalendarDefinition,
    *,
    clone_calendar: CloneCalendar,
    build_change_record: BuildCalendarChangeRecord,
    changed_year: Optional[int] = None,
    changed_month: int = 1,
    changed_day: int = 1,
) -> None:
    world._setting_bundle.world_definition.calendar = clone_calendar(calendar)
    world.calendar_history = apply_calendar_definition_history(
        calendar=calendar,
        current_year=world.year,
        calendar_history=world.calendar_history,
        build_change_record=build_change_record,
        changed_year=changed_year,
        changed_month=changed_month,
        changed_day=changed_day,
    )


def remaining_days_in_year(world: Any, month: int, day: int) -> int:
    return remaining_days_in_year_for_calendar(base_calendar_ref(world), month, day)


def advance_calendar_position(
    world: Any,
    month: int,
    day: int,
    days: int = 1,
) -> Tuple[int, int, int]:
    return advance_calendar_position_for_calendar(
        base_calendar_ref(world),
        month,
        day,
        days=days,
    )

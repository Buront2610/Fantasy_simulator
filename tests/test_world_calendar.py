from __future__ import annotations

from fantasy_simulator.content.setting_bundle import CalendarDefinition, CalendarMonthDefinition
from fantasy_simulator.world import CalendarChangeRecord
from fantasy_simulator.world_calendar import (
    advance_calendar_position,
    apply_calendar_definition_history,
    calendar_definition_for_date_ref,
)


def test_calendar_definition_for_date_ref_uses_latest_history_before_target_date() -> None:
    baseline = CalendarDefinition(
        calendar_key="baseline",
        display_name="Baseline",
        months=[CalendarMonthDefinition("one", "One", 30)],
    )
    first = CalendarDefinition(
        calendar_key="first",
        display_name="First",
        months=[
            CalendarMonthDefinition("one", "One", 30),
            CalendarMonthDefinition("two", "Two", 30),
        ],
    )
    second = CalendarDefinition(
        calendar_key="second",
        display_name="Second",
        months=[CalendarMonthDefinition("one", "One", 45)],
    )
    history = [
        CalendarChangeRecord(year=1001, month=2, day=1, calendar=first),
        CalendarChangeRecord(year=1003, month=1, day=1, calendar=second),
    ]

    assert calendar_definition_for_date_ref(
        base_calendar=second,
        calendar_baseline=baseline,
        calendar_history=history,
        year=1001,
        month=1,
        day=30,
    ).calendar_key == "baseline"
    assert calendar_definition_for_date_ref(
        base_calendar=second,
        calendar_baseline=baseline,
        calendar_history=history,
        year=1002,
        month=1,
        day=1,
    ).calendar_key == "first"


def test_apply_calendar_definition_history_clamps_and_sorts_changes() -> None:
    calendar = CalendarDefinition(
        calendar_key="moonstep",
        display_name="Moonstep",
        months=[
            CalendarMonthDefinition("wax", "Wax", 20),
            CalendarMonthDefinition("wane", "Wane", 35),
        ],
    )
    history = [
        CalendarChangeRecord(
            year=1005,
            month=2,
            day=10,
            calendar=CalendarDefinition(
                calendar_key="older",
                display_name="Older",
                months=[CalendarMonthDefinition("old", "Old", 30)],
            ),
        )
    ]

    updated = apply_calendar_definition_history(
        calendar=calendar,
        current_year=1004,
        calendar_history=history,
        build_change_record=lambda year, month, day, changed_calendar: CalendarChangeRecord(
            year=year,
            month=month,
            day=day,
            calendar=changed_calendar,
        ),
        changed_month=9,
        changed_day=99,
    )

    assert [(entry.year, entry.month, entry.day) for entry in updated] == [(1004, 2, 35), (1005, 2, 10)]
    assert updated[0].calendar.calendar_key == "moonstep"


def test_advance_calendar_position_respects_variable_month_lengths_helper() -> None:
    calendar = CalendarDefinition(
        calendar_key="moonstep",
        display_name="Moonstep",
        months=[
            CalendarMonthDefinition("wax", "Wax", 10),
            CalendarMonthDefinition("wane", "Wane", 40),
        ],
    )

    assert advance_calendar_position(calendar, 1, 10, days=1) == (2, 1, 0)
    assert advance_calendar_position(calendar, 2, 40, days=1) == (1, 1, 1)

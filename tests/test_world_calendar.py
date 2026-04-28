from __future__ import annotations

from fantasy_simulator.content.setting_bundle import CalendarDefinition, CalendarMonthDefinition
from fantasy_simulator.world import CalendarChangeRecord
from fantasy_simulator.world_calendar import (
    advance_calendar_position,
    apply_calendar_definition_history,
    calendar_definition_for_date_ref,
)
from fantasy_simulator import world_calendar_facade


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


def test_calendar_facade_preserves_world_wrapper_semantics_without_world_construction() -> None:
    baseline = CalendarDefinition(
        calendar_key="baseline",
        display_name="Baseline",
        months=[CalendarMonthDefinition("first", "First", 30, season="winter")],
    )
    replacement = CalendarDefinition(
        calendar_key="replacement",
        display_name="Replacement",
        months=[
            CalendarMonthDefinition("wax", "Wax", 12, season="spring"),
            CalendarMonthDefinition("wane", "Wane", 40, season="summer"),
        ],
    )

    class _WorldDefinition:
        calendar = baseline

    class _SettingBundle:
        world_definition = _WorldDefinition()

    class _World:
        _setting_bundle = _SettingBundle()
        calendar_baseline = CalendarDefinition.from_dict(baseline.to_dict())
        calendar_history = []
        year = 1004

        def _calendar_definition_for_date_ref(self, year, month=1, day=1, *, calendar_key=""):
            return world_calendar_facade.calendar_definition_for_date_ref(
                self,
                year,
                month,
                day,
                calendar_key=calendar_key,
            )

    world = _World()

    world_calendar_facade.apply_calendar_definition(
        world,
        replacement,
        clone_calendar=lambda calendar: CalendarDefinition.from_dict(calendar.to_dict()),
        build_change_record=lambda year, month, day, calendar: CalendarChangeRecord(
            year=year,
            month=month,
            day=day,
            calendar=calendar,
        ),
        changed_month=8,
        changed_day=99,
    )
    replacement.display_name = "Mutated Elsewhere"

    assert world_calendar_facade.months_per_year(world) == 2
    assert world_calendar_facade.days_in_month(world, 2) == 40
    assert world_calendar_facade.month_display_name(world, 2) == "Wane"
    assert world_calendar_facade.month_display_name_for_date(world, 1005, 2) == "Wane"
    assert world_calendar_facade.season_for_date(world, 1005, 2) == "summer"
    assert world_calendar_facade.remaining_days_in_year(world, 1, 12) == 41
    assert world_calendar_facade.advance_calendar_position(world, 2, 40, days=1) == (1, 1, 1)
    assert world.calendar_history[0].month == 2
    assert world.calendar_history[0].day == 40
    assert world._setting_bundle.world_definition.calendar.display_name == "Replacement"

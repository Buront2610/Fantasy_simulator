from __future__ import annotations

from fantasy_simulator.world_event.models import WorldEventRecord
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.world import World
from fantasy_simulator.world_event import log_facade
from fantasy_simulator.world_event.log import format_event_log_entry, project_event_log_lines


def _translate(key: str, **kwargs: object) -> str:
    if key == "event_log_prefix":
        return f"[Y{kwargs['year']}]"
    if key == "event_log_prefix_month":
        return f"[Y{kwargs['year']} M{kwargs['month']}]"
    if key == "event_log_prefix_day":
        return f"[Y{kwargs['year']} M{kwargs['month']} D{kwargs['day']}]"
    if key == "event_change_no_faction":
        return "none"
    if key == "events.location_faction_changed.summary":
        return (
            f"{kwargs['location']} changed controlling faction from "
            f"{kwargs['old_faction']} to {kwargs['new_faction']}."
        )
    raise AssertionError(key)


def test_format_event_log_entry_year_only() -> None:
    entry = format_event_log_entry("hello", translate=_translate, year=1000)
    assert entry == "[Y1000] hello"


def test_format_event_log_entry_year_month() -> None:
    entry = format_event_log_entry("hello", translate=_translate, year=1000, month=2)
    assert entry == "[Y1000 M2] hello"


def test_format_event_log_entry_year_month_day() -> None:
    entry = format_event_log_entry("hello", translate=_translate, year=1000, month=2, day=3)
    assert entry == "[Y1000 M2 D3] hello"


def test_format_event_log_entry_day_without_month_uses_year_only() -> None:
    entry = format_event_log_entry("hello", translate=_translate, year=1000, day=3)
    assert entry == "[Y1000] hello"


def test_project_event_log_lines_uses_canonical_description() -> None:
    records = [
        WorldEventRecord(kind="battle", year=1000, description="new-format"),
    ]

    projected = project_event_log_lines(records, max_event_log=10, translate=_translate)
    assert projected == ["[Y1000 M1 D1] new-format"]


def test_project_event_log_lines_with_zero_limit_returns_empty_list() -> None:
    records = [
        WorldEventRecord(kind="meeting", year=1000, description="hidden"),
    ]

    assert project_event_log_lines(records, max_event_log=0, translate=_translate) == []


def test_project_event_log_lines_uses_formatting() -> None:
    records = [
        WorldEventRecord(kind="battle", year=1001, month=6, day=4, description="battle"),
    ]

    projected = project_event_log_lines(records, max_event_log=10, translate=_translate)
    assert projected == ["[Y1001 M6 D4] battle"]


def test_project_event_log_lines_uses_record_description_without_world_context() -> None:
    records = [
        WorldEventRecord(
            kind="location_faction_changed",
            year=1001,
            month=6,
            day=4,
            description="Aethoria Capital changed controlling faction from none to stormwatch_wardens.",
            summary_key="events.location_faction_changed.summary",
            render_params={
                "location": "Aethoria Capital",
                "old_faction_id": None,
                "new_faction_id": "stormwatch_wardens",
            },
        ),
    ]

    projected = project_event_log_lines(records, max_event_log=10, translate=_translate)

    assert projected == [
        "[Y1001 M6 D4] Aethoria Capital changed controlling faction from none to stormwatch_wardens."
    ]


def test_world_event_log_view_uses_world_context_for_authored_faction_names() -> None:
    previous_locale = get_locale()
    set_locale("en")
    world = World()
    world.record_event(
        WorldEventRecord(
            kind="location_faction_changed",
            year=1001,
            month=6,
            day=4,
            description="Aethoria Capital changed controlling faction from none to stormwatch_wardens.",
            summary_key="events.location_faction_changed.summary",
            render_params={
                "location": "Aethoria Capital",
                "old_faction_id": None,
                "new_faction_id": "stormwatch_wardens",
            },
        )
    )

    try:
        assert list(world.event_log) == [
            "[Year 1001, Month 6, Day 4] "
            "Aethoria Capital changed controlling faction from none to Stormwatch Wardens."
        ]
    finally:
        set_locale(previous_locale)


def test_event_log_facade_projects_canonical_records_only() -> None:
    set_locale("en")

    class _World:
        MAX_EVENT_LOG = 2

        def __init__(self) -> None:
            self.event_records = []

    world = _World()
    world.event_records.extend([
        WorldEventRecord(kind="meeting", year=1041, month=1, day=1, description="Older"),
        WorldEventRecord(kind="battle", year=1042, month=3, day=3, description="Second"),
        WorldEventRecord(kind="battle", year=1042, month=3, day=4, description="Third"),
    ])

    assert list(log_facade.event_log_view(world)) == [
        "[Year 1042, Month 3, Day 3] Second",
        "[Year 1042, Month 3, Day 4] Third",
    ]
    assert log_facade.event_log_lines(world, last_n=1) == [
        "[Year 1042, Month 3, Day 4] Third",
    ]
    assert log_facade.event_log_lines(world, last_n=0) == []


def test_event_log_view_with_zero_max_event_log_returns_empty_view() -> None:
    set_locale("en")

    class _World:
        MAX_EVENT_LOG = 0

        def __init__(self) -> None:
            self.event_records = [
                WorldEventRecord(kind="meeting", year=1041, month=1, day=1, description="Hidden"),
            ]

    world = _World()

    assert list(log_facade.event_log_view(world)) == []
    assert log_facade.event_log_lines(world) == []


def test_event_log_has_no_display_assignment_path() -> None:
    world = World()

    try:
        world.event_log = ["legacy display line"]
    except AttributeError:
        pass
    else:
        raise AssertionError("event_log assignment should not be supported")

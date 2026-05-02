from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.i18n import get_locale, set_locale
from fantasy_simulator.world import World
from fantasy_simulator import world_event_log_facade
from fantasy_simulator.world_event_log import format_event_log_entry, project_compatibility_event_log


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


def test_format_event_log_entry_day_without_month_uses_year_only_compat() -> None:
    entry = format_event_log_entry("hello", translate=_translate, year=1000, day=3)
    assert entry == "[Y1000] hello"


def test_project_compatibility_event_log_uses_canonical_description() -> None:
    records = [
        WorldEventRecord(kind="battle", year=1000, description="new-format"),
    ]

    projected = project_compatibility_event_log(records, max_event_log=10, translate=_translate)
    assert projected == ["[Y1000 M1 D1] new-format"]


def test_project_compatibility_event_log_uses_formatting_when_no_legacy_entry() -> None:
    records = [
        WorldEventRecord(kind="battle", year=1001, month=6, day=4, description="battle"),
    ]

    projected = project_compatibility_event_log(records, max_event_log=10, translate=_translate)
    assert projected == ["[Y1001 M6 D4] battle"]


def test_project_compatibility_event_log_keeps_legacy_default_without_world_context() -> None:
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

    projected = project_compatibility_event_log(records, max_event_log=10, translate=_translate)

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


def test_project_compatibility_event_log_preserves_exact_legacy_event_log_entry() -> None:
    records = [
        WorldEventRecord(
            kind="legacy_event_log",
            year=1000,
            month=1,
            day=1,
            description="Year 1000: A legacy omen spread through the capital.",
            legacy_event_log_entry="Year 1000: A legacy omen spread through the capital.",
        ),
    ]

    projected = project_compatibility_event_log(records, max_event_log=10, translate=_translate)
    assert projected == ["Year 1000: A legacy omen spread through the capital."]


def test_legacy_event_log_entry_is_not_retranslated_after_locale_switch() -> None:
    previous_locale = get_locale()
    set_locale(previous_locale)
    world = World()
    world.record_event(
        WorldEventRecord(
            kind="legacy_event_log",
            year=1000,
            month=1,
            day=1,
            description="A legacy omen spread through the capital.",
            legacy_event_log_entry="Year 1000: A legacy omen spread through the capital.",
        )
    )

    set_locale("ja")
    try:
        assert list(world.event_log) == ["Year 1000: A legacy omen spread through the capital."]
    finally:
        set_locale(previous_locale)


def test_event_log_facade_preserves_world_wrapper_semantics() -> None:
    set_locale("en")

    class _World:
        MAX_EVENT_LOG = 2
        year = 1042

        def __init__(self) -> None:
            self._display_event_log = []
            self.event_records = []

    world = _World()

    world_event_log_facade.append_event_log_entry(world, "First")
    world_event_log_facade.append_event_log_entry(world, "Second", month=3)
    world_event_log_facade.append_event_log_entry(world, "Third", month=3, day=4)

    assert list(world_event_log_facade.event_log_view(world)) == [
        "[Year 1042, Month 3] Second",
        "[Year 1042, Month 3, Day 4] Third",
    ]
    assert world_event_log_facade.compatibility_event_log(world, last_n=1) == [
        "[Year 1042, Month 3, Day 4] Third",
    ]

    world_event_log_facade.set_event_log_entries(world, ["stale", "older", "newer"])
    assert list(world_event_log_facade.event_log_view(world)) == ["older", "newer"]

    world.event_records.append(
        WorldEventRecord(kind="battle", year=1043, month=1, day=2, description="Canonical")
    )
    assert list(world_event_log_facade.event_log_view(world)) == [
        "[Year 1043, Month 1, Day 2] Canonical",
    ]

    world_event_log_facade.rebuild_compatibility_event_log(world)
    assert world._display_event_log == []


def test_event_log_setter_rejects_stale_display_assignment_after_canonical_history() -> None:
    world = World()
    world.record_event(
        WorldEventRecord(
            record_id="r1",
            kind="battle",
            year=1001,
            description="Canonical clash",
        )
    )

    try:
        world.event_log = ["stale cache entry"]
    except RuntimeError as exc:
        assert "canonical event_records" in str(exc)
    else:
        raise AssertionError("event_log assignment should fail after canonical history exists")

    assert world.event_log == ["[Year 1001, Month 1, Day 1] Canonical clash"]

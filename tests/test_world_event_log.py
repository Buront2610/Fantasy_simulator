from __future__ import annotations

from fantasy_simulator.event_models import WorldEventRecord
from fantasy_simulator.world_event_log import format_event_log_entry, project_compatibility_event_log


def _translate(key: str, **kwargs: int) -> str:
    if key == "event_log_prefix":
        return f"[Y{kwargs['year']}]"
    if key == "event_log_prefix_month":
        return f"[Y{kwargs['year']} M{kwargs['month']}]"
    if key == "event_log_prefix_day":
        return f"[Y{kwargs['year']} M{kwargs['month']} D{kwargs['day']}]"
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


def test_project_compatibility_event_log_prefers_legacy_entry_when_present() -> None:
    records = [
        WorldEventRecord(kind="battle", year=1000, description="new-format", legacy_event_log_entry="legacy-format"),
    ]

    projected = project_compatibility_event_log(records, max_event_log=10, translate=_translate)
    assert projected == ["legacy-format"]


def test_project_compatibility_event_log_uses_formatting_when_no_legacy_entry() -> None:
    records = [
        WorldEventRecord(kind="battle", year=1001, month=6, day=4, description="battle"),
    ]

    projected = project_compatibility_event_log(records, max_event_log=10, translate=_translate)
    assert projected == ["[Y1001 M6 D4] battle"]

"""
tests/test_reports.py - Unit tests for the reports module.
"""

import pytest
from fantasy_simulator.character import Character
from fantasy_simulator.content.setting_bundle import CalendarDefinition, CalendarMonthDefinition
from fantasy_simulator.events import WorldEventRecord
from fantasy_simulator.i18n import get_locale, set_locale, tr
from fantasy_simulator.reports import (
    CharacterReportEntry,
    MonthlyReport,
    YearlyReport,
    format_monthly_report,
    format_yearly_report,
    generate_monthly_report,
    generate_yearly_report,
)
from fantasy_simulator.simulator import Simulator
from fantasy_simulator.world import World


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_locale():
    previous = get_locale()
    set_locale("en")
    yield
    set_locale(previous)


def _make_char(
    name: str,
    location_id: str = "loc_aethoria_capital",
    favorite: bool = False,
    spotlighted: bool = False,
    playable: bool = False,
) -> Character:
    return Character(
        name=name, age=25, gender="Male", race="Human", job="Warrior",
        strength=50, constitution=50, intelligence=50,
        dexterity=50, wisdom=40, charisma=40,
        skills={"Swordsmanship": 2},
        location_id=location_id,
        favorite=favorite,
        spotlighted=spotlighted,
        playable=playable,
    )


@pytest.fixture
def world() -> World:
    return World()


@pytest.fixture
def world_with_chars(world) -> World:
    """A world with a favorite, a spotlighted, and a regular character."""
    c1 = _make_char("Hero", favorite=True)
    c2 = _make_char("Sidekick", spotlighted=True)
    c3 = _make_char("NPC")
    for c in [c1, c2, c3]:
        world.add_character(c)
    return world


# ---------------------------------------------------------------------------
# WorldEventRecord time field tests — SI-9: month/day must be in range
# ---------------------------------------------------------------------------

class TestWorldEventRecordMonth:
    def test_month_defaults_to_one(self):
        rec = WorldEventRecord(kind="battle", year=1000)
        assert rec.month == 1

    def test_month_can_be_set(self):
        rec = WorldEventRecord(kind="battle", year=1000, month=5)
        assert rec.month == 5

    def test_month_clamped_to_min_one(self):
        rec = WorldEventRecord(kind="battle", year=1000, month=-3)
        assert rec.month == 1

    def test_month_zero_clamped_to_one(self):
        rec = WorldEventRecord(kind="battle", year=1000, month=0)
        assert rec.month == 1

    def test_month_preserves_large_values_for_non_gregorian_calendars(self):
        rec = WorldEventRecord(kind="battle", year=1000, month=99)
        assert rec.month == 99

    def test_month_in_to_dict(self):
        rec = WorldEventRecord(kind="journey", year=1001, month=7)
        d = rec.to_dict()
        assert d["month"] == 7

    def test_month_from_dict(self):
        d = {
            "record_id": "abc123",
            "kind": "journey",
            "year": 1001,
            "month": 7,
        }
        rec = WorldEventRecord.from_dict(d)
        assert rec.month == 7

    def test_month_defaults_in_from_dict_when_missing(self):
        """Old saves without month should get month=1 (clamped by __post_init__)."""
        d = {"record_id": "abc123", "kind": "meeting", "year": 1000}
        rec = WorldEventRecord.from_dict(d)
        assert rec.month == 1

    def test_from_event_result_month_defaults_to_one(self):
        from fantasy_simulator.events import EventResult
        er = EventResult(description="test", event_type="meeting", year=1000)
        rec = WorldEventRecord.from_event_result(er)
        assert rec.month == 1

    def test_day_defaults_to_one(self):
        rec = WorldEventRecord(kind="battle", year=1000)
        assert rec.day == 1

    def test_day_clamped_to_range(self):
        assert WorldEventRecord(kind="battle", year=1000, day=0).day == 1
        assert WorldEventRecord(kind="battle", year=1000, day=99).day == 99


# ---------------------------------------------------------------------------
# Monthly report generation tests
# ---------------------------------------------------------------------------

class TestGenerateMonthlyReport:
    def test_empty_report_when_no_events(self, world_with_chars):
        report = generate_monthly_report(world_with_chars, 1000, 3)
        assert isinstance(report, MonthlyReport)
        assert report.year == 1000
        assert report.month == 3
        assert report.total_events == 0

    def test_report_includes_watched_characters_with_events(self, world_with_chars):
        """Watched chars should appear only if they have events in the period."""
        hero = world_with_chars.characters[0]
        world_with_chars.record_event(WorldEventRecord(
            record_id="r1", kind="battle", year=1000, month=3,
            primary_actor_id=hero.char_id,
            description="Hero fought bravely", severity=3,
        ))
        report = generate_monthly_report(world_with_chars, 1000, 3)
        # Only Hero should appear (Sidekick has no events this month)
        assert len(report.character_entries) == 1
        hero_entry = report.character_entries[0]
        assert hero_entry.name == "Hero"
        assert "fought bravely" in hero_entry.events[0]

    def test_watched_char_without_events_excluded(self, world_with_chars):
        """Watched chars with no events in the period should not appear."""
        world_with_chars.record_event(WorldEventRecord(
            record_id="r_npc", kind="meeting", year=1000, month=3,
            description="Something happened", severity=1,
        ))
        report = generate_monthly_report(world_with_chars, 1000, 3)
        # No watched chars have events, so none should appear
        assert len(report.character_entries) == 0

    def test_report_excludes_unwatched_character_entries(self, world_with_chars):
        npc = world_with_chars.characters[2]  # "NPC" - no flags
        world_with_chars.record_event(WorldEventRecord(
            record_id="r2", kind="meeting", year=1000, month=3,
            primary_actor_id=npc.char_id,
            description="NPC did something", severity=1,
        ))
        report = generate_monthly_report(world_with_chars, 1000, 3)
        char_names = {e.name for e in report.character_entries}
        assert "NPC" not in char_names

    def test_notable_events_filtered_by_severity(self, world_with_chars):
        world_with_chars.record_event(WorldEventRecord(
            record_id="r3", kind="meeting", year=1000, month=5,
            description="Minor event", severity=1,
        ))
        world_with_chars.record_event(WorldEventRecord(
            record_id="r4", kind="battle", year=1000, month=5,
            description="Major battle", severity=3,
        ))
        report = generate_monthly_report(world_with_chars, 1000, 5)
        assert "Major battle" in report.notable_events
        assert "Minor event" not in report.notable_events

    def test_location_entries_populated(self, world_with_chars):
        world_with_chars.record_event(WorldEventRecord(
            record_id="r5", kind="discovery", year=1000, month=6,
            location_id="loc_aethoria_capital",
            description="Found treasure", severity=3,
        ))
        report = generate_monthly_report(world_with_chars, 1000, 6)
        assert len(report.location_entries) == 1
        assert report.location_entries[0].location_id == "loc_aethoria_capital"

    def test_filters_by_year_and_month(self, world_with_chars):
        world_with_chars.record_event(WorldEventRecord(
            record_id="r6", kind="battle", year=1000, month=3,
            description="March event", severity=3,
        ))
        world_with_chars.record_event(WorldEventRecord(
            record_id="r7", kind="battle", year=1000, month=4,
            description="April event", severity=3,
        ))
        report = generate_monthly_report(world_with_chars, 1000, 3)
        assert report.total_events == 1
        assert "March event" in report.notable_events

    def test_month_label_uses_historical_calendar_after_calendar_change(self, world_with_chars):
        old_calendar = CalendarDefinition(
            calendar_key="old_reckoning",
            display_name="Old Reckoning",
            months=[
                CalendarMonthDefinition("dawn", "Dawnturn", 30, season="winter"),
                CalendarMonthDefinition("wane", "Wanetide", 30, season="summer"),
            ],
        )
        new_calendar = CalendarDefinition(
            calendar_key="new_reckoning",
            display_name="New Reckoning",
            months=[
                CalendarMonthDefinition("glass", "Glassrise", 30, season="winter"),
                CalendarMonthDefinition("ember", "Emberwane", 30, season="spring"),
                CalendarMonthDefinition("storm", "Stormwake", 30, season="summer"),
            ],
        )
        world_with_chars.setting_bundle.world_definition.calendar = old_calendar
        world_with_chars.calendar_baseline = CalendarDefinition.from_dict(old_calendar.to_dict())
        world_with_chars.record_event(WorldEventRecord(
            record_id="hist_1",
            kind="meeting",
            year=1000,
            month=2,
            calendar_key="old_reckoning",
            description="Old calendar event",
            severity=2,
        ))
        world_with_chars.apply_calendar_definition(
            new_calendar,
            effective_year=1001,
            effective_month=1,
            effective_day=1,
        )

        report = generate_monthly_report(world_with_chars, 1000, 2)

        assert report.month_label == "Wanetide"
        assert report.season == "summer"


# ---------------------------------------------------------------------------
# Yearly report generation tests
# ---------------------------------------------------------------------------

class TestGenerateYearlyReport:
    def test_empty_report_when_no_events(self, world_with_chars):
        report = generate_yearly_report(world_with_chars, 1000)
        assert isinstance(report, YearlyReport)
        assert report.year == 1000
        assert report.total_events == 0
        assert report.deaths_this_year == 0

    def test_report_includes_notable_events(self, world_with_chars):
        world_with_chars.record_event(WorldEventRecord(
            record_id="y1", kind="death", year=1001, month=6,
            description="Tragic death", severity=5,
        ))
        report = generate_yearly_report(world_with_chars, 1001)
        assert "Tragic death" in report.notable_events

    def test_deaths_counted_from_events(self, world_with_chars):
        """deaths_this_year must come from event records, not world state."""
        world_with_chars.record_event(WorldEventRecord(
            record_id="d1", kind="death", year=1001, month=3,
            description="Death 1", severity=5,
        ))
        world_with_chars.record_event(WorldEventRecord(
            record_id="d2", kind="death", year=1001, month=9,
            description="Death 2", severity=5,
        ))
        report = generate_yearly_report(world_with_chars, 1001)
        assert report.deaths_this_year == 2

    def test_deaths_counted_from_all_fatal_event_kinds(self, world_with_chars):
        world_with_chars.record_event(WorldEventRecord(
            record_id="df1", kind="death", year=1001, month=2,
            description="Death 1", severity=5,
        ))
        world_with_chars.record_event(WorldEventRecord(
            record_id="df2", kind="adventure_death", year=1001, month=6,
            description="Adventure death", severity=5,
        ))
        world_with_chars.record_event(WorldEventRecord(
            record_id="df3", kind="battle_fatal", year=1001, month=9,
            description="Battle fatality", severity=5,
        ))

        report = generate_yearly_report(world_with_chars, 1001)

        assert report.deaths_this_year == 3

    def test_report_includes_watched_character_year_summaries(self, world_with_chars):
        hero = world_with_chars.characters[0]
        world_with_chars.record_event(WorldEventRecord(
            record_id="y2", kind="marriage", year=1001, month=6,
            primary_actor_id=hero.char_id,
            description="Hero got married", severity=4,
        ))
        report = generate_yearly_report(world_with_chars, 1001)
        assert len(report.character_entries) == 1
        hero_entry = report.character_entries[0]
        assert hero_entry.name == "Hero"
        assert "got married" in hero_entry.events[0]

    def test_watched_char_without_events_excluded_from_yearly(self, world_with_chars):
        """Watched chars with no events that year should not appear."""
        world_with_chars.record_event(WorldEventRecord(
            record_id="y_other", kind="meeting", year=1001, month=3,
            description="Something happened", severity=1,
        ))
        report = generate_yearly_report(world_with_chars, 1001)
        # No watched chars have events, so none should appear
        assert len(report.character_entries) == 0

    def test_filters_by_year(self, world_with_chars):
        world_with_chars.record_event(WorldEventRecord(
            record_id="y3", kind="battle", year=1001, month=3,
            description="Battle of 1001", severity=4,
        ))
        world_with_chars.record_event(WorldEventRecord(
            record_id="y4", kind="battle", year=1002, month=3,
            description="Battle of 1002", severity=4,
        ))
        report = generate_yearly_report(world_with_chars, 1001)
        assert report.total_events == 1

    def test_location_entries_only_notable(self, world_with_chars):
        world_with_chars.record_event(WorldEventRecord(
            record_id="y5", kind="meeting", year=1001, month=6,
            location_id="loc_aethoria_capital",
            description="Quiet meeting", severity=1,
        ))
        report = generate_yearly_report(world_with_chars, 1001)
        # Location has only minor events, should not appear
        assert len(report.location_entries) == 0

    def test_report_does_not_use_current_world_state(self, world_with_chars):
        """Year 1000 report read from year 1003 must not reflect year-1003 state."""
        hero = world_with_chars.characters[0]
        world_with_chars.record_event(WorldEventRecord(
            record_id="hev", kind="battle", year=1000, month=5,
            primary_actor_id=hero.char_id,
            description="Hero battled in year 1000", severity=3,
        ))
        # Advance time to year 1003
        for _ in range(3):
            world_with_chars.advance_time(1)
        assert world_with_chars.year == 1003

        report_at_1003 = generate_yearly_report(world_with_chars, 1000)
        # The report should still contain year-1000 events
        assert report_at_1003.total_events == 1
        assert report_at_1003.character_entries[0].name == "Hero"
        # deaths_this_year comes from events, not current state; no death events in year 1000
        assert report_at_1003.deaths_this_year == 0


# ---------------------------------------------------------------------------
# Report formatting tests
# ---------------------------------------------------------------------------

class TestFormatMonthlyReport:
    def test_format_contains_title(self):
        report = MonthlyReport(year=1003, month=2, month_label="Frostwane", season="winter", total_events=0)
        text = format_monthly_report(report)
        assert "1003" in text
        assert "Frostwane" in text

    def test_format_contains_character_entries(self):
        entry = CharacterReportEntry(
            char_id="c1", name="Hero",
            events=["Found an item"],
        )
        report = MonthlyReport(
            year=1003, month=3, character_entries=[entry], total_events=1,
        )
        text = format_monthly_report(report)
        assert "Hero" in text
        assert "Found an item" in text

    def test_format_contains_notable_events(self):
        report = MonthlyReport(
            year=1003, month=5,
            notable_events=["A dragon appeared"],
            total_events=1,
        )
        text = format_monthly_report(report)
        assert "dragon" in text

    def test_season_shown_in_format(self):
        report = MonthlyReport(year=1003, month=1, month_label="Embermorn", season="winter", total_events=0)
        text = format_monthly_report(report)
        assert "Winter" in text

    def test_summer_month(self):
        report = MonthlyReport(year=1003, month=7, month_label="Goldleaf", season="summer", total_events=0)
        text = format_monthly_report(report)
        assert "Summer" in text

    def test_empty_world_section_not_shown(self):
        """If all location entries have no notable events, no World section header."""
        from fantasy_simulator.reports import LocationReportEntry
        loc = LocationReportEntry(
            location_id="loc_test", name="Test", event_count=1,
            notable_events=[],
        )
        report = MonthlyReport(
            year=1003, month=3, location_entries=[loc], total_events=1,
        )
        text = format_monthly_report(report)
        assert "World News" not in text


class TestFormatYearlyReport:
    def test_format_contains_title(self):
        report = YearlyReport(year=1003, total_events=0, deaths_this_year=0)
        text = format_yearly_report(report)
        assert "1003" in text

    def test_format_contains_notable_events(self):
        report = YearlyReport(
            year=1003,
            notable_events=["The king was slain"],
            total_events=1,
            deaths_this_year=1,
        )
        text = format_yearly_report(report)
        assert "king was slain" in text

    def test_format_shows_deaths_from_events(self):
        report = YearlyReport(
            year=1003, total_events=5, deaths_this_year=2,
        )
        text = format_yearly_report(report)
        assert "2" in text


# ---------------------------------------------------------------------------
# Simulator integration tests
# ---------------------------------------------------------------------------

class TestSimulatorReportIntegration:
    def test_all_simulator_events_have_valid_month(self):
        """Every event recorded by the simulator must have month in 1..12."""
        world = World()
        c1 = _make_char("Alice")
        c2 = _make_char("Bob", location_id="loc_silverbrook")
        for c in [c1, c2]:
            world.add_character(c)
        sim = Simulator(world, events_per_year=8, seed=42)
        sim.advance_years(3)
        for rec in world.event_records:
            assert 1 <= rec.month <= 12, (
                f"Record {rec.record_id} (kind={rec.kind}) has month={rec.month}"
            )

    def test_current_month_never_zero(self):
        """current_month must always be in 1..12, even between years."""
        world = World()
        c = _make_char("Hero")
        world.add_character(c)
        sim = Simulator(world, events_per_year=4, seed=42)
        assert sim.current_month >= 1
        sim.advance_years(1)
        assert 1 <= sim.current_month <= 12
        assert 1 <= sim.current_day <= 30

    def test_get_monthly_report_returns_string(self):
        world = World()
        c = _make_char("Hero", favorite=True)
        world.add_character(c)
        sim = Simulator(world, events_per_year=4, seed=42)
        sim.advance_years(1)
        text = sim.get_monthly_report(1000, 1)
        assert isinstance(text, str)
        assert "1000" in text

    def test_get_yearly_report_returns_string(self):
        world = World()
        c = _make_char("Hero", favorite=True)
        world.add_character(c)
        sim = Simulator(world, events_per_year=4, seed=42)
        sim.advance_years(1)
        text = sim.get_yearly_report(1000)
        assert isinstance(text, str)
        assert "1000" in text

    def test_get_latest_yearly_report(self):
        world = World()
        c = _make_char("Hero", favorite=True)
        world.add_character(c)
        sim = Simulator(world, events_per_year=4, seed=42)
        sim.advance_years(2)
        text = sim.get_latest_yearly_report()
        assert isinstance(text, str)
        # Should be for the most recently completed year
        assert "1001" in text

    def test_get_latest_completed_report_year_without_records(self):
        world = World(year=950)
        sim = Simulator(world, events_per_year=0, seed=42)
        assert sim.get_latest_completed_report_year() == 950

    def test_get_latest_completed_report_year_without_records_after_advance(self):
        world = World(year=950)
        sim = Simulator(world, events_per_year=0, seed=42)
        sim.advance_years(2)
        assert sim.world.year == 952
        assert sim.get_latest_completed_report_year() == 951

    def test_get_latest_completed_report_year_uses_earliest_record_year(self):
        world = World(year=1001)
        world.record_event(WorldEventRecord(
            record_id="r1",
            kind="meeting",
            year=1000,
            month=4,
            description="Meeting",
            severity=1,
        ))
        sim = Simulator(world, events_per_year=0, seed=42)
        assert sim.get_latest_completed_report_year() == 1000

    def test_get_summary_uses_world_event_records(self):
        """get_summary() should use WorldEventRecord, not history."""
        world = World()
        c1 = _make_char("Alice")
        c2 = _make_char("Bob")
        for c in [c1, c2]:
            world.add_character(c)
        sim = Simulator(world, events_per_year=4, seed=42)
        sim.advance_years(1)
        summary = sim.get_summary()
        assert "Total events" in summary or "記録イベント数" in summary

    def test_get_summary_event_type_fallback(self):
        """Unknown event kinds should not raise; they get a fallback label."""
        world = World()
        world.record_event(WorldEventRecord(
            record_id="x1", kind="some_unknown_kind", year=1000, month=3,
            description="Mystery", severity=1,
        ))
        sim = Simulator(world, events_per_year=0, seed=42)
        summary = sim.get_summary()
        # Should contain a readable fallback, not crash
        assert "Some unknown kind" in summary or "some_unknown_kind" in summary

    def test_get_summary_includes_adventure_death_in_notable_moments(self):
        world = World()
        world.record_event(WorldEventRecord(
            record_id="fatal_summary_1",
            kind="adventure_death",
            year=1000,
            month=3,
            description="A hero fell on an adventure",
            severity=5,
        ))
        sim = Simulator(world, events_per_year=0, seed=42)

        summary = sim.get_summary()

        assert "A hero fell on an adventure" in summary

    def test_current_month_serialization_round_trip(self):
        world = World()
        c = _make_char("Hero")
        world.add_character(c)
        sim = Simulator(world, events_per_year=4, seed=42)
        sim.current_month = 7
        sim.current_day = 13
        data = sim.to_dict()
        assert data["current_month"] == 7
        assert data["current_day"] == 13
        sim2 = Simulator.from_dict(data)
        assert sim2.current_month == 7
        assert sim2.current_day == 13

    def test_start_year_serialization_round_trip(self):
        world = World(year=1234)
        c = _make_char("Hero")
        world.add_character(c)
        sim = Simulator(world, events_per_year=0, seed=42)
        sim.advance_years(1)
        data = sim.to_dict()
        sim2 = Simulator.from_dict(data)
        assert sim2.start_year == 1234
        assert sim2.get_latest_completed_report_year() == 1234

    def test_current_month_from_dict_clamped(self):
        """Loading a save with invalid month/day should clamp into range."""
        world = World()
        c = _make_char("Hero")
        world.add_character(c)
        sim = Simulator(world, events_per_year=4, seed=42)
        data = sim.to_dict()
        data["current_month"] = 0
        data["current_day"] = 0
        sim2 = Simulator.from_dict(data)
        assert sim2.current_month == 1
        assert sim2.current_day == 1

    def test_start_year_from_dict_defaults_to_world_year(self):
        world = World(year=1005)
        c = _make_char("Hero")
        world.add_character(c)
        sim = Simulator(world, events_per_year=0, seed=42)
        data = sim.to_dict()
        data.pop("start_year", None)
        sim2 = Simulator.from_dict(data)
        assert sim2.start_year == 1005

    def test_resolve_adventure_choice_has_valid_month(self):
        """Events from resolve_adventure_choice must have valid month/day."""
        world = World()
        c = _make_char("Hero")
        world.add_character(c)
        sim = Simulator(world, events_per_year=8, seed=42)
        # Run to generate some adventures
        sim.advance_years(5)
        # Check all adventure_choice records
        for rec in world.event_records:
            if rec.kind == "adventure_choice":
                assert 1 <= rec.month <= 12, (
                    f"adventure_choice record has month={rec.month}"
                )
                assert 1 <= rec.day <= 30, (
                    f"adventure_choice record has day={rec.day}"
                )


# ---------------------------------------------------------------------------
# i18n tests for report keys
# ---------------------------------------------------------------------------

_ADVENTURE_EVENT_KINDS = [
    "injury_recovery", "adventure_started", "adventure_arrived",
    "adventure_choice", "adventure_death", "adventure_injured",
    "adventure_discovery", "adventure_returned_injured",
    "adventure_returned", "adventure_retreated", "adventure_update",
]

_ALL_RECORDED_EVENT_KINDS = [
    # EventSystem.generate_random_event()
    "anniversary",
    "romance",
    "marriage",
    "battle_fatal",
    "battle",
    "discovery",
    "meeting",
    "aging",
    "death",
    "skill_training",
    "journey",
    # Simulator structured/adventure events
    "injury_recovery",
    "adventure_started",
    "adventure_arrived",
    "adventure_choice",
    "adventure_death",
    "adventure_injured",
    "adventure_discovery",
    "adventure_returned_injured",
    "adventure_returned",
    "adventure_retreated",
    "adventure_update",
]


class TestReportI18n:
    def test_report_keys_exist_en(self):
        set_locale("en")
        assert tr("report_monthly_title", year=1000, month=1, season="Winter") != "report_monthly_title"
        assert tr("report_yearly_title", year=1000) != "report_yearly_title"
        assert tr("report_section_watched") != "report_section_watched"
        assert tr("report_section_notable") != "report_section_notable"
        assert tr("report_section_world") != "report_section_world"
        assert tr("report_section_watched_year") != "report_section_watched_year"
        assert tr("report_deaths_this_year", count=0) != "report_deaths_this_year"
        assert tr("season_winter") != "season_winter"

    def test_report_keys_exist_ja(self):
        set_locale("ja")
        assert tr("report_monthly_title", year=1000, month=1, season="冬") != "report_monthly_title"
        assert tr("report_yearly_title", year=1000) != "report_yearly_title"
        assert tr("report_section_watched") != "report_section_watched"
        assert tr("report_section_watched_year") != "report_section_watched_year"
        assert tr("report_deaths_this_year", count=1) != "report_deaths_this_year"
        assert tr("season_winter") == "冬"
        set_locale("en")

    def test_adventure_event_type_keys_en(self):
        """All adventure/injury event kinds must have i18n keys."""
        set_locale("en")
        for kind in _ADVENTURE_EVENT_KINDS:
            key = f"event_type_{kind}"
            assert tr(key) != key, f"Missing i18n key: {key}"

    def test_adventure_event_type_keys_ja(self):
        set_locale("ja")
        for kind in _ADVENTURE_EVENT_KINDS:
            key = f"event_type_{kind}"
            assert tr(key) != key, f"Missing ja i18n key: {key}"
        set_locale("en")

    def test_all_record_event_type_keys_en(self):
        """All event kinds recorded in WorldEventRecord should have en i18n keys."""
        set_locale("en")
        for kind in _ALL_RECORDED_EVENT_KINDS:
            key = f"event_type_{kind}"
            assert tr(key) != key, f"Missing en i18n key: {key}"

    def test_all_record_event_type_keys_ja(self):
        """All event kinds recorded in WorldEventRecord should have ja i18n keys."""
        set_locale("ja")
        for kind in _ALL_RECORDED_EVENT_KINDS:
            key = f"event_type_{kind}"
            assert tr(key) != key, f"Missing ja i18n key: {key}"
        set_locale("en")

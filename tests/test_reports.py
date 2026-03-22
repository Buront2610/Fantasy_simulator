"""
tests/test_reports.py - Unit tests for the reports module.
"""

import pytest
from character import Character
from events import WorldEventRecord
from i18n import get_locale, set_locale, tr
from reports import (
    MonthlyReport,
    YearlyReport,
    format_monthly_report,
    format_yearly_report,
    generate_monthly_report,
    generate_yearly_report,
)
from simulator import Simulator
from world import World


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
# WorldEventRecord month field tests
# ---------------------------------------------------------------------------

class TestWorldEventRecordMonth:
    def test_month_defaults_to_zero(self):
        rec = WorldEventRecord(kind="battle", year=1000)
        assert rec.month == 0

    def test_month_can_be_set(self):
        rec = WorldEventRecord(kind="battle", year=1000, month=5)
        assert rec.month == 5

    def test_month_clamped_non_negative(self):
        rec = WorldEventRecord(kind="battle", year=1000, month=-3)
        assert rec.month == 0

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
        d = {"record_id": "abc123", "kind": "meeting", "year": 1000}
        rec = WorldEventRecord.from_dict(d)
        assert rec.month == 0


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

    def test_report_includes_watched_characters(self, world_with_chars):
        world_with_chars.record_event(WorldEventRecord(
            record_id="r1", kind="battle", year=1000, month=3,
            primary_actor_id=world_with_chars.characters[0].char_id,
            description="Hero fought bravely", severity=3,
        ))
        report = generate_monthly_report(world_with_chars, 1000, 3)
        assert len(report.character_entries) == 2  # favorite + spotlighted
        hero_entry = next(e for e in report.character_entries if e.name == "Hero")
        assert len(hero_entry.events) == 1
        assert "fought bravely" in hero_entry.events[0]

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


# ---------------------------------------------------------------------------
# Yearly report generation tests
# ---------------------------------------------------------------------------

class TestGenerateYearlyReport:
    def test_empty_report_when_no_events(self, world_with_chars):
        report = generate_yearly_report(world_with_chars, 1000)
        assert isinstance(report, YearlyReport)
        assert report.year == 1000
        assert report.total_events == 0
        assert report.alive_count == 3
        assert report.dead_count == 0

    def test_report_includes_notable_events(self, world_with_chars):
        world_with_chars.record_event(WorldEventRecord(
            record_id="y1", kind="death", year=1001,
            description="Tragic death", severity=5,
        ))
        report = generate_yearly_report(world_with_chars, 1001)
        assert "Tragic death" in report.notable_events

    def test_report_includes_watched_character_year_summaries(self, world_with_chars):
        hero = world_with_chars.characters[0]
        world_with_chars.record_event(WorldEventRecord(
            record_id="y2", kind="marriage", year=1001, month=6,
            primary_actor_id=hero.char_id,
            description="Hero got married", severity=4,
        ))
        report = generate_yearly_report(world_with_chars, 1001)
        hero_entry = next(e for e in report.character_entries if e.name == "Hero")
        assert "got married" in hero_entry.events[0]

    def test_filters_by_year(self, world_with_chars):
        world_with_chars.record_event(WorldEventRecord(
            record_id="y3", kind="battle", year=1001,
            description="Battle of 1001", severity=4,
        ))
        world_with_chars.record_event(WorldEventRecord(
            record_id="y4", kind="battle", year=1002,
            description="Battle of 1002", severity=4,
        ))
        report = generate_yearly_report(world_with_chars, 1001)
        assert report.total_events == 1

    def test_location_entries_only_notable(self, world_with_chars):
        world_with_chars.record_event(WorldEventRecord(
            record_id="y5", kind="meeting", year=1001,
            location_id="loc_aethoria_capital",
            description="Quiet meeting", severity=1,
        ))
        report = generate_yearly_report(world_with_chars, 1001)
        # Location has only minor events, should not appear
        assert len(report.location_entries) == 0


# ---------------------------------------------------------------------------
# Report formatting tests
# ---------------------------------------------------------------------------

class TestFormatMonthlyReport:
    def test_format_contains_title(self):
        report = MonthlyReport(year=1003, month=2, total_events=0)
        text = format_monthly_report(report)
        assert "1003" in text
        assert "2" in text

    def test_format_contains_character_entries(self):
        from reports import CharacterReportEntry
        entry = CharacterReportEntry(
            char_id="c1", name="Hero", status="alive",
            location_name="Aethoria Capital",
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
        report = MonthlyReport(year=1003, month=1, total_events=0)
        text = format_monthly_report(report)
        assert "Winter" in text

    def test_summer_month(self):
        report = MonthlyReport(year=1003, month=7, total_events=0)
        text = format_monthly_report(report)
        assert "Summer" in text


class TestFormatYearlyReport:
    def test_format_contains_title(self):
        report = YearlyReport(year=1003, total_events=0, alive_count=5, dead_count=2)
        text = format_yearly_report(report)
        assert "1003" in text
        assert "5" in text

    def test_format_contains_notable_events(self):
        report = YearlyReport(
            year=1003,
            notable_events=["The king was slain"],
            total_events=1,
            alive_count=10, dead_count=1,
        )
        text = format_yearly_report(report)
        assert "king was slain" in text


# ---------------------------------------------------------------------------
# Simulator integration tests
# ---------------------------------------------------------------------------

class TestSimulatorReportIntegration:
    def test_simulator_events_have_month(self):
        """Events recorded by the simulator should have month > 0."""
        world = World()
        c1 = _make_char("Alice")
        c2 = _make_char("Bob", location_id="loc_silverbrook")
        for c in [c1, c2]:
            world.add_character(c)
        sim = Simulator(world, events_per_year=8, seed=42)
        sim.advance_years(1)
        records_with_month = [r for r in world.event_records if r.month > 0]
        assert len(records_with_month) > 0

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

    def test_current_month_serialization_round_trip(self):
        world = World()
        c = _make_char("Hero")
        world.add_character(c)
        sim = Simulator(world, events_per_year=4, seed=42)
        sim.current_month = 7
        data = sim.to_dict()
        assert data["current_month"] == 7
        sim2 = Simulator.from_dict(data)
        assert sim2.current_month == 7


# ---------------------------------------------------------------------------
# i18n tests for report keys
# ---------------------------------------------------------------------------

class TestReportI18n:
    def test_monthly_report_keys_exist_en(self):
        set_locale("en")
        assert tr("report_monthly_title", year=1000, month=1, season="Winter") != "report_monthly_title"
        assert tr("report_yearly_title", year=1000) != "report_yearly_title"
        assert tr("report_section_characters") != "report_section_characters"
        assert tr("report_section_notable") != "report_section_notable"
        assert tr("report_section_world") != "report_section_world"
        assert tr("season_winter") != "season_winter"

    def test_monthly_report_keys_exist_ja(self):
        set_locale("ja")
        assert tr("report_monthly_title", year=1000, month=1, season="冬") != "report_monthly_title"
        assert tr("report_yearly_title", year=1000) != "report_yearly_title"
        assert tr("report_section_characters") != "report_section_characters"
        assert tr("season_winter") == "冬"
        set_locale("en")

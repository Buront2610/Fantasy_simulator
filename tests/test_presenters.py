"""Presenter/view-model regression tests."""

from fantasy_simulator.i18n import set_locale
from fantasy_simulator.ui.presenters import ReportPresenter
from fantasy_simulator.ui.view_models import build_monthly_report_card_view, build_notification_views
from fantasy_simulator.rumor import Rumor
from fantasy_simulator.world import CalendarChangeRecord, World
from fantasy_simulator.events import WorldEventRecord
from fantasy_simulator.content.setting_bundle import CalendarDefinition, CalendarMonthDefinition


def test_monthly_report_card_is_built_from_event_records():
    set_locale("en")
    world = World()
    c = world.characters[0] if world.characters else None
    if c is None:
        from fantasy_simulator.character import Character
        c = Character("Aldric", 20, "Male", "Human", "Warrior", location_id="loc_aethoria_capital")
        world.add_character(c)
    world.event_records.append(
        WorldEventRecord(
            year=world.year,
            month=3,
            kind="adventure_returned",
            description="Aldric returned.",
            primary_actor_id=c.char_id,
            location_id="loc_aethoria_capital",
        )
    )
    card = build_monthly_report_card_view(world, world.year, 3)
    lines = ReportPresenter.render_monthly_card(card)
    assert any("Monthly highlights" in line for line in lines)
    assert any("Recent adventures" in line for line in lines)


def test_monthly_report_card_excludes_pending_adventure_choices_from_completed_adventures():
    set_locale("en")
    world = World()
    c = world.characters[0] if world.characters else None
    if c is None:
        from fantasy_simulator.character import Character
        c = Character("Aldric", 20, "Male", "Human", "Warrior", location_id="loc_aethoria_capital")
        world.add_character(c)
    world.event_records.append(
        WorldEventRecord(
            year=world.year,
            month=3,
            kind="adventure_choice",
            description="Aldric must decide whether to press on.",
            primary_actor_id=c.char_id,
            location_id="loc_aethoria_capital",
        )
    )

    card = build_monthly_report_card_view(world, world.year, 3)

    assert card.completed_adventures == []


def test_notification_views_render_canonical_summary_records_with_world_context():
    set_locale("en")
    world = World()
    record = WorldEventRecord(
        year=world.year,
        month=3,
        kind="location_faction_changed",
        description="Aethoria Capital changed controlling faction from none to stormwatch_wardens.",
        summary_key="events.location_faction_changed.summary",
        render_params={
            "location": "Aethoria Capital",
            "old_faction_id": None,
            "new_faction_id": "stormwatch_wardens",
        },
    )

    views = build_notification_views([record], world=world)

    assert views[0].text == "Aethoria Capital changed controlling faction from none to Stormwatch Wardens."


def test_monthly_report_card_renders_completed_adventure_summary_records():
    set_locale("en")
    world = World()
    world.record_event(
        WorldEventRecord(
            year=world.year,
            month=3,
            kind="adventure_returned",
            description="Legacy adventure text.",
            location_id="loc_aethoria_capital",
            summary_key="events.battle.summary",
            render_params={"actor": "Aldric"},
        )
    )

    card = build_monthly_report_card_view(world, world.year, 3)

    assert card.completed_adventures == ["Aldric fought at Aethoria Capital."]


def test_monthly_report_card_uses_historical_calendar_label_after_calendar_change():
    set_locale("en")
    world = World()
    world.record_event(
        WorldEventRecord(
            record_id="rec_hist",
            year=world.year,
            month=3,
            day=1,
            kind="meeting",
            description="Archive note.",
            calendar_key="old_calendar",
        )
    )
    world.calendar_history.append(
        CalendarChangeRecord(
            year=world.year,
            month=1,
            day=1,
            calendar=CalendarDefinition(
                calendar_key="old_calendar",
                display_name="Old Calendar",
                months=[
                    CalendarMonthDefinition("m1", "Firstwane", 30),
                    CalendarMonthDefinition("m2", "Secondwane", 30),
                    CalendarMonthDefinition("m3", "Wanetide", 30),
                ],
            ),
        )
    )
    world.calendar_baseline = CalendarDefinition(
        calendar_key="new_calendar",
        display_name="New Calendar",
        months=[
            CalendarMonthDefinition("m1", "Prime", 30),
            CalendarMonthDefinition("m2", "Duet", 30),
            CalendarMonthDefinition("m3", "Trine", 30),
        ],
    )

    card = build_monthly_report_card_view(world, world.year, 3)

    assert card.month_label == "Wanetide"


def test_monthly_report_card_surfaces_hot_rumors():
    set_locale("en")
    world = World()
    world.rumors.append(
        Rumor(
            id="rumor_1",
            description="Something happened at the capital.",
            reliability="plausible",
            source_location_id="loc_aethoria_capital",
            year_created=world.year,
            month_created=3,
        )
    )

    card = build_monthly_report_card_view(world, world.year, 3)
    lines = ReportPresenter.render_monthly_card(card)

    assert any("Rumors" in line for line in lines)
    assert any("Something happened at the capital." in line for line in lines)

"""Presenter/view-model regression tests."""

from fantasy_simulator.i18n import set_locale
from fantasy_simulator.ui.presenters import ReportPresenter
from fantasy_simulator.ui.view_models import build_monthly_report_card_view
from fantasy_simulator.world import World
from fantasy_simulator.events import WorldEventRecord


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
            kind="adventure_resolved",
            description="Aldric returned.",
            primary_actor_id=c.char_id,
            location_id="loc_aethoria_capital",
        )
    )
    card = build_monthly_report_card_view(world, world.year, 3)
    lines = ReportPresenter.render_monthly_card(card)
    assert any("Monthly highlights" in line for line in lines)
    assert any("Recent adventures" in line for line in lines)

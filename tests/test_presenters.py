"""Presenter/view-model regression tests."""

from fantasy_simulator.i18n import set_locale
from fantasy_simulator.ui.screen_dashboard import _render_world_dashboard
from fantasy_simulator.ui.ui_context import UIContext
from fantasy_simulator.ui.presenters import LanguagePresenter, ReportPresenter
from fantasy_simulator.ui.view_models import (
    build_monthly_report_card_view,
    build_notification_views,
    build_world_dashboard_view,
    build_yearly_report_card_view,
)
from fantasy_simulator.character import Character
from fantasy_simulator.rumor import Rumor
from fantasy_simulator.world import CalendarChangeRecord, World
from fantasy_simulator.events import WorldEventRecord
from fantasy_simulator.content.setting_bundle import CalendarDefinition, CalendarMonthDefinition


class CaptureOutput:
    def __init__(self):
        self.lines = []

    def print_line(self, text=""):
        self.lines.append(text)

    def print_heading(self, text):
        self.lines.append(text)

    def print_separator(self, char="=", width=62):
        self.lines.append(char * width)

    def print_error(self, text):
        self.lines.append(text)

    def print_success(self, text):
        self.lines.append(text)

    def print_warning(self, text):
        self.lines.append(text)

    def print_wrapped(self, text, indent=4):
        self.lines.append(" " * indent + text)

    def print_dim(self, text):
        self.lines.append(text)

    def print_highlighted(self, text):
        self.lines.append(text)

    def print_menu(self, prompt, key_label_pairs, default=None):
        self.lines.append(prompt)

    def format_status(self, text, positive):
        return text

    def print_panel(self, title, text):
        self.lines.append(title)
        self.lines.append(text)

    def get_terminal_width(self):
        return 80


class NoopInput:
    def read_line(self, prompt):
        return ""

    def read_menu_key(self, key_label_pairs, default=None):
        return default or ""

    def pause(self, message=""):
        return None


def test_language_presenter_surfaces_runtime_lore_details_concisely():
    set_locale("en")
    status = {
        "language_key": "child",
        "display_name": "Child Speech",
        "lineage": ["Proto", "Child Speech"],
        "sample_forms": {
            "given_names": ["Darin", "Sela"],
            "surnames": ["Torhand"],
            "lexicon": ["dara", "shel", "mor"],
            "toponym": "Dareth",
        },
        "runtime_state": {
            "derived_name_stems": ["dar", "mor", "sel", "extra"],
            "derived_toponym_suffixes": ["eth", "ath"],
        },
        "sound_shifts": {"a": "e", "t": "d", "s": "sh", "k": "g", "p": "b"},
        "recent_evolution_records": [
            {
                "year": 1200,
                "source_token": "s",
                "target_token": "sh",
                "rule_position": "initial",
            },
            {
                "year": 1210,
                "added_name_stem": "mor",
                "rule_position": "any",
            },
            {
                "year": 1220,
                "added_toponym_suffix": "ath",
                "rule_position": "final",
            },
        ],
        "evolution_count": 3,
    }

    lines = LanguagePresenter.render_status(status)

    assert "    Given names: Darin, Sela (+dar, mor, sel)" in lines
    assert "    Lexicon: dara, shel, mor" in lines
    assert "    Toponym: Dareth (+eth, ath)" in lines
    assert "    Evolution events: 3 (a>e, t>d, s>sh, k>g)" in lines
    assert "      1220: +ath (final)" in lines
    assert "      1210: +mor" in lines
    assert "      1200: s>sh (initial)" in lines


def test_language_presenter_keeps_legacy_minimal_status_output():
    set_locale("en")
    status = {
        "language_key": "plain",
        "display_name": "Plain",
        "lineage": ["Plain"],
        "sample_forms": {
            "given_names": ["Ala"],
            "surnames": [],
            "lexicon": [],
            "toponym": "Alaton",
        },
        "evolution_count": 0,
    }

    lines = LanguagePresenter.render_status(status)

    assert lines == [
        "  Plain",
        "    Lineage: Plain",
        "    Given names: Ala",
        "    Toponym: Alaton",
        "    Evolution events: 0",
    ]


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


def test_monthly_report_card_highlights_both_route_event_endpoints():
    set_locale("en")
    world = World()
    route = world.routes[0]
    world.apply_route_blocked_change(route.route_id, True, month=3)

    card = build_monthly_report_card_view(world, world.year, 3)

    assert world.location_name(route.from_site_id) in card.highlighted_locations
    assert world.location_name(route.to_site_id) in card.highlighted_locations


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


def test_monthly_report_card_clusters_rumor_threads_by_source_event():
    set_locale("en")
    world = World()
    world.record_event(
        WorldEventRecord(
            record_id="evt_road",
            kind="route_blocked",
            year=world.year,
            month=3,
            day=1,
            location_id="loc_aethoria_capital",
            description="The capital road failed.",
        )
    )
    world.rumors.extend([
        Rumor(
            id="rumor_low",
            description="Travelers say the road is unsafe.",
            reliability="doubtful",
            spread_level=4,
            source_location_id="loc_aethoria_capital",
            source_event_id="evt_road",
            year_created=world.year,
            month_created=3,
        ),
        Rumor(
            id="rumor_hot",
            description="Merchants insist the capital road collapsed.",
            reliability="plausible",
            spread_level=8,
            source_location_id="loc_aethoria_capital",
            source_event_id="evt_road",
            year_created=world.year,
            month_created=3,
        ),
    ])

    card = build_monthly_report_card_view(world, world.year, 3)
    lines = ReportPresenter.render_monthly_card(card)

    assert [(thread.source_event_id, thread.rumor_count) for thread in card.rumor_threads] == [("evt_road", 2)]
    assert card.rumor_threads[0].source_event_text == "The capital road failed."
    assert card.rumor_threads[0].headline == "Merchants insist the capital road collapsed."
    assert card.rumor_threads[0].source_location_name == "Aethoria Capital"
    assert any("Rumor threads" in line for line in lines)
    assert any("evt_road: 2 rumor(s)" in line and "plausible" in line for line in lines)


def test_monthly_report_card_surfaces_world_change_projection_summary():
    set_locale("en")
    world = World()
    route = world.routes[0]
    world.apply_route_blocked_change(route.route_id, True, month=3)
    world.record_event(
        WorldEventRecord(
            record_id="rec_occupation",
            kind="location_faction_changed",
            year=world.year,
            month=3,
            location_id="loc_aethoria_capital",
            description="Aethoria Capital changed hands.",
        )
    )

    card = build_monthly_report_card_view(world, world.year, 3)
    lines = ReportPresenter.render_monthly_card(card)

    assert [(item.category, item.count) for item in card.world_changes] == [
        ("occupation", 1),
        ("route", 1),
    ]
    assert [(item.record_id, item.category) for item in card.world_change_entries] == [
        (world.event_records[0].record_id, "route"),
        ("rec_occupation", "occupation"),
    ]
    assert any("World News" in line and "Occupation: 1" in line and "Route: 1" in line for line in lines)
    assert any("Occupation: Aethoria Capital changed hands." in line for line in lines)


def test_monthly_report_card_clusters_world_change_threads_by_category():
    set_locale("en")
    world = World()
    route = world.routes[0]
    blocked = world.apply_route_blocked_change(route.route_id, True, year=world.year, month=3, day=1)
    reopened = world.apply_route_blocked_change(route.route_id, False, year=world.year, month=3, day=2)
    terrain = world.apply_terrain_cell_change(
        2,
        2,
        biome="forest",
        year=world.year,
        month=3,
        day=3,
        location_id="loc_aethoria_capital",
    )

    card = build_monthly_report_card_view(world, world.year, 3)
    lines = ReportPresenter.render_monthly_card(card)

    assert blocked is not None
    assert reopened is not None
    assert terrain is not None
    assert [(thread.category, thread.count) for thread in card.world_change_threads] == [
        ("route", 2),
        ("terrain", 1),
    ]
    assert card.world_change_threads[0].headline.endswith("reopened.")
    assert world.location_name(route.from_site_id) in card.world_change_threads[0].location_names
    assert any("World-change threads" in line for line in lines)
    assert any("Route: 2 change(s)" in line and "reopened." in line for line in lines)
    assert any("Terrain: 1 change(s)" in line and "Aethoria Capital" in line for line in lines)


def test_monthly_report_card_surfaces_edited_headlines_before_raw_sections():
    set_locale("en")
    world = World()
    world.record_event(
        WorldEventRecord(
            record_id="minor",
            kind="meeting",
            year=world.year,
            month=3,
            day=1,
            severity=1,
            description="A quiet council met.",
        )
    )
    route = world.routes[0]
    blocked = world.apply_route_blocked_change(route.route_id, True, year=world.year, month=3, day=2)
    world.record_event(
        WorldEventRecord(
            record_id="severe",
            kind="battle",
            year=world.year,
            month=3,
            day=3,
            severity=5,
            description="A severe battle shook the capital.",
        )
    )

    card = build_monthly_report_card_view(world, world.year, 3)
    lines = ReportPresenter.render_monthly_card(card)

    assert blocked is not None
    assert [(item.category, item.record_id) for item in card.headline_events[:2]] == [
        ("world_change", blocked.record_id),
        ("conflict", "severe"),
    ]
    headline_index = lines.index("  Headlines:")
    world_news_index = next(index for index, line in enumerate(lines) if "World News" in line)
    assert headline_index < world_news_index
    assert any("World change: " in line and "was blocked." in line for line in lines)
    assert any("Conflict: A severe battle shook the capital." in line for line in lines)


def test_monthly_report_card_clusters_location_threads_from_records():
    set_locale("en")
    world = World()
    route = world.routes[0]
    blocked = world.apply_route_blocked_change(route.route_id, True, year=world.year, month=3, day=1)
    world.record_event(
        WorldEventRecord(
            record_id="capital_meeting",
            kind="meeting",
            year=world.year,
            month=3,
            day=2,
            location_id=route.from_site_id,
            severity=2,
            description="A local council reviewed the damage.",
        )
    )
    world.record_event(
        WorldEventRecord(
            record_id="thornwood_skirmish",
            kind="battle",
            year=world.year,
            month=3,
            day=3,
            location_id=route.to_site_id,
            severity=5,
            description="A route-end skirmish escalated.",
        )
    )

    card = build_monthly_report_card_view(world, world.year, 3)
    lines = ReportPresenter.render_monthly_card(card)

    assert blocked is not None
    assert card.location_threads[0].location_id == route.from_site_id
    assert card.location_threads[0].event_count == 2
    assert card.location_threads[0].world_change_count == 1
    assert "was blocked" in card.location_threads[0].headline
    assert any("Location threads" in line for line in lines)
    expected = f"{world.location_name(route.from_site_id)}: 2 event(s), 1 world change(s)"
    assert any(expected in line for line in lines)


def test_monthly_report_card_clusters_watched_actor_threads_from_records():
    set_locale("en")
    world = World()
    watched = Character("Mira", 24, "Female", "Human", "Ranger", location_id="loc_aethoria_capital")
    watched.favorite = True
    unwatched = Character("Orven", 31, "Male", "Human", "Scholar", location_id="loc_aethoria_capital")
    world.add_character(watched)
    world.add_character(unwatched)
    world.record_event(
        WorldEventRecord(
            record_id="mira_minor",
            kind="meeting",
            year=world.year,
            month=3,
            day=1,
            primary_actor_id=watched.char_id,
            severity=1,
            description="Mira met a border scout.",
        )
    )
    world.record_event(
        WorldEventRecord(
            record_id="mira_battle",
            kind="battle",
            year=world.year,
            month=3,
            day=2,
            primary_actor_id=watched.char_id,
            severity=5,
            description="Mira held the pass.",
        )
    )
    world.record_event(
        WorldEventRecord(
            record_id="orven_note",
            kind="meeting",
            year=world.year,
            month=3,
            day=3,
            primary_actor_id=unwatched.char_id,
            severity=5,
            description="Orven wrote a private note.",
        )
    )

    card = build_monthly_report_card_view(world, world.year, 3)
    lines = ReportPresenter.render_monthly_card(card)

    assert [(thread.actor_name, thread.event_count) for thread in card.watched_threads] == [("Mira", 2)]
    assert card.watched_threads[0].headline == "Mira held the pass."
    assert any("Watched threads" in line for line in lines)
    assert any("Mira: 2 event(s) | Mira held the pass." in line for line in lines)
    assert all(thread.actor_name != "Orven" for thread in card.watched_threads)


def test_world_dashboard_major_events_are_severity_first():
    set_locale("en")
    world = World()
    world.record_event(
        WorldEventRecord(
            record_id="recent",
            year=world.year,
            month=5,
            day=1,
            kind="meeting",
            severity=3,
            description="A recent moderate event.",
        )
    )
    world.record_event(
        WorldEventRecord(
            record_id="older",
            year=world.year,
            month=1,
            day=1,
            kind="battle",
            severity=5,
            description="An older severe event.",
        )
    )

    dashboard = build_world_dashboard_view(world, current_month=5)

    assert dashboard.major_events[:2] == [
        "An older severe event.",
        "A recent moderate event.",
    ]


def test_world_dashboard_hot_rumors_are_spread_and_heat_first():
    set_locale("en")
    world = World()
    capital = world.get_location_by_id("loc_aethoria_capital")
    thornwood = world.get_location_by_id("loc_thornwood")
    assert capital is not None
    assert thornwood is not None
    capital.rumor_heat = 1
    thornwood.rumor_heat = 9
    world.rumors.append(
        Rumor(
            id="rumor_old_low_spread",
            description="Fresh but quiet rumor.",
            reliability="plausible",
            source_location_id="loc_aethoria_capital",
            spread_level=1,
            age_in_months=0,
        )
    )
    world.rumors.append(
        Rumor(
            id="rumor_hot",
            description="Widespread forest rumor.",
            reliability="plausible",
            source_location_id="loc_thornwood",
            spread_level=8,
            age_in_months=3,
        )
    )

    dashboard = build_world_dashboard_view(world, current_month=1)

    assert dashboard.hot_rumors[0].startswith("Widespread forest rumor.")


def test_world_dashboard_surfaces_active_wars_until_war_ends():
    set_locale("en")
    world = World()
    world.apply_war_declaration(
        "stormwatch_wardens",
        "silverbrook_merchant_league",
        location_ids=("loc_aethoria_capital", "loc_silverbrook"),
        year=world.year,
        month=2,
    )

    dashboard = build_world_dashboard_view(world, current_month=2)

    assert [item.text for item in dashboard.active_wars] == [
        "Stormwatch Wardens declared war on Silverbrook Merchant League."
    ]

    world.apply_war_ended(
        "silverbrook_merchant_league",
        "stormwatch_wardens",
        location_ids=("loc_silverbrook", "loc_aethoria_capital"),
        year=world.year,
        month=3,
    )
    dashboard = build_world_dashboard_view(world, current_month=3)

    assert dashboard.active_wars == []


def test_world_dashboard_surfaces_current_era_and_civilization_phase():
    set_locale("en")
    world = World()
    world.apply_era_shift(
        "age_of_reckoning",
        authored_era_keys={"age_of_embers", "age_of_reckoning"},
        year=world.year,
        month=2,
    )
    world.apply_civilization_phase_drift(
        "crisis",
        score_deltas={"safety": -10},
        year=world.year,
        month=3,
    )

    dashboard = build_world_dashboard_view(world, current_month=3)

    assert dashboard.era_status is not None
    assert dashboard.era_status.era_id == "age_of_reckoning"
    assert dashboard.era_status.civilization_phase == "crisis"
    assert dashboard.era_status.text == "era: age_of_reckoning | civilization: crisis"


def test_world_dashboard_surfaces_current_occupations_until_release():
    set_locale("en")
    world = World()
    occupied = world.apply_controlling_faction_change(
        "loc_aethoria_capital",
        "stormwatch_wardens",
        year=world.year,
        month=2,
    )

    dashboard = build_world_dashboard_view(world, current_month=2)

    assert occupied is not None
    assert [item.record_id for item in dashboard.current_occupations] == [occupied.record_id]
    assert dashboard.current_occupations[0].location_id == "loc_aethoria_capital"
    assert dashboard.current_occupations[0].controlling_faction_id == "stormwatch_wardens"
    assert dashboard.current_occupations[0].text == (
        "Aethoria Capital changed controlling faction from none to Stormwatch Wardens."
    )

    world.apply_controlling_faction_change(
        "loc_aethoria_capital",
        None,
        year=world.year,
        month=3,
    )
    dashboard = build_world_dashboard_view(world, current_month=3)

    assert dashboard.current_occupations == []


def test_world_dashboard_surfaces_current_route_closures_until_reopen():
    set_locale("en")
    world = World()
    route = world.routes[0]
    blocked = world.apply_route_blocked_change(route.route_id, True, year=world.year, month=2)

    dashboard = build_world_dashboard_view(world, current_month=2)

    assert blocked is not None
    assert [item.route_id for item in dashboard.current_route_closures] == [route.route_id]
    assert [item.record_id for item in dashboard.current_route_closures] == [blocked.record_id]
    assert dashboard.current_route_closures[0].from_location_id == route.from_site_id
    assert dashboard.current_route_closures[0].to_location_id == route.to_site_id
    assert dashboard.current_route_closures[0].text == (
        f"The route from {world.location_name(route.from_site_id)} "
        f"to {world.location_name(route.to_site_id)} was blocked."
    )

    world.apply_route_blocked_change(route.route_id, False, year=world.year, month=3)
    dashboard = build_world_dashboard_view(world, current_month=3)

    assert dashboard.current_route_closures == []


def test_world_dashboard_surfaces_recent_world_change_entries():
    set_locale("en")
    world = World()
    route = world.routes[0]
    blocked = world.apply_route_blocked_change(route.route_id, True, year=world.year, month=2)
    declared = world.apply_war_declaration(
        "stormwatch_wardens",
        "silverbrook_merchant_league",
        year=world.year,
        month=3,
    )

    dashboard = build_world_dashboard_view(world, current_month=3)

    assert blocked is not None
    assert declared is not None
    assert [(item.record_id, item.category) for item in dashboard.world_change_entries] == [
        (blocked.record_id, "route"),
        (declared.record_id, "war"),
    ]

    output = CaptureOutput()
    _render_world_dashboard(dashboard, ctx=UIContext(inp=NoopInput(), out=output))

    assert "  Recent world changes" in output.lines
    assert any("Route: " in line and "was blocked." in line for line in output.lines)
    assert any(
        "War: " in line and "Stormwatch Wardens declared war on Silverbrook Merchant League." in line
        for line in output.lines
    )


def test_world_dashboard_builds_follow_up_actions_from_observer_attention():
    set_locale("en")
    world = World()
    hero = Character("Mira", 24, "Female", "Human", "Ranger", location_id="loc_aethoria_capital")
    hero.favorite = True
    world.add_character(hero)
    route = world.routes[0]
    blocked = world.apply_route_blocked_change(route.route_id, True, year=world.year, month=2)
    world.rumors.append(
        Rumor(
            id="rumor_follow",
            description="Travelers whisper that the capital road is dangerous.",
            reliability="plausible",
            source_location_id="loc_aethoria_capital",
            spread_level=5,
        )
    )

    dashboard = build_world_dashboard_view(world, current_month=2)

    assert blocked is not None
    identities = [(item.key, item.target_type, item.target_id) for item in dashboard.follow_up_actions]
    assert ("inspect_character", "character", hero.char_id) in identities
    assert ("inspect_route_closure", "route", route.route_id) in identities
    assert ("review_rumor", "rumor", "rumor_follow") in identities
    assert dashboard.follow_up_actions[0].label == "Inspect Mira at Aethoria Capital."
    assert any(item.record_id == blocked.record_id for item in dashboard.follow_up_actions)


def test_monthly_report_card_renders_world_change_category_display_labels():
    set_locale("en")
    world = World()
    route = world.routes[0]
    world.apply_route_blocked_change(route.route_id, True, month=3)
    world.record_event(
        WorldEventRecord(
            record_id="rec_occupation",
            kind="location_faction_changed",
            year=world.year,
            month=3,
            location_id="loc_aethoria_capital",
            description="Aethoria Capital changed hands.",
        )
    )

    card = build_monthly_report_card_view(world, world.year, 3)
    lines = ReportPresenter.render_monthly_card(card)
    world_news_line = next(line for line in lines if "World News" in line)

    assert "Occupation: 1" in world_news_line
    assert "Route: 1" in world_news_line
    assert "occupation: 1" not in world_news_line
    assert "route: 1" not in world_news_line


def test_yearly_report_card_surfaces_world_change_projection_details():
    set_locale("en")
    world = World()
    route = world.routes[0]
    world.apply_route_blocked_change(route.route_id, True, month=3)
    world.apply_war_declaration(
        "stormwatch_wardens",
        "silverbrook_merchant_league",
        year=world.year,
        month=4,
        day=2,
    )

    card = build_yearly_report_card_view(world, world.year)
    lines = ReportPresenter.render_yearly_card(card)

    assert [(item.category, item.count) for item in card.world_changes] == [
        ("route", 1),
        ("war", 1),
    ]
    assert [item.category for item in card.headline_events[:2]] == ["world_change", "world_change"]
    assert [item.category for item in card.world_change_entries] == ["route", "war"]
    assert any("Yearly highlights" in line for line in lines)
    assert any("Headlines" in line for line in lines)
    assert any("World News" in line and "Route: 1" in line and "War: 1" in line for line in lines)
    assert any(
        "War:" in line and "Stormwatch Wardens declared war on Silverbrook Merchant League." in line
        for line in lines
    )


def test_yearly_report_card_surfaces_rumor_threads_from_active_and_archive():
    set_locale("en")
    world = World()
    world.record_event(
        WorldEventRecord(
            record_id="evt_archive",
            kind="discovery",
            year=world.year,
            month=4,
            day=3,
            location_id="loc_thornwood_forest",
            description="A hidden shrine was found.",
        )
    )
    world.rumors.append(
        Rumor(
            id="rumor_active",
            description="Pilgrims are searching the old road.",
            reliability="plausible",
            spread_level=5,
            source_location_id="loc_aethoria_capital",
            source_event_id="evt_active",
            year_created=world.year,
            month_created=5,
        )
    )
    world.rumor_archive.append(
        Rumor(
            id="rumor_archive",
            description="Foresters whisper about a hidden shrine.",
            reliability="certain",
            spread_level=9,
            source_location_id="loc_thornwood_forest",
            source_event_id="evt_archive",
            year_created=world.year,
            month_created=4,
        )
    )

    card = build_yearly_report_card_view(world, world.year)
    lines = ReportPresenter.render_yearly_card(card)

    assert [(thread.source_event_id, thread.rumor_count) for thread in card.rumor_threads] == [
        ("evt_archive", 1),
        ("evt_active", 1),
    ]
    assert card.rumor_threads[0].source_event_text == "A hidden shrine was found."
    assert any("Rumor threads" in line for line in lines)
    assert any("evt_archive: 1 rumor(s)" in line and "certain" in line for line in lines)

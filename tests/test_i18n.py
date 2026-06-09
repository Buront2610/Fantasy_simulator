"""
tests/test_i18n.py - Unit tests for CLI localization helpers.
"""

import pytest

from fantasy_simulator.i18n import get_locale, set_locale, tr, tr_term


@pytest.fixture(autouse=True)
def _reset_locale():
    set_locale("en")
    yield
    set_locale("en")


class TestI18n:
    def test_set_locale_to_japanese(self):
        set_locale("ja")
        assert get_locale() == "ja"
        assert tr("main_menu") == "メインメニュー"

    def test_set_locale_to_english(self):
        set_locale("en")
        assert get_locale() == "en"
        assert tr("main_menu") == "MAIN MENU"

    def test_unknown_locale_falls_back_to_english(self):
        set_locale("unknown")
        assert get_locale() == "en"
        assert tr("exit") == "Exit"

    def test_translation_interpolation(self):
        set_locale("ja")
        assert "Year 42" in tr("simulation_advanced_to_year", year=42)

    def test_new_localized_labels_exist(self):
        set_locale("ja")
        assert tr("running_simulation_details", years=3, events=8).startswith("シミュレーション実行中")
        assert tr("primary_skills_label") == "主要スキル"

    def test_term_translation_in_japanese(self):
        set_locale("ja")
        assert tr_term("Warrior") == "戦士"
        assert tr_term("Quick Wit") == "機転"

    def test_event_type_translations_in_japanese(self):
        set_locale("ja")
        assert tr("event_type_meeting") == "出会い"
        assert tr("event_type_death") == "死亡"
        assert tr("event_type_battle") == "戦闘"
        assert tr("event_type_marriage") == "結婚"
        assert tr("event_type_discovery") == "発見"
        assert tr("event_type_skill_training") == "技能訓練"
        assert tr("times_suffix") == "回"

    def test_event_type_translations_in_english(self):
        set_locale("en")
        assert tr("event_type_meeting") == "Meeting"
        assert tr("event_type_death") == "Death"
        assert tr("times_suffix") == "times"

    def test_adventure_discovery_terms_in_japanese(self):
        set_locale("ja")
        assert tr_term("an ancient relic") == "古代の遺物"
        assert tr_term("a pouch of moon-silver") == "月銀の小袋"
        assert tr_term("a fragment of lost lore") == "失われし伝承の断片"
        assert tr_term("a cache of monster trophies") == "魔物の戦利品の隠し場所"

    def test_adventure_discovery_terms_passthrough_in_english(self):
        set_locale("en")
        assert tr_term("an ancient relic") == "an ancient relic"

    def test_event_log_prefix_translations(self):
        set_locale("ja")
        assert "[1000年]" == tr("event_log_prefix", year=1000)
        set_locale("en")
        assert "[Year 1000]" == tr("event_log_prefix", year=1000)

    def test_injury_status_translations_in_japanese(self):
        set_locale("ja")
        assert tr("injury_status_none") == "なし"
        assert tr("injury_status_injured") == "負傷中"

    def test_injury_status_translations_in_english(self):
        set_locale("en")
        assert tr("injury_status_none") == "none"
        assert tr("injury_status_injured") == "injured"

    def test_auto_pause_years_elapsed_translation_exists(self):
        set_locale("ja")
        assert tr("auto_pause_years_elapsed") == "時間が経過しました"
        set_locale("en")
        assert tr("auto_pause_years_elapsed") == "Time has passed"

    def test_auto_pause_recommendation_templates_render(self):
        set_locale("ja")
        assert tr("auto_pause_subreasons") == "重要な理由:"
        assert tr("auto_pause_recommendations") == "推奨確認:"
        assert tr("auto_pause_context_actor", actor="Mira") == "停止要因: Mira"
        assert tr("auto_pause_context_location", location="Capital") == "停止地点: Capital"
        assert "Mira" in tr("auto_pause_subreason_actor_in_danger", actor="Mira", location="Capital")
        assert "Mira" in tr("auto_pause_recommendation_inspect_character", actor="Mira", location="Capital")
        assert "Capital" in tr("auto_pause_subreason_world_change_notification", actor="", location="Capital")
        assert tr("auto_pause_recommendation_review_world_dashboard", actor="", location="Capital")
        assert tr("auto_pause_action_target_route", target="North Road") == "経路: North Road"
        set_locale("en")
        assert tr("auto_pause_subreasons") == "Why this matters:"
        assert tr("auto_pause_recommendations") == "Recommended checks:"
        assert tr("auto_pause_context_actor", actor="Mira") == "Cause context: Mira"
        assert tr("auto_pause_context_location", location="Capital") == "Cause context: Capital"
        assert "Mira" in tr("auto_pause_subreason_actor_in_danger", actor="Mira", location="Capital")
        assert "Mira" in tr("auto_pause_recommendation_inspect_character", actor="Mira", location="Capital")
        assert "Capital" in tr("auto_pause_subreason_world_change_notification", actor="", location="Capital")
        assert tr("auto_pause_recommendation_review_world_dashboard", actor="", location="Capital")
        assert tr("auto_pause_action_target_route", target="North Road") == "route: North Road"

    def test_rumor_board_templates_render(self):
        set_locale("ja")
        assert tr("rumor_board_menu") == "噂一覧"
        assert "Aethoria" in tr("rumor_board_meta", location="Aethoria", age=2, spread=4, event_id="evt1")
        assert "Aethoria" in tr("rumor_board_detail_source", location="Aethoria", age=2, spread=4)
        assert "local" in tr(
            "rumor_board_detail_tracking",
            audience="local",
            bias="local",
            distortion=1,
            tracked=tr("rumor_tracked_yes"),
        )
        set_locale("en")
        assert tr("rumor_board_menu") == "Rumor board"
        assert "evt1" in tr("rumor_board_meta", location="Aethoria", age=2, spread=4, event_id="evt1")
        assert "Aethoria" in tr("rumor_board_detail_source", location="Aethoria", age=2, spread=4)
        assert tr("rumor_tracked_marker") == "[tracked]"
        assert "tracked: yes" in tr(
            "rumor_board_detail_tracking",
            audience="local",
            bias="local",
            distortion=1,
            tracked=tr("rumor_tracked_yes"),
        )

    def test_report_headline_templates_render(self):
        set_locale("ja")
        assert tr("report_section_headlines") == "見出し"
        assert tr("report_headline_category_world_change") == "世界変化"
        assert "Aethoria" in tr(
            "report_location_thread_line",
            location="Aethoria",
            count=2,
            world_changes=1,
            headline="変化あり",
        )
        assert "Mira" in tr("report_watched_thread_line", actor="Mira", count=2, headline="変化あり")
        assert "経路" in tr(
            "report_world_change_thread_line",
            category="経路",
            count=2,
            locations="Aethoria",
            headline="変化あり",
        )
        set_locale("en")
        assert tr("report_section_headlines") == "Headlines"
        assert tr("report_headline_category_world_change") == "World change"
        assert "2 event(s)" in tr(
            "report_location_thread_line",
            location="Aethoria",
            count=2,
            world_changes=1,
            headline="Changed",
        )
        assert tr("report_watched_thread_line", actor="Mira", count=2, headline="Changed") == (
            "    Mira: 2 event(s) | Changed"
        )
        assert tr(
            "report_world_change_thread_line",
            category="Route",
            count=2,
            locations="Aethoria",
            headline="Changed",
        ) == "    Route: 2 change(s), Aethoria | Changed"
        assert tr(
            "report_rumor_thread_line",
            source_event="evt1",
            count=2,
            location="Aethoria",
            reliability="plausible",
            spread=7,
            headline="Changed",
        ) == "    evt1: 2 rumor(s), Aethoria, plausible, spread 7/10 | Changed"

    def test_dashboard_templates_render(self):
        set_locale("ja")
        assert tr("dashboard_menu") == "世界ダッシュボード"
        assert "Aethoria" in tr("dashboard_title", world="Aethoria")
        assert tr("dashboard_follow_up") == "次の確認"
        assert "Mira" in tr("dashboard_follow_up_inspect_character", actor="Mira", location="Aethoria")
        set_locale("en")
        assert tr("dashboard_menu") == "World dashboard"
        assert "Aethoria" in tr("dashboard_title", world="Aethoria")
        assert tr("dashboard_follow_up") == "Follow up"
        assert "Mira" in tr("dashboard_follow_up_inspect_character", actor="Mira", location="Aethoria")

    @pytest.mark.parametrize("locale", ["en", "ja"])
    @pytest.mark.parametrize(
        "key",
        [
            "memorial_epitaph_spouse",
            "memorial_epitaph_family",
            "memorial_epitaph_savior",
            "alias_spouse_site",
            "alias_family_site",
            "alias_savior_site",
            "alias_rescued_site",
        ],
    )
    def test_relation_specific_templates_render_without_placeholder_leaks(self, locale: str, key: str):
        set_locale(locale)
        result = tr(key, name="Aldric", year=1005, location="Thornwood", era="Age of Embers")
        assert result
        assert "Aldric" in result
        assert "{" not in result

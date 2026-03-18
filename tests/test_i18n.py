"""
tests/test_i18n.py - Unit tests for CLI localization helpers.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from i18n import get_locale, set_locale, tr, tr_term


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
        assert tr("event_type_meeting") == "meeting"
        assert tr("event_type_death") == "death"
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

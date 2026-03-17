"""
tests/test_i18n.py - Unit tests for CLI localization helpers.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from i18n import get_locale, set_locale, tr


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

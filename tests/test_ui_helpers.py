"""Tests for ui_helpers module."""

from __future__ import annotations

import unittest

from unittest.mock import patch

import fantasy_simulator.ui.ui_helpers as ui_helpers
from fantasy_simulator.ui.ui_helpers import (
    HEADER,
    _c,
    _choose_key,
    _hr,
    _read_menu_choice,
    _render_menu,
    bold,
    cyan,
    dim,
    display_width,
    fit_display_width,
    green,
    red,
    yellow,
)


class TestColorHelpers(unittest.TestCase):
    """Colour / style wrapper functions."""

    def test_bold_wraps_text(self) -> None:
        result = bold("hello")
        self.assertIn("hello", result)
        self.assertTrue(result.startswith("\033["))

    def test_red_contains_31(self) -> None:
        self.assertIn("31", red("x"))

    def test_green_contains_32(self) -> None:
        self.assertIn("32", green("x"))

    def test_yellow_contains_33(self) -> None:
        self.assertIn("33", yellow("x"))

    def test_cyan_contains_36(self) -> None:
        self.assertIn("36", cyan("x"))

    def test_dim_contains_2(self) -> None:
        self.assertIn("\033[2m", dim("x"))

    def test_raw_c_helper(self) -> None:
        self.assertEqual(_c("foo", "99"), "\033[99mfoo\033[0m")


class TestLayoutHelpers(unittest.TestCase):
    """_hr and HEADER constants."""

    def test_hr_default(self) -> None:
        line = _hr()
        self.assertTrue(line.startswith("  "))
        self.assertEqual(line, "  " + "=" * 62)

    def test_hr_custom(self) -> None:
        self.assertEqual(_hr("-", 5), "  -----")

    def test_header_contains_title(self) -> None:
        self.assertIn("FANTASY SIMULATOR", HEADER)


class TestDisplayWidthHelpers(unittest.TestCase):
    """Terminal display width helpers."""

    def test_display_width_counts_cjk_as_two_columns(self) -> None:
        self.assertEqual(display_width("A界B"), 4)

    def test_fit_display_width_preserves_target_width_with_cjk(self) -> None:
        result = fit_display_width("勇者アレクサンドリア", 10)

        self.assertEqual(display_width(result), 10)
        self.assertIn("...", result)

    def test_display_width_uses_wcwidth_when_available(self) -> None:
        with patch.object(ui_helpers, "_wcswidth", return_value=2):
            self.assertEqual(display_width("❤️"), 2)

    def test_fit_display_width_uses_wcwidth_character_widths(self) -> None:
        def fake_wcwidth(char: str) -> int:
            return 2 if char == "·" else 1

        with patch.object(ui_helpers, "_wcswidth", None), patch.object(
            ui_helpers,
            "_wcwidth",
            side_effect=fake_wcwidth,
        ):
            self.assertEqual(fit_display_width("a·b", 3, suffix=""), "a·")


class TestRenderMenu(unittest.TestCase):
    """_render_menu prints items to stdout — no input()."""

    def test_renders_all_items(self) -> None:
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            _render_menu("Choose", [("a", "Alpha"), ("b", "Beta")])
        text = buf.getvalue()
        self.assertIn("Alpha", text)
        self.assertIn("Beta", text)

    def test_renders_prompt_when_non_empty(self) -> None:
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            _render_menu("My Prompt", [("x", "X")])
        self.assertIn("My Prompt", buf.getvalue())

    def test_skips_prompt_when_empty(self) -> None:
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            _render_menu("", [("x", "X")])
        self.assertNotIn("My Prompt", buf.getvalue())


class TestReadMenuChoice(unittest.TestCase):
    """_read_menu_choice validates and returns the key."""

    @patch("builtins.input", return_value="2")
    def test_returns_key_not_label(self, _mock_input: object) -> None:
        result = _read_menu_choice(
            [("alpha", "Alpha Label"), ("beta", "Beta Label")],
        )
        self.assertEqual(result, "beta")

    @patch("builtins.input", return_value="1")
    def test_returns_first_key(self, _mock_input: object) -> None:
        result = _read_menu_choice(
            [("first", "First"), ("second", "Second")],
        )
        self.assertEqual(result, "first")

    @patch("builtins.input", return_value="")
    def test_default_selection(self, _mock_input: object) -> None:
        result = _read_menu_choice(
            [("a", "A"), ("b", "B")],
            default="2",
        )
        self.assertEqual(result, "b")


class TestChooseKeyCompat(unittest.TestCase):
    """_choose_key backward-compat wrapper delegates to render + read."""

    @patch("builtins.input", return_value="1")
    def test_returns_key(self, _mock_input: object) -> None:
        result = _choose_key("Pick", [("k", "K Label")])
        self.assertEqual(result, "k")


if __name__ == "__main__":
    unittest.main()

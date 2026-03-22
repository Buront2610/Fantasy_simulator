"""Tests for ui_helpers module."""

from __future__ import annotations

import unittest

from unittest.mock import patch

from ui_helpers import (
    HEADER,
    _c,
    _choose_key,
    _hr,
    bold,
    cyan,
    dim,
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


class TestChooseKey(unittest.TestCase):
    """_choose_key returns the key, not the display label."""

    @patch("builtins.input", return_value="2")
    def test_returns_key_not_label(self, _mock_input: object) -> None:
        result = _choose_key(
            "Pick one",
            [("alpha", "Alpha Label"), ("beta", "Beta Label")],
        )
        self.assertEqual(result, "beta")

    @patch("builtins.input", return_value="1")
    def test_returns_first_key(self, _mock_input: object) -> None:
        result = _choose_key(
            "Pick one",
            [("first", "First"), ("second", "Second")],
        )
        self.assertEqual(result, "first")

    @patch("builtins.input", return_value="")
    def test_default_selection(self, _mock_input: object) -> None:
        result = _choose_key(
            "Pick one",
            [("a", "A"), ("b", "B")],
            default="2",
        )
        self.assertEqual(result, "b")


if __name__ == "__main__":
    unittest.main()

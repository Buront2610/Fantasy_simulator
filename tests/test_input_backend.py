"""Tests for ui.input_backend — InputBackend protocol and StdInputBackend.

These tests verify:
- StdInputBackend.read_line delegates to builtin input().
- StdInputBackend.read_menu_key reads a validated index and returns the key.
- StdInputBackend.pause delegates to _pause without error.
- A custom class satisfying the InputBackend protocol works polymorphically.
- Default argument edge cases are handled.
"""

from __future__ import annotations

import unittest
from os import environ
from unittest.mock import patch, MagicMock

from fantasy_simulator.i18n import set_locale
from fantasy_simulator.ui.input_backend import (
    InputBackend,
    PromptToolkitInputBackend,
    StdInputBackend,
    create_default_input_backend,
)


class TestStdInputBackendReadLine(unittest.TestCase):
    """StdInputBackend.read_line must delegate to builtin input()."""

    def setUp(self) -> None:
        self.backend = StdInputBackend()

    @patch("builtins.input", return_value="hello world")
    def test_returns_user_input(self, mock_input: MagicMock) -> None:
        result = self.backend.read_line("prompt> ")
        self.assertEqual(result, "hello world")
        mock_input.assert_called_once_with("prompt> ")

    @patch("builtins.input", return_value="")
    def test_returns_empty_string_on_empty_input(self, mock_input: MagicMock) -> None:
        result = self.backend.read_line()
        self.assertEqual(result, "")
        mock_input.assert_called_once_with("")

    @patch("builtins.input", return_value="  spaced  ")
    def test_preserves_whitespace(self, mock_input: MagicMock) -> None:
        """read_line should NOT strip — that's the caller's job."""
        result = self.backend.read_line()
        self.assertEqual(result, "  spaced  ")


class TestStdInputBackendReadMenuKey(unittest.TestCase):
    """StdInputBackend.read_menu_key must return the key, not the display label."""

    def setUp(self) -> None:
        set_locale("en")
        self.backend = StdInputBackend()

    @patch("builtins.input", return_value="2")
    def test_returns_key_for_selected_option(self, _mock: MagicMock) -> None:
        result = self.backend.read_menu_key(
            [("alpha", "Alpha Label"), ("beta", "Beta Label")],
        )
        self.assertEqual(result, "beta")

    @patch("builtins.input", return_value="1")
    def test_returns_first_key(self, _mock: MagicMock) -> None:
        result = self.backend.read_menu_key(
            [("first", "First Choice"), ("second", "Second Choice")],
        )
        self.assertEqual(result, "first")

    @patch("builtins.input", return_value="")
    def test_default_selection(self, _mock: MagicMock) -> None:
        """Empty input with default='2' should select the second item."""
        result = self.backend.read_menu_key(
            [("a", "A"), ("b", "B")],
            default="2",
        )
        self.assertEqual(result, "b")

    @patch("builtins.input", return_value="1")
    def test_single_option(self, _mock: MagicMock) -> None:
        """A menu with only one option should still work."""
        result = self.backend.read_menu_key(
            [("only", "The Only Option")],
        )
        self.assertEqual(result, "only")


class TestStdInputBackendPause(unittest.TestCase):
    """StdInputBackend.pause must call _pause without errors."""

    def setUp(self) -> None:
        set_locale("en")
        self.backend = StdInputBackend()

    @patch("fantasy_simulator.ui.ui_helpers._pause", return_value=None)
    def test_pause_delegates(self, mock_pause: MagicMock) -> None:
        self.backend.pause()
        mock_pause.assert_called_once()


class TestCustomInputBackend(unittest.TestCase):
    """A custom class can satisfy the InputBackend protocol."""

    def test_custom_backend_works_polymorphically(self) -> None:
        """A recording backend can capture inputs for testing."""
        class RecordingBackend:
            def __init__(self) -> None:
                self.calls: list = []

            def read_line(self, prompt: str = "") -> str:
                self.calls.append(("read_line", prompt))
                return "recorded"

            def read_menu_key(self, key_label_pairs, default=None):
                self.calls.append(("read_menu_key", len(key_label_pairs)))
                return key_label_pairs[0][0]

            def pause(self, message: str = "") -> None:
                self.calls.append(("pause", message))

        backend = RecordingBackend()
        # Verify it satisfies the protocol structurally
        self.assertTrue(isinstance(backend, InputBackend))
        # Verify it works
        self.assertEqual(backend.read_line("test> "), "recorded")
        self.assertEqual(
            backend.read_menu_key([("k", "K")]),
            "k",
        )
        backend.pause("done")
        self.assertEqual(len(backend.calls), 3)


class TestPromptToolkitDefaultFactory(unittest.TestCase):
    """Default input backend factory should degrade gracefully."""

    def test_factory_falls_back_to_std_when_prompt_toolkit_unavailable(self) -> None:
        with (
            patch.dict(environ, {"FANTASY_SIMULATOR_INPUT_BACKEND": "prompt_toolkit"}, clear=False),
            patch(
                "fantasy_simulator.ui.input_backend.PromptToolkitInputBackend",
                side_effect=ImportError("no prompt_toolkit"),
            ),
        ):
            backend = create_default_input_backend()
        self.assertIsInstance(backend, StdInputBackend)

    def test_factory_defaults_to_std_without_opt_in(self) -> None:
        with patch.dict(environ, {"FANTASY_SIMULATOR_INPUT_BACKEND": ""}, clear=False):
            backend = create_default_input_backend()
        self.assertIsInstance(backend, StdInputBackend)

    def test_factory_prefers_prompt_toolkit_when_available(self) -> None:
        fake = object()
        with (
            patch.dict(environ, {"FANTASY_SIMULATOR_INPUT_BACKEND": "prompt_toolkit"}, clear=False),
            patch(
                "fantasy_simulator.ui.input_backend.PromptToolkitInputBackend",
                return_value=fake,
            ),
        ):
            backend = create_default_input_backend()
        self.assertIs(backend, fake)

    def test_prompt_toolkit_menu_key_uses_default(self) -> None:
        backend = PromptToolkitInputBackend.__new__(PromptToolkitInputBackend)
        backend._session = type("S", (), {"prompt": staticmethod(lambda *_a, **_k: "")})()
        key = backend.read_menu_key([("a", "A"), ("b", "B")], default="2")
        self.assertEqual(key, "b")

    def test_prompt_toolkit_invalid_then_valid_string(self) -> None:
        backend = PromptToolkitInputBackend.__new__(PromptToolkitInputBackend)
        replies = iter(["invalid", "2"])
        backend._session = type("S", (), {"prompt": staticmethod(lambda *_a, **_k: next(replies))})()
        key = backend.read_menu_key([("alpha", "A"), ("beta", "B")], default="1")
        self.assertEqual(key, "beta")

    def test_prompt_toolkit_out_of_range_then_valid(self) -> None:
        backend = PromptToolkitInputBackend.__new__(PromptToolkitInputBackend)
        replies = iter(["99", "1"])
        backend._session = type("S", (), {"prompt": staticmethod(lambda *_a, **_k: next(replies))})()
        key = backend.read_menu_key([("alpha", "A"), ("beta", "B")], default=None)
        self.assertEqual(key, "alpha")

    def test_factory_does_not_swallow_runtime_error(self) -> None:
        with (
            patch.dict(environ, {"FANTASY_SIMULATOR_INPUT_BACKEND": "prompt_toolkit"}, clear=False),
            patch(
                "fantasy_simulator.ui.input_backend.PromptToolkitInputBackend",
                side_effect=RuntimeError("boom"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                create_default_input_backend()


if __name__ == "__main__":
    unittest.main()

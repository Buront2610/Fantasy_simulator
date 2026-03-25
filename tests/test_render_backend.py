"""Tests for ui.render_backend — RenderBackend protocol and PrintRenderBackend.

These tests verify:
- PrintRenderBackend.print_line outputs text to stdout.
- PrintRenderBackend.print_heading wraps text with bold ANSI codes.
- PrintRenderBackend.print_separator outputs a horizontal rule.
- PrintRenderBackend.print_error wraps text with red ANSI codes.
- PrintRenderBackend.print_success wraps text with green ANSI codes.
- PrintRenderBackend.print_warning wraps text with yellow ANSI codes.
- A custom class satisfying the RenderBackend protocol works polymorphically.
"""

from __future__ import annotations

import io
import re
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from fantasy_simulator.ui.render_backend import (
    PrintRenderBackend,
    RenderBackend,
    create_default_render_backend,
)


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


class TestPrintRenderBackendPrintLine(unittest.TestCase):
    """print_line must send text to stdout."""

    def setUp(self) -> None:
        self.backend = PrintRenderBackend()

    def test_prints_plain_text(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.backend.print_line("Hello, world!")
        self.assertEqual(buf.getvalue().strip(), "Hello, world!")

    def test_prints_empty_line(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.backend.print_line()
        self.assertEqual(buf.getvalue(), "\n")

    def test_prints_unicode_text(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.backend.print_line("日本語テスト")
        self.assertIn("日本語テスト", buf.getvalue())


class TestPrintRenderBackendHeading(unittest.TestCase):
    """print_heading must output bold-formatted text."""

    def setUp(self) -> None:
        self.backend = PrintRenderBackend()

    def test_contains_bold_ansi_code(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.backend.print_heading("Title")
        output = buf.getvalue()
        # Bold is ANSI code 1
        self.assertIn("\033[1m", output)
        stripped = _ANSI_RE.sub("", output)
        self.assertIn("Title", stripped)


class TestPrintRenderBackendSeparator(unittest.TestCase):
    """print_separator must output a horizontal rule with configurable char/width."""

    def setUp(self) -> None:
        self.backend = PrintRenderBackend()

    def test_default_separator(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.backend.print_separator()
        output = buf.getvalue().strip()
        # Default: '=' * 62 with leading spaces
        self.assertIn("=" * 62, output)

    def test_custom_char_and_width(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.backend.print_separator("-", 10)
        output = buf.getvalue().strip()
        self.assertIn("-" * 10, output)
        self.assertNotIn("-" * 11, output)


class TestPrintRenderBackendColors(unittest.TestCase):
    """print_error / print_success / print_warning must use correct ANSI colors."""

    def setUp(self) -> None:
        self.backend = PrintRenderBackend()

    def test_error_uses_red(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.backend.print_error("fail")
        output = buf.getvalue()
        # Red is ANSI code 31
        self.assertIn("\033[31m", output)
        self.assertIn("fail", _ANSI_RE.sub("", output))

    def test_success_uses_green(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.backend.print_success("ok")
        output = buf.getvalue()
        # Green is ANSI code 32
        self.assertIn("\033[32m", output)
        self.assertIn("ok", _ANSI_RE.sub("", output))

    def test_warning_uses_yellow(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.backend.print_warning("caution")
        output = buf.getvalue()
        # Yellow is ANSI code 33
        self.assertIn("\033[33m", output)
        self.assertIn("caution", _ANSI_RE.sub("", output))

    def test_highlighted_uses_cyan(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.backend.print_highlighted("item")
        output = buf.getvalue()
        # Cyan is ANSI code 36
        self.assertIn("\033[36m", output)
        self.assertIn("item", _ANSI_RE.sub("", output))

    def test_format_status_positive_uses_green(self) -> None:
        result = self.backend.format_status("Alive", True)
        self.assertIn("\033[32m", result)
        self.assertIn("Alive", _ANSI_RE.sub("", result))

    def test_format_status_negative_uses_red(self) -> None:
        result = self.backend.format_status("Dead", False)
        self.assertIn("\033[31m", result)
        self.assertIn("Dead", _ANSI_RE.sub("", result))

    def test_format_status_returns_string_not_none(self) -> None:
        self.assertIsInstance(self.backend.format_status("X", True), str)
        self.assertIsInstance(self.backend.format_status("X", False), str)

    def test_print_wrapped_uses_print_line(self) -> None:
        """print_wrapped must not call print() directly — it must go through
        self.print_line(), so a subclass can intercept all output."""
        lines: list = []

        class CapturingBackend(PrintRenderBackend):
            def print_line(self, text: str = "") -> None:  # type: ignore[override]
                lines.append(text)

        backend = CapturingBackend()
        captured = io.StringIO()
        with redirect_stdout(captured):
            backend.print_wrapped("Hello world, this is a test of wrapping.", indent=2)

        # All output must have been captured by print_line override
        self.assertTrue(len(lines) > 0, "print_line was never called")
        # Nothing should have leaked to actual stdout
        self.assertEqual(captured.getvalue(), "")

    def test_print_menu_renders_items_to_stdout(self) -> None:
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.backend.print_menu(
                "Choose",
                [("a", "Alpha"), ("b", "Beta")],
                default="1",
            )
        text = buf.getvalue()
        self.assertIn("Alpha", text)
        self.assertIn("Beta", text)

    def test_print_menu_no_input_call(self) -> None:
        """print_menu must not call input() — only rendering, no reading."""
        with patch("builtins.input", side_effect=AssertionError("input() was called")):
            buf = io.StringIO()
            with redirect_stdout(buf):
                self.backend.print_menu("Pick", [("x", "X")])


class TestCustomRenderBackend(unittest.TestCase):
    """A custom class can satisfy the RenderBackend protocol."""

    def test_buffer_backend_captures_all_output(self) -> None:
        """A buffer backend can collect all output for snapshot testing."""
        class BufferRenderBackend:
            def __init__(self) -> None:
                self.lines: list = []

            def print_line(self, text: str = "") -> None:
                self.lines.append(("line", text))

            def print_heading(self, text: str) -> None:
                self.lines.append(("heading", text))

            def print_separator(self, char: str = "=", width: int = 62) -> None:
                self.lines.append(("sep", char, width))

            def print_error(self, text: str) -> None:
                self.lines.append(("error", text))

            def print_success(self, text: str) -> None:
                self.lines.append(("success", text))

            def print_warning(self, text: str) -> None:
                self.lines.append(("warning", text))

            def print_wrapped(self, text: str, indent: int = 4) -> None:
                self.lines.append(("wrapped", text))

            def print_dim(self, text: str) -> None:
                self.lines.append(("dim", text))

            def print_highlighted(self, text: str) -> None:
                self.lines.append(("highlighted", text))

            def format_status(self, text: str, positive: bool) -> str:
                return text  # plain, no ANSI

            def print_menu(self, prompt, key_label_pairs, default=None) -> None:
                self.lines.append(("menu", prompt, len(key_label_pairs)))

        backend = BufferRenderBackend()
        self.assertIsInstance(backend, RenderBackend)

        backend.print_line("hello")
        backend.print_heading("TITLE")
        backend.print_separator("-", 20)
        backend.print_error("err")
        backend.print_success("ok")
        backend.print_warning("warn")
        backend.print_wrapped("long text")
        backend.print_dim("faint")
        backend.print_highlighted("accent")

        self.assertEqual(len(backend.lines), 9)
        self.assertEqual(backend.lines[0], ("line", "hello"))
        self.assertEqual(backend.lines[1], ("heading", "TITLE"))
        self.assertEqual(backend.lines[2], ("sep", "-", 20))
        self.assertEqual(backend.lines[3], ("error", "err"))
        self.assertEqual(backend.lines[4], ("success", "ok"))
        self.assertEqual(backend.lines[5], ("warning", "warn"))
        self.assertEqual(backend.lines[6], ("wrapped", "long text"))
        self.assertEqual(backend.lines[7], ("dim", "faint"))
        self.assertEqual(backend.lines[8], ("highlighted", "accent"))


class TestRenderBackendFactory(unittest.TestCase):
    """Default renderer factory should degrade gracefully."""

    def test_factory_falls_back_to_print_backend(self) -> None:
        with patch(
            "fantasy_simulator.ui.render_backend.RichRenderBackend",
            side_effect=ImportError("no rich"),
        ):
            backend = create_default_render_backend()
        self.assertIsInstance(backend, PrintRenderBackend)


if __name__ == "__main__":
    unittest.main()

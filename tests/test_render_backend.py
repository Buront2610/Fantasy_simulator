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
from os import environ
import re
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from fantasy_simulator.ui.render_backend import (
    PrintRenderBackend,
    RenderBackend,
    create_default_render_backend,
)

try:
    import rich  # noqa: F401
    _RICH_AVAILABLE = True
except ImportError:
    _RICH_AVAILABLE = False


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

            def print_panel(self, title: str, text: str) -> None:
                self.lines.append(("panel", title, text))

            def get_terminal_width(self) -> int:
                return 80

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
        with (
            patch.dict(environ, {"FANTASY_SIMULATOR_UI_BACKEND": "rich"}, clear=False),
            patch(
                "fantasy_simulator.ui.render_backend.RichRenderBackend",
                side_effect=ImportError("no rich"),
            ),
        ):
            backend = create_default_render_backend()
        self.assertIsInstance(backend, PrintRenderBackend)

    def test_factory_defaults_to_print_without_opt_in(self) -> None:
        with patch.dict(environ, {"FANTASY_SIMULATOR_UI_BACKEND": ""}, clear=False):
            backend = create_default_render_backend()
        self.assertIsInstance(backend, PrintRenderBackend)

    def test_print_backend_panel_outputs_title_and_body(self) -> None:
        backend = PrintRenderBackend()
        buf = io.StringIO()
        with redirect_stdout(buf):
            backend.print_panel("PanelTitle", "line1\nline2")
        text = _ANSI_RE.sub("", buf.getvalue())
        self.assertIn("PanelTitle", text)
        self.assertIn("line1", text)
        self.assertIn("line2", text)

    def test_factory_does_not_swallow_runtime_error(self) -> None:
        with (
            patch.dict(environ, {"FANTASY_SIMULATOR_UI_BACKEND": "rich"}, clear=False),
            patch(
                "fantasy_simulator.ui.render_backend.RichRenderBackend",
                side_effect=RuntimeError("boom"),
            ),
        ):
            with self.assertRaises(RuntimeError):
                create_default_render_backend()


@unittest.skipUnless(_RICH_AVAILABLE, "rich is not installed")
class TestRichRenderBackendSafety(unittest.TestCase):
    """Rich backend should avoid implicit markup interpolation hazards."""

    def test_print_line_disables_markup(self) -> None:
        from fantasy_simulator.ui.render_backend import RichRenderBackend
        from rich.text import Text

        backend = RichRenderBackend.__new__(RichRenderBackend)
        backend._console = unittest.mock.Mock()
        backend.print_line("[danger]")
        (arg,), _kwargs = backend._console.print.call_args
        self.assertIsInstance(arg, Text)
        self.assertEqual(arg.plain, "[danger]")

    def test_print_heading_disables_markup_and_uses_style(self) -> None:
        from fantasy_simulator.ui.render_backend import RichRenderBackend
        from rich.text import Text

        backend = RichRenderBackend.__new__(RichRenderBackend)
        backend._console = unittest.mock.Mock()
        backend.print_heading("[Heading]")
        (arg,), _kwargs = backend._console.print.call_args
        self.assertIsInstance(arg, Text)
        self.assertEqual(arg.plain, "[Heading]")

    def test_print_error_uses_text_renderable(self) -> None:
        from fantasy_simulator.ui.render_backend import RichRenderBackend
        from rich.text import Text

        backend = RichRenderBackend.__new__(RichRenderBackend)
        backend._console = unittest.mock.Mock()
        backend.print_error("[err]")
        (arg,), _kwargs = backend._console.print.call_args
        self.assertIsInstance(arg, Text)
        self.assertEqual(arg.plain, "[err]")

    def test_format_status_returns_plain_text(self) -> None:
        from fantasy_simulator.ui.render_backend import RichRenderBackend

        backend = RichRenderBackend.__new__(RichRenderBackend)
        backend._console = unittest.mock.Mock()
        status = backend.format_status("[alive]", True)
        self.assertIn("[alive]", status)
        self.assertIn("\033[32m", status)

    def test_print_panel_uses_text_renderables(self) -> None:
        from fantasy_simulator.ui.render_backend import RichRenderBackend
        from rich.text import Text

        backend = RichRenderBackend.__new__(RichRenderBackend)
        backend._console = unittest.mock.Mock()
        with patch("rich.panel.Panel") as mock_panel:
            backend.print_panel("[title]", "[body]")
        _args, kwargs = mock_panel.call_args
        self.assertIsInstance(_args[0], Text)
        self.assertEqual(_args[0].plain, "[body]")
        self.assertIsInstance(kwargs["title"], Text)
        self.assertEqual(kwargs["title"].plain, "[title]")
        self.assertFalse(kwargs["expand"])
        self.assertEqual(kwargs["padding"], (0, 0))

    def test_print_wrapped_uses_rich_fold_with_indent(self) -> None:
        from fantasy_simulator.ui.render_backend import RichRenderBackend
        from rich.text import Text

        backend = RichRenderBackend.__new__(RichRenderBackend)
        backend._console = unittest.mock.Mock()
        backend.print_wrapped("日本語 mixed width line", indent=2)
        (renderable,), kwargs = backend._console.print.call_args
        self.assertIsInstance(renderable, Text)
        self.assertTrue(renderable.plain.startswith("  "))
        self.assertEqual(kwargs["overflow"], "fold")
        self.assertFalse(kwargs["no_wrap"])

    def test_print_menu_uses_i18n_and_no_markup_strings(self) -> None:
        from fantasy_simulator.i18n import set_locale
        from fantasy_simulator.ui.render_backend import RichRenderBackend

        set_locale("ja")
        backend = RichRenderBackend.__new__(RichRenderBackend)
        backend._console = unittest.mock.Mock()

        class FakeTable:
            def __init__(self, *args, **kwargs) -> None:
                self.columns = []
                self.rows = []

            def add_column(self, name, **_kwargs) -> None:
                self.columns.append(name)

            def add_row(self, idx, label) -> None:
                self.rows.append((idx, label))

        fake_table = FakeTable()
        fake_panel = object()
        with (
            patch("rich.table.Table", return_value=fake_table),
            patch("rich.panel.Panel", return_value=fake_panel),
        ):
            backend.print_menu("Prompt", [("k1", "項目A"), ("k2", "項目B")], default="1")

        self.assertIn("項目", fake_table.columns)
        row_label = fake_table.rows[0][1]
        self.assertFalse(isinstance(row_label, str))
        backend._console.print.assert_called_once_with(fake_panel)


if __name__ == "__main__":
    unittest.main()

"""
render_backend.py - Abstract rendering interface for the CLI.

Defines ``RenderBackend`` so that the actual output mechanism (plain
``print()``, Rich console, Textual widgets, …) can be swapped without
touching input or domain code.
"""

from __future__ import annotations

import textwrap
from typing import List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class RenderBackend(Protocol):
    """Minimal contract every output provider must satisfy."""

    def print_line(self, text: str = "") -> None:
        """Print a single line of text."""
        ...  # pragma: no cover

    def print_heading(self, text: str) -> None:
        """Print a heading / title line."""
        ...  # pragma: no cover

    def print_separator(self, char: str = "=", width: int = 62) -> None:
        """Print a horizontal separator."""
        ...  # pragma: no cover

    def print_error(self, text: str) -> None:
        """Print an error message (e.g. in red)."""
        ...  # pragma: no cover

    def print_success(self, text: str) -> None:
        """Print a success message (e.g. in green)."""
        ...  # pragma: no cover

    def print_warning(self, text: str) -> None:
        """Print a warning message (e.g. in yellow)."""
        ...  # pragma: no cover

    def print_wrapped(self, text: str, indent: int = 4) -> None:
        """Print word-wrapped text with the given indentation."""
        ...  # pragma: no cover

    def print_dim(self, text: str) -> None:
        """Print dimmed / muted text."""
        ...  # pragma: no cover

    def print_highlighted(self, text: str) -> None:
        """Print highlighted / accented text (e.g. in cyan)."""
        ...  # pragma: no cover

    def print_menu(
        self,
        prompt: str,
        key_label_pairs: List[Tuple[str, str]],
        default: Optional[str] = None,
    ) -> None:
        """Render a numbered menu.

        Displays *prompt* as a heading, then each ``(key, label)`` pair as
        a numbered item.  The selected item is not read here — that is
        handled by ``InputBackend.read_menu_key()``.
        """
        ...  # pragma: no cover

    def format_status(self, text: str, positive: bool) -> str:
        """Return *text* formatted as positive (green) or negative (red).

        Intended for embedding inside a larger ``print_line`` call where
        only part of the string carries semantic colour — e.g. a roster
        row or a progress line with an inline alive-count.
        Plain / test backends may return *text* unchanged.
        """
        ...  # pragma: no cover


class PrintRenderBackend:
    """Default backend that delegates to plain ``print()`` with ANSI codes."""

    def print_line(self, text: str = "") -> None:
        print(text)

    def print_heading(self, text: str) -> None:
        from .ui_helpers import bold
        print(bold(text))

    def print_separator(self, char: str = "=", width: int = 62) -> None:
        from .ui_helpers import _hr
        print(_hr(char, width))

    def print_error(self, text: str) -> None:
        from .ui_helpers import red
        print(red(text))

    def print_success(self, text: str) -> None:
        from .ui_helpers import green
        print(green(text))

    def print_warning(self, text: str) -> None:
        from .ui_helpers import yellow
        print(yellow(text))

    def print_wrapped(self, text: str, indent: int = 4) -> None:
        prefix = " " * indent
        for line in text.splitlines():
            if line.strip():
                for wrapped in textwrap.wrap(
                    line,
                    width=70,
                    initial_indent=prefix,
                    subsequent_indent=prefix,
                ):
                    self.print_line(wrapped)
            else:
                self.print_line()

    def print_dim(self, text: str) -> None:
        from .ui_helpers import dim
        print(dim(text))

    def print_highlighted(self, text: str) -> None:
        from .ui_helpers import cyan
        print(cyan(text))

    def print_menu(
        self,
        prompt: str,
        key_label_pairs: List[Tuple[str, str]],
        default: Optional[str] = None,
    ) -> None:
        from .ui_helpers import _render_menu
        _render_menu(prompt, key_label_pairs, default)

    def format_status(self, text: str, positive: bool) -> str:
        from .ui_helpers import green, red
        return green(text) if positive else red(text)

    def print_panel(self, title: str, text: str) -> None:
        self.print_separator("-")
        self.print_heading(f"  {title}")
        for line in text.splitlines():
            self.print_line(line)
        self.print_separator("-")

    def get_terminal_width(self) -> int:
        """Best-effort terminal width for responsive rendering."""
        import shutil

        return shutil.get_terminal_size(fallback=(80, 24)).columns


class RichRenderBackend(PrintRenderBackend):
    """Thin Rich-based shell with graceful fallback to ANSI/plain rendering."""

    def __init__(self) -> None:
        from rich.console import Console

        self._console = Console()
        self._force_plain = not self._console.color_system

    def print_line(self, text: str = "") -> None:
        self._console.print(text)

    def print_heading(self, text: str) -> None:
        self._console.print(f"[bold]{text}[/bold]")

    def print_separator(self, char: str = "=", width: int = 62) -> None:
        from rich.rule import Rule

        self._console.print(Rule(characters=char, style="dim"))

    def print_error(self, text: str) -> None:
        self._console.print(text, style="bold red")

    def print_success(self, text: str) -> None:
        self._console.print(text, style="bold green")

    def print_warning(self, text: str) -> None:
        self._console.print(text, style="bold yellow")

    def print_dim(self, text: str) -> None:
        self._console.print(text, style="dim")

    def print_highlighted(self, text: str) -> None:
        self._console.print(text, style="bold cyan")

    def print_menu(
        self,
        prompt: str,
        key_label_pairs: List[Tuple[str, str]],
        default: Optional[str] = None,
    ) -> None:
        from rich.panel import Panel
        from rich.table import Table

        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("#", justify="right", style="bold")
        table.add_column("Option")
        for i, (_, label) in enumerate(key_label_pairs, 1):
            mark = " [dim](default)[/dim]" if default == str(i) else ""
            table.add_row(str(i), f"{label}{mark}")
        self._console.print(Panel(table, title=prompt, border_style="cyan"))

    def print_panel(self, title: str, text: str) -> None:
        from rich.panel import Panel

        self._console.print(Panel(text, title=title, border_style="blue"))

    def format_status(self, text: str, positive: bool) -> str:
        if self._force_plain:
            return text
        return f"[green]{text}[/green]" if positive else f"[red]{text}[/red]"

    def get_terminal_width(self) -> int:
        return self._console.size.width


def create_default_render_backend() -> RenderBackend:
    """Return Rich backend when available; otherwise ANSI print backend."""
    try:
        return RichRenderBackend()
    except Exception:
        return PrintRenderBackend()

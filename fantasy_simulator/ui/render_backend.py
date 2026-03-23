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

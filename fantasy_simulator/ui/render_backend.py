"""
render_backend.py - Abstract rendering interface for the CLI.

Defines ``RenderBackend`` so that the actual output mechanism (plain
``print()``, Rich console, Textual widgets, …) can be swapped without
touching input or domain code.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


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

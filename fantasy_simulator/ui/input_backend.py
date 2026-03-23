"""
input_backend.py - Abstract input interface for the CLI.

Defines ``InputBackend`` so that the actual input mechanism (builtin
``input()``, prompt_toolkit, Textual widgets, …) can be swapped without
touching presentation or domain code.
"""

from __future__ import annotations

from typing import List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class InputBackend(Protocol):
    """Minimal contract every input provider must satisfy."""

    def read_line(self, prompt: str = "") -> str:
        """Read a single line of text from the user."""
        ...  # pragma: no cover

    def choose_key(
        self,
        prompt: str,
        key_label_pairs: List[Tuple[str, str]],
        default: Optional[str] = None,
    ) -> str:
        """Display a numbered menu and return the **key** of the selected item.

        *key_label_pairs* is ``[(key, display_label), ...]``.
        *default* is a 1-based index string (e.g. ``"1"``).
        """
        ...  # pragma: no cover

    def pause(self, message: str = "") -> None:
        """Wait for the user to press Enter."""
        ...  # pragma: no cover


class StdInputBackend:
    """Default backend that delegates to Python's builtin ``input()``."""

    def read_line(self, prompt: str = "") -> str:
        return input(prompt)

    def choose_key(
        self,
        prompt: str,
        key_label_pairs: List[Tuple[str, str]],
        default: Optional[str] = None,
    ) -> str:
        from .ui_helpers import _choose_key
        return _choose_key(prompt, key_label_pairs, default)

    def pause(self, message: str = "") -> None:
        from .ui_helpers import _pause
        _pause(message)
